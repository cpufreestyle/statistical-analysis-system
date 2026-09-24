"""AI provider 可插拔层的派发与解析测试（把此前 _verify_provider.py 的 12 项固化）。

全部离线：``OpenAICompatAnalyzer`` 的 ``analyze()`` 通过 mock 掉 ``_session.post``
返回假响应，不发任何真实网络请求。覆盖：
- ``get_analyzer`` 按 ``AI_PROVIDER`` / 别名 / 未知回落派发；
- 缺失密钥抛 ``AgentInfiniError``；
- config.yaml 缺失（OSError）时优雅返回 None；
- ``OpenAICompatAnalyzer.analyze`` 的成功 / 空 choices 兜底 / 401 / 坏 JSON / 连接错误；
- ``InfiniSynapseAnalyzer._iter_events`` 的 data 行解析 / HTTP 错误，以及**SSE 中文必须按
  UTF-8 解码**（服务端不声明 charset 时 requests 会按 latin-1 搅烂中文）的回归；
- ``_system_prompt`` 按语言切换；
- ``_lang_header`` 取值。
"""
from __future__ import annotations

import pytest
import requests

from src import analyzer
from src.analyzer import (
    AgentInfiniError,
    OpenAICompatAnalyzer,
    InfiniSynapseAnalyzer,
    get_analyzer,
)


_AI_ENV_VARS = [
    "AI_PROVIDER", "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL", "AI_API_KEY",
    "INFINISYNAPSE_API_KEY", "INFINISYNAPSE_SERVER", "QU_STAT_INFINI_KEY",
]


@pytest.fixture(autouse=True)
def _clear_ai_env(monkeypatch):
    """每个用例前清空所有 AI 相关环境变量，避免互相污染。"""
    for k in _AI_ENV_VARS:
        monkeypatch.delenv(k, raising=False)
    yield


# ---------------------------------------------------------------------------
# get_analyzer 派发
# ---------------------------------------------------------------------------
def test_dispatch_openai_compat_by_env(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai_compat")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    az = get_analyzer(lang="en")
    assert isinstance(az, OpenAICompatAnalyzer)
    assert az.api_key == "sk-test"
    assert az.base_url == "https://api.openai.com/v1"


def test_dispatch_openai_alias_compat(monkeypatch):
    # 容忍连字符 / 简写写法
    monkeypatch.setenv("AI_PROVIDER", "compat")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert isinstance(get_analyzer(lang="en"), OpenAICompatAnalyzer)


def test_dispatch_openai_alias_openai_compatible(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert isinstance(get_analyzer(lang="en"), OpenAICompatAnalyzer)


def test_dispatch_infinisynapse_by_env(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "infinisynapse")
    monkeypatch.setenv("INFINISYNAPSE_API_KEY", "sk-x")
    az = get_analyzer(lang="en")
    assert isinstance(az, InfiniSynapseAnalyzer)


def test_dispatch_unknown_provider_falls_back_to_infinisynapse(monkeypatch):
    # 未知 provider 名 -> 回落到 infinisynapse（不报错、不崩溃）
    monkeypatch.setenv("AI_PROVIDER", "totally_unknown")
    monkeypatch.setenv("INFINISYNAPSE_API_KEY", "sk-x")
    assert isinstance(get_analyzer(lang="en"), InfiniSynapseAnalyzer)


def test_openai_compat_missing_key_raises(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai_compat")
    # 没有 OPENAI_API_KEY / AI_API_KEY，config 也没有 -> 抛错
    with pytest.raises(AgentInfiniError):
        get_analyzer(lang="en")


def test_config_missing_returns_none(monkeypatch):
    # config.yaml 读不到（OSError 兜底）-> 视为未配置 -> 返回 None，不抛异常
    monkeypatch.setattr(analyzer, "CONFIG_PATH",
                        analyzer.CONFIG_PATH.parent / "does_not_exist.yaml")
    assert get_analyzer(lang="en") is None


# ---------------------------------------------------------------------------
# OpenAICompatAnalyzer.analyze 解析路径
# ---------------------------------------------------------------------------
class _Resp:
    def __init__(self, status_code=200, payload=None, text="", raises=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self._raises = raises

    def json(self):
        if self._raises:
            raise self._raises
        return self._payload


def _make_analyzer() -> OpenAICompatAnalyzer:
    return OpenAICompatAnalyzer(api_key="sk", model="gpt-4o-mini",
                                base_url="https://example/v1")


def test_analyze_success():
    az = _make_analyzer()
    az._session.post = lambda *a, **k: _Resp(  # noqa: ARG005
        200, {"choices": [{"message": {"content": "Hello world"}}]})
    out = az.analyze("question?")
    assert out["done"] is True
    assert out["result"] == "Hello world"
    # task_id 是合法 uuid
    import uuid
    uuid.UUID(out["task_id"])


def test_analyze_empty_choices_graceful_fallback():
    # 空 choices：与 InfiniSynapse 一致，优雅降级返回兜底文案，不抛异常
    az = _make_analyzer()
    az._session.post = lambda *a, **k: _Resp(200, {"choices": []})  # noqa: ARG005
    out = az.analyze("q")
    assert out["done"] is True
    assert "模型未返回" in out["result"]


def test_analyze_http_error_raises():
    az = _make_analyzer()
    az._session.post = lambda *a, **k: _Resp(401, text="unauthorized")  # noqa: ARG005
    with pytest.raises(AgentInfiniError):
        az.analyze("q")


def test_analyze_bad_json_raises():
    az = _make_analyzer()
    az._session.post = lambda *a, **k: _Resp(  # noqa: ARG005
        200, raises=ValueError("bad json"))
    with pytest.raises(AgentInfiniError):
        az.analyze("q")


def test_analyze_connection_error_raises():
    az = _make_analyzer()
    def _boom(*a, **k):
        raise requests.RequestException("conn refused")
    az._session.post = _boom
    with pytest.raises(AgentInfiniError):
        az.analyze("q")


def test_system_prompt_language():
    zh = OpenAICompatAnalyzer(api_key="sk", prefer_language="zh_CN")
    en = OpenAICompatAnalyzer(api_key="sk", prefer_language="en_US")
    assert "资深统计分析师" in zh._system_prompt()
    assert "senior statistical analyst" in en._system_prompt()


# ---------------------------------------------------------------------------
# InfiniSynapse SSE 行解析
# ---------------------------------------------------------------------------
_SSE_LINES = [
    "event: message.delta",       # 只有 event: 行 → 跳过
    "",                           # 空行 → 跳过
    "data: {\"data\":{\"message\":{\"text\":\"第一段\"}}}",
    "data: ping",                 # 心跳 → 跳过
    "data: not-json",             # 坏 JSON → 跳过而不打断整条流
    "data: {\"data\":{\"message\":{\"text\":\"第二段\"}}}",
]


class _SSEResp:
    """支持 ``with`` 的假 SSE 响应；``iter_lines`` 按给定元素类型原样吐行。"""

    text = ""

    def __init__(self, lines, status_code=200):
        self._lines = lines
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self, **_kw):
        return iter(self._lines)


@pytest.mark.parametrize("element_type", ["str", "bytes"])
def test_iter_events_parses_data_lines_regardless_of_element_type(element_type):
    """`iter_lines` 的元素类型随依赖版本而变（bytes / str），解析必须都成立。

    否则换一台依赖版本不同的机器就会在 `startswith` 上出错（正是 CI 与本地
    结论相反的那次）。
    """
    lines = ([ln.encode("utf-8") for ln in _SSE_LINES] if element_type == "bytes"
             else list(_SSE_LINES))
    az = InfiniSynapseAnalyzer(api_key="k", server="https://example")
    az._session.get = lambda *a, **k: _SSEResp(lines)  # noqa: ARG005
    texts = [ev["data"]["message"]["text"] for ev in az._iter_events("conn-id")]
    assert texts == ["第一段", "第二段"]


def test_iter_events_raises_on_http_error():
    az = InfiniSynapseAnalyzer(api_key="k", server="https://example")
    az._session.get = lambda *a, **k: _SSEResp([], status_code=500)  # noqa: ARG005
    with pytest.raises(AgentInfiniError):
        list(az._iter_events("conn-id"))


class _RequestsLikeSSEResp:
    """按 requests 的真实语义吐 SSE 行，用于固化编码回归。

    requests 在 ``decode_unicode=True`` 时按响应头 charset 解码，缺 charset
    时回落 ISO-8859-1；InfiniSynapse 的 ``text/event-stream`` 并不带 charset，
    中文会被搅成乱码。``decode_unicode=False`` 则原样给字节。
    """

    text = ""

    def __init__(self, raw_lines, status_code=200):
        self._raw_lines = raw_lines
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self, decode_unicode=True, **_kw):
        if decode_unicode:
            return iter([ln.decode("iso-8859-1") for ln in self._raw_lines])
        return iter(self._raw_lines)


_UTF8_SSE_LINES = [
    "event: message.delta",
    "data: {\"data\":{\"message\":{\"text\":\"中文解读不得乱码\",\"say\":\"completion_result\"}}}",
]


def _utf8_bytes(lines):
    """按 UTF-8 编码成 requests 在 ``decode_unicode=False`` 时给出的原始字节。"""
    return [ln.encode("utf-8") for ln in lines]


def test_iter_events_decodes_sse_bytes_as_utf8():
    """中文不得因 charset 缺失而乱码（曾用假云端实测复现 latin-1 搅字）。

    ``decode_unicode=True`` 时假响应故意按 ISO-8859-1 解码，复现线上真实行为；
    被测代码必须去要原始字节自行按 UTF-8 解码，否则断言必然失败。
    """
    az = InfiniSynapseAnalyzer(api_key="k", server="https://example")
    az._session.get = lambda *a, **k: _RequestsLikeSSEResp(  # noqa: ARG005
        _utf8_bytes(_UTF8_SSE_LINES))
    events = list(az._iter_events("conn-id"))
    assert len(events) == 1
    msg = events[0]["data"]["message"]
    assert msg["text"] == "中文解读不得乱码"
    assert msg["say"] == "completion_result"


def test_analyze_end_to_end_utf8_sse_not_garbled():
    """端到端：newTask + SSE 流聚合出的解读文本必须是原文，不是 latin-1 残片。"""
    az = InfiniSynapseAnalyzer(api_key="k", server="https://example")
    az._session.post = lambda *a, **k: _Resp(200, {})  # noqa: ARG005
    az._session.get = lambda *a, **k: _RequestsLikeSSEResp(  # noqa: ARG005
        _utf8_bytes(_UTF8_SSE_LINES))
    out = az.analyze("本季度统计公报")
    assert out["done"] is True
    assert out["result"] == "中文解读不得乱码"
    assert out["console_url"]


# ---------------------------------------------------------------------------
# _lang_header
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("zh-CN", "zh_CN"),
    ("zh_CN", "zh_CN"),
    ("en_US", "en_US"),
    (None, "zh_CN"),
    ("ja-JP", "ja-JP"),   # 未知语言原样透传（不臆造），仅 falsy 时回落 zh_CN
])
def test_lang_header(raw, expected):
    assert analyzer._lang_header(raw) == expected
