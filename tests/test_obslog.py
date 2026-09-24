"""可观测性三条腿：``/healthz`` 探活、慢查询告警、慢请求告警。

共同取向是**观测代码不得影响主流程**：探针永不 500、永不触发播种；告警阈值可被
环境变量整体关闭；监听器里出任何问题都不该把业务请求带下去。测试因此两头都钉——
「该报的时候真的报」，以及「不该报的时候别报」。
"""
from __future__ import annotations

import logging

import pytest

#: ``/healthz`` 的字段集合。抽成常量是为了让下面几条测试共用同一份预期，
#: 改字段时只改一处，而不是让某条测试悄悄少断言一个键。
HEALTHZ_FIELDS = {
    "status", "version", "db_ok", "seeded",
    "kv_configured", "indicator_rows", "knowledge_rows", "uptime_s",
}


@pytest.fixture()
def empty_db():
    """构造「库在、但一行数据都没有」的降级态；用完把数据补回来。

    ``yield`` 之后重新播种是必须的：本文件按字母序排在 ``test_stats_core`` 与
    ``test_web`` 之前，清空不还原会让后面依赖 seeded fixture 的测试拿到空表。
    """
    from src import knowledge as kb
    from src.db import INDICATORS, KNOWLEDGE, count_indicators, engine, init_db
    from src.loader import load_seed_data

    init_db()
    had_rows = count_indicators() > 0
    with engine.begin() as conn:
        conn.execute(INDICATORS.delete())
        conn.execute(KNOWLEDGE.delete())
    yield
    if had_rows:
        load_seed_data()
        kb.seed_default_knowledge()


@pytest.fixture()
def no_seed(monkeypatch):
    """把播种打成炸弹——探活端点一旦触发播种，测试立刻炸。"""
    import src.loader as loader

    def boom(*args, **kwargs):
        raise AssertionError("/healthz 不得触发播种")

    monkeypatch.setattr(loader, "load_seed_data", boom)
    return boom


# ---------------------------------------------------------------------------
# /healthz —— 探活端点
# ---------------------------------------------------------------------------
def test_healthz_is_always_200_and_json(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"


def test_healthz_field_set_is_flat_and_stable(client):
    """字段集合恒定且全是标量——监控端才能不判「这个键这次有没有」地直接取值。"""
    payload = client.get("/healthz").get_json()
    assert set(payload) == HEALTHZ_FIELDS
    assert all(isinstance(v, (bool, int, str)) for v in payload.values())
    assert payload["version"] != "unknown"


def test_healthz_reports_ok_when_seeded(seeded_client):
    payload = seeded_client.get("/healthz").get_json()
    assert payload["status"] == "ok"
    assert payload["db_ok"] is True
    assert payload["seeded"] is True
    assert payload["indicator_rows"] > 0


def test_healthz_reports_degraded_when_empty(client, empty_db, no_seed):
    """没数据 → degraded，但仍然是 200：探针的职责是「活着吗」，不是「数据全吗」。"""
    payload = client.get("/healthz").get_json()
    assert payload["status"] == "degraded"
    assert payload["db_ok"] is True          # 库可达，只是空
    assert payload["seeded"] is False
    assert payload["indicator_rows"] == 0    # 键仍在，值为 0


def test_healthz_needs_no_auth_in_production(monkeypatch, seeded_client):
    """线上也得放行——平台存活探针不会带 ``X-Admin-Token``。"""
    from src import web

    monkeypatch.setattr(web, "_IS_SERVERLESS", True)
    monkeypatch.setattr(web, "_ADMIN_TOKEN", "secret-token")
    assert seeded_client.get("/healthz").status_code == 200


def test_healthz_is_documented_as_a_public_ops_endpoint(client):
    """/docs 与实现互为镜像（约定 8）：新端点必须登记，且不能漏了分组。"""
    from src import api_docs

    entry = next(e for e in api_docs.ENDPOINTS if str(e["path"]) == "/healthz")
    assert entry["auth"] is False
    assert entry["group"] == "ops"
    assert "ops" in api_docs.GROUPS


# ---------------------------------------------------------------------------
# 慢查询告警
# ---------------------------------------------------------------------------
def _db_logs(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "src.db"]


def test_slow_query_is_logged(client, caplog, monkeypatch):
    from src import db

    monkeypatch.setattr(db, "SLOW_QUERY_MS", 0.001)      # 1 微秒，必然越过阈值
    with caplog.at_level(logging.WARNING, logger="src.db"):
        db.query_indicators()
    assert any(m.startswith("slow query") for m in _db_logs(caplog)), caplog.text


def test_slow_query_message_is_one_truncated_line(client, caplog, monkeypatch):
    """语句压成单行并截断——一行一条才方便 grep 与日志聚合。"""
    from src import db

    monkeypatch.setattr(db, "SLOW_QUERY_MS", 0.001)
    with caplog.at_level(logging.WARNING, logger="src.db"):
        db.count_indicators()
    message = next(m for m in _db_logs(caplog) if m.startswith("slow query"))
    assert "\n" not in message
    assert len(message) < 260


def test_slow_query_silent_when_under_threshold(client, caplog, monkeypatch):
    from src import db

    monkeypatch.setattr(db, "SLOW_QUERY_MS", 600_000.0)  # 10 分钟
    with caplog.at_level(logging.WARNING, logger="src.db"):
        db.query_indicators()
    assert not _db_logs(caplog)


def test_slow_query_disabled_at_zero(client, caplog, monkeypatch):
    """``<=0`` 是「关闭」而不是「全都算慢」——否则想关告警时反而被刷屏。"""
    from src import db

    monkeypatch.setattr(db, "SLOW_QUERY_MS", 0.0)
    with caplog.at_level(logging.WARNING, logger="src.db"):
        db.query_indicators()
    assert not _db_logs(caplog)


def test_failed_query_does_not_leak_start_timestamps():
    """失败语句也要出栈，否则长连接上的时间栈会无限增长。"""
    from sqlalchemy import text

    from src.db import engine

    with engine.connect() as conn:
        with pytest.raises(Exception):
            conn.execute(text("SELECT * FROM no_such_table"))
        assert conn.info.get("qu_stat_query_started", []) == []


# ---------------------------------------------------------------------------
# 慢请求告警
# ---------------------------------------------------------------------------
def _web_logs(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "src.web"]


def test_slow_request_is_logged_with_flat_fields(client, caplog, monkeypatch):
    from src import web

    monkeypatch.setattr(web, "SLOW_REQUEST_MS", 0.001)
    with caplog.at_level(logging.WARNING, logger="src.web"):
        client.get("/api/stats")
    messages = [m for m in _web_logs(caplog) if m.startswith("slow request")]
    assert messages, caplog.text
    for field in ("method=GET", "path=/api/stats", "status=200", "ms="):
        assert field in messages[0]


def test_slow_request_silent_when_fast(client, caplog, monkeypatch):
    from src import web

    monkeypatch.setattr(web, "SLOW_REQUEST_MS", 600_000.0)
    with caplog.at_level(logging.WARNING, logger="src.web"):
        client.get("/api/stats")
    assert not [m for m in _web_logs(caplog) if m.startswith("slow request")]


def test_slow_request_hook_does_not_break_plain_responses(client, monkeypatch):
    """钩子挂了也不能影响响应本身——这是「观测不得影响主流程」的底线。"""
    from src import web

    monkeypatch.setattr(web, "SLOW_REQUEST_MS", 0.001)
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    assert resp.get_json()["indicator_rows"] >= 0

