"""云端 AI 分析层：可插拔 provider（InfiniSynapse / 任意 OpenAI 兼容端点）。

设计原则：
- 默认关闭；仅当配置了对应 provider 的密钥时才启用。未启用或缺失 key 时，
  调用方（``/api/ask``、统计公报）自动回退到本地统计，只加一条说明、不报错。
- **两个 provider，用 ``AI_PROVIDER`` 选择**：
  - ``infinisynapse``（默认）：国内 InfiniSynapse Server API。
    直连其 REST 接口（``/api/ai/message`` 发起 newTask +
    ``/api/ai/events`` 消费 SSE 流），不依赖 agent_infini 二进制；
    每次请求都走真实 HTTPS 接口，调用记录可在服务端审计，满足比赛
    「集成 InfiniSynapse API、调用日志可查验」的硬性要求。
  - ``openai_compat``：任意 OpenAI 兼容的 ``/chat/completions`` 端点。
    覆盖 OpenAI、OpenRouter、Groq、DeepSeek、Moonshot 以及本地
    vLLM / Ollama / LM Studio——它们共用同一套协议，因此一个实现即可接多家。
    这样海外用户拿不到 InfiniSynapse key 时也能用上「AI 解读」。
- 两个 provider 的 ``analyze()`` 返回结构一致（``{task_id, done, result}``），
  调用方无需关心底层是哪一家。
- 外部请求会经系统 HTTP(S)_PROXY 环境变量，因此在配置了
  127.0.0.1:7897 代理的机器上可正常联网。

注意：本模块不会执行任何远程安装脚本，也不会联网下载二进制。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import cast, Iterator

import requests
import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

# Vercel / Serverless 等长连接受限环境：缩短超时，避免函数挂死
_DEFAULT_TIMEOUT = int(os.environ.get("INFINI_TIMEOUT", "120"))


class AgentInfiniError(Exception):
    """InfiniSynapse API 调用相关错误。"""


def _load_cfg() -> dict[str, object]:
    """读取 config.yaml；**文件不存在时返回空字典**（与 `src/db.py` 的 Vercel 兜底一致）。

    Serverless 部署包里不一定带 config.yaml，此时任何 provider 都视为未配置，
    走「本地统计」降级路径，而不是抛 FileNotFoundError 打断请求。
    """
    try:
        with CONFIG_PATH.open(encoding="utf-8") as f:
            return cast("dict[str, object]", yaml.safe_load(f) or {})
    except OSError:
        return {}


def _lang_header(lang: str | None) -> str:
    """界面语言 -> InfiniSynapse `x-lang` 取值。"""
    if lang and lang.lower().startswith("zh"):
        return "zh_CN"
    if lang and lang.lower().startswith("en"):
        return "en_US"
    return lang or "zh_CN"


class InfiniSynapseAnalyzer:
    """直连 InfiniSynapse Server API 的分析器（SSE 流式收集结果）。"""

    def __init__(self, api_key: str, server: str = "https://app.infinisynapse.cn",
                 prefer_language: str = "zh_CN"):
        self.api_key: str = api_key
        self.server: str = server.rstrip("/")
        self.prefer_language: str = prefer_language
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "x-lang": prefer_language,
        })

    # ------------------------------------------------------------------
    def new_task(self, query: str, conn_id: str | None = None) -> tuple[str, str]:
        """发起 newTask，返回 (task_id, conn_id)。"""
        task_id = str(uuid.uuid4())
        if conn_id is None:
            conn_id = str(uuid.uuid4())
        payload = {
            "type": "newTask",
            "taskId": task_id,
            "connId": conn_id,
            "text": query,
            "images": [],
            "files": [],
        }
        r = self._session.post(
            f"{self.server}/api/ai/message", json=payload,
            timeout=_DEFAULT_TIMEOUT,
        )
        if r.status_code >= 400:
            raise AgentInfiniError(f"newTask 失败({r.status_code}): {r.text[:200]}")
        return task_id, conn_id

    def _iter_events(self, conn_id: str) -> Iterator[dict[str, object]]:
        """消费 SSE 事件流，逐条 yield 解析后的 data JSON。"""
        url = f"{self.server}/api/ai/events?connId={conn_id}"
        with self._session.get(
            url, headers={"Accept": "text/event-stream"},
            stream=True, timeout=_DEFAULT_TIMEOUT,
        ) as resp:
            if resp.status_code >= 400:
                raise AgentInfiniError(
                    f"events 流失败({resp.status_code}): {resp.text[:200]}")
            buf = ""
            for chunk in resp.iter_lines(decode_unicode=True):
                # requests 2.34 起自带类型标注，把 iter_lines 的元素声明为 bytes，
                # 与 decode_unicode=True 的实际返回（str）不符。显式解码让两侧都对。
                raw = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
                if not raw:
                    continue
                if raw.startswith("event:"):
                    continue
                if raw.startswith("data:"):
                    buf = raw[len("data:"):].strip()
                    if not buf or buf == "ping":
                        continue
                    try:
                        yield cast("dict[str, object]", json.loads(buf))
                    except json.JSONDecodeError:
                        continue

    def analyze(self, query: str, followups: list[str] | None = None,
                max_wait: int = 110) -> dict[str, object]:
        """一站式：newTask -> 收 SSE 流 -> 返回聚合文本与 task_id。"""
        task_id, conn_id = self.new_task(query)
        texts: list[str] = []
        started = time.time()
        done = False
        for ev in self._iter_events(conn_id):
            ev_type = ev.get("event") or ev.get("type")
            data = cast("dict[str, object]", ev.get("data", {}))
            msg = cast("dict[str, object]", data.get("message", {}))
            text = cast("str", msg.get("text", "") or "")
            if text:
                texts.append(text)
            # completion_result 表示任务完成信号
            say = cast("str", msg.get("say") or msg.get("ask") or "")
            if say == "completion_result" or text.strip() == "completion_result":
                done = True
                break
            if time.time() - started > max_wait:
                break
        # 若有追问，再发起一轮（复用同一 task，沿用 conn_id）
        for fq in (followups or []):
            self.new_task(fq, conn_id=conn_id)
            for ev in self._iter_events(conn_id):
                msg = cast("dict[str, object]",
                           cast("dict[str, object]", ev.get("data", {})).get("message", {}))
                t = cast("str", msg.get("text", "") or "")
                if t:
                    texts.append(t)
                if time.time() - started > max_wait:
                    break
        return {
            "task_id": task_id,
            "done": done,
            "result": "\n".join(texts).strip() or "（未收到明确文本结果，请稍后在 InfiniSynapse 控制台查看任务工作区）",
        }


class OpenAICompatAnalyzer:
    """任意 OpenAI 兼容 ``/chat/completions`` 端点（海外可用、也可自建）。

    一个实现接多家：OpenAI、OpenRouter、Groq、DeepSeek、Moonshot，
    以及本地 vLLM / Ollama / LM Studio —— 它们共用同一套请求/响应协议，
    靠 ``base_url`` + ``model`` 区分，不必为每家写适配器。

    非流式：Serverless 环境（Vercel）对长连接不友好，且本项目一次只要一段解读文本。
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini",
                 base_url: str = "https://api.openai.com/v1",
                 prefer_language: str = "en_US"):
        self.api_key: str = api_key
        self.model: str = model
        self.base_url: str = base_url.rstrip("/")
        self.prefer_language: str = prefer_language
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _system_prompt(self) -> str:
        if self.prefer_language.lower().startswith("zh"):
            return ("你是资深统计分析师。只依据用户给出的真实统计数据作答，"
                    "不要编造任何未给出的数字。")
        return ("You are a senior statistical analyst. Answer using only the real "
                "figures the user supplies; never invent numbers that are not given.")

    def analyze(self, query: str, followups: list[str] | None = None,
                max_wait: int = 110) -> dict[str, object]:
        """返回 ``{task_id, done, result}`` —— 与 InfiniSynapse 一致，调用方无需改动。

        ``max_wait`` 仅为签名对齐（非流式调用没有等待上限），实际不生效。
        """
        _ = max_wait
        task_id = str(uuid.uuid4())
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": query},
        ]
        for fq in (followups or []):
            messages.append({"role": "user", "content": fq})

        try:
            r = self._session.post(
                f"{self.base_url}/chat/completions",
                json={"model": self.model, "messages": messages,
                      "temperature": 0.2, "stream": False},
                timeout=_DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise AgentInfiniError(f"OpenAI 兼容端点请求失败: {exc}") from exc
        if r.status_code >= 400:
            raise AgentInfiniError(
                f"OpenAI 兼容端点返回 {r.status_code}: {r.text[:300]}")

        try:
            choices = cast("list[object]", r.json().get("choices") or [])
            first = cast("dict[str, object]", choices[0] if choices else {})
            message = cast("dict[str, object]", first.get("message") or {})
            text = str(message.get("content") or "").strip()
        except (ValueError, IndexError, KeyError, TypeError, AttributeError) as exc:
            raise AgentInfiniError(f"OpenAI 兼容端点返回解析失败: {exc}") from exc
        return {
            "task_id": task_id,
            "done": True,
            "result": text or "（模型未返回文本结果）",
        }


#: ``AI_PROVIDER`` 的合法写法（容忍下划线/连字符写法差异）
_OPENAI_ALIASES = {"openai", "openai_compat", "openai-compatible",
                   "openai_compatible", "compat", "openai-compatible-api"}


def _openai_compat_analyzer(ai_cfg: dict[str, object],
                            lang: str | None) -> OpenAICompatAnalyzer:
    """构造 OpenAI 兼容 provider；**密钥只走环境变量**或 config 的显式字段。"""
    oc = cast("dict[str, object]", ai_cfg.get("openai_compat", {}))
    api_key_obj = (os.environ.get("OPENAI_API_KEY")
                   or os.environ.get("AI_API_KEY")
                   or oc.get("api_key"))
    if not api_key_obj:
        raise AgentInfiniError(
            "AI_PROVIDER=openai_compat 但未配置密钥 "
            "(set env OPENAI_API_KEY, or fill config.yaml ai.openai_compat.api_key)")
    model = str(os.environ.get("OPENAI_MODEL") or oc.get("model") or "gpt-4o-mini")
    base_url = str(os.environ.get("OPENAI_BASE_URL")
                   or oc.get("base_url") or "https://api.openai.com/v1")
    return OpenAICompatAnalyzer(
        api_key=str(api_key_obj), model=model, base_url=base_url,
        prefer_language=_lang_header(lang) if lang else "en_US",
    )


def get_analyzer(lang: str | None = None
                 ) -> InfiniSynapseAnalyzer | OpenAICompatAnalyzer | None:
    """按配置构造分析器；未启用或配置不全时返回 None（调用方回退本地统计）。

    provider 选择：环境变量 ``AI_PROVIDER`` > config.yaml 的 ``ai.provider``
    > 默认 ``infinisynapse``。

    - ``openai_compat``：读 ``OPENAI_API_KEY`` / ``OPENAI_BASE_URL`` /
      ``OPENAI_MODEL``（config 的 ``ai.openai_compat.*`` 为备选）。
    - ``infinisynapse``：读 ``INFINISYNAPSE_API_KEY``（或 config 的
      ``infinisynapse.api_key``），``INFINISYNAPSE_SERVER`` 可覆盖服务地址。

    ``lang`` 决定回复语言（InfiniSynapse 走 ``x-lang``，OpenAI 兼容走 system prompt）。

    注意：密钥**优先用环境变量**——config.yaml 是被 git 跟踪的，勿填真实 key。
    """
    full = _load_cfg()
    ai_cfg = cast("dict[str, object]", full.get("ai", {}))
    provider = str(os.environ.get("AI_PROVIDER")
                   or ai_cfg.get("provider") or "infinisynapse").strip().lower()

    if provider in _OPENAI_ALIASES:
        return _openai_compat_analyzer(ai_cfg, lang)

    cfg = cast("dict[str, object]", full.get("infinisynapse", {}))
    if not cfg.get("enabled"):
        return None
    api_key_obj = (os.environ.get("INFINISYNAPSE_API_KEY")
                   or os.environ.get("QU_STAT_INFINI_KEY")
                   or cfg.get("api_key"))
    if not api_key_obj:
        raise AgentInfiniError(
            "infinisynapse.enabled=true but no api_key configured "
            "(set env INFINISYNAPSE_API_KEY, or fill config.yaml)")
    api_key = str(api_key_obj)
    server = str(os.environ.get("INFINISYNAPSE_SERVER")
                 or cfg.get("server") or "https://app.infinisynapse.cn")
    prefer = _lang_header(lang) if lang else str(cfg.get("prefer_language", "zh_CN"))
    return InfiniSynapseAnalyzer(api_key=api_key, server=server, prefer_language=prefer)
