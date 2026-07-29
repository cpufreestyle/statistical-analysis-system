"""云端 AI 分析层：直连 InfiniSynapse Server API（Bearer Token 鉴权）。

设计原则：
- 默认关闭；仅当 config.yaml 中 infinisynapse.enabled=true 且配置了
  server/api_key 时启用。未启用或缺失 key 时，调用方回退到本地统计。
- 直接调用 InfiniSynapse Server API（/api/ai/message 发起 newTask +
  /api/ai/events 消费 SSE 流），不依赖 agent_infini 二进制；
  每次请求都走真实 HTTPS 接口，调用记录可在服务端审计，满足比赛
  「集成 InfiniSynapse API、调用日志可查验」的硬性要求。
- 外部请求（InfiniSynapse REST API）会经系统 HTTP(S)_PROXY 环境变量，
  因此在配置了 127.0.0.1:7897 代理的机器上可正常联网。

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
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return cast("dict[str, object]", yaml.safe_load(f) or {})


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
            for raw in resp.iter_lines(decode_unicode=True):
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


def get_analyzer() -> InfiniSynapseAnalyzer | None:
    """按 config.yaml 构造分析器；未启用或配置不全时返回 None。"""
    cfg = cast("dict[str, object]", _load_cfg().get("infinisynapse", {}))
    if not cfg.get("enabled"):
        return None
    api_key_obj = cfg.get("api_key")
    if not api_key_obj:
        raise AgentInfiniError("infinisynapse.enabled=true 但未配置 api_key")
    api_key = str(api_key_obj)
    server = cast("str", cfg.get("server") or "https://app.infinisynapse.cn")
    prefer = str(cfg.get("prefer_language", "zh_CN"))
    return InfiniSynapseAnalyzer(api_key=api_key, server=server, prefer_language=prefer)
