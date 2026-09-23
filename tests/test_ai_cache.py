"""AI 解读缓存（``src/ai_cache.py``）与两处接线（``/api/ask``、统计公报）的契约测试。

为什么单独测
------------
这个缓存的**正确性边界只有一条**：数据变了就不能再命中。命中键一旦漏掉事实文件的
内容，就会把旧数据的解读配给新数据——页面看不出任何异常，只会静静地给出错误解读，
正好踩中项目「AI 不得编造数字」的底线。所以「键随数据变化」被放在第一条。

其余覆盖失效策略（失败不缓存 / 无文本不缓存 / TTL / LRU）、可关闭性，
以及 L2（Redis）挂掉时只降级不炸主链路——Serverless 上 Redis 抖动是常态。
"""
from __future__ import annotations

import pytest

from src import ai_cache, kv_store


#: 真实形状的事实文件：name + JSON 文本内容（内容才是数字的载体）
FACTS = [{"name": "facts.json", "content": '{"year": 2024, "gdp": 18.7}'}]


class _FakeAnalyzer:
    """记录调用次数的假分析器：缓存一旦失效，调用数就会暴露。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def analyze(self, query: str, followups: list[str] | None = None,
                max_wait: int | None = None,
                files: list[dict[str, object]] | None = None,
                images: list[dict[str, object]] | None = None
                ) -> dict[str, object]:
        self.calls.append(query)
        return {"task_id": f"t-{len(self.calls)}", "done": True,
                "result": f"answer {len(self.calls)}"}


class _FlakyAnalyzer(_FakeAnalyzer):
    """前两次抛错、第三次才成功的假分析器（模拟云端抖动）。"""

    def analyze(self, query: str, followups: list[str] | None = None,
                max_wait: int | None = None,
                files: list[dict[str, object]] | None = None,
                images: list[dict[str, object]] | None = None
                ) -> dict[str, object]:
        self.calls.append(query)
        if len(self.calls) <= 2:
            raise RuntimeError("cloud is down")
        return {"task_id": "t-3", "done": True, "result": "finally"}


class _SilentAnalyzer(_FakeAnalyzer):
    """返回空文本的假分析器：测「没有可缓存内容」这一支。"""

    def analyze(self, query: str, followups: list[str] | None = None,
                max_wait: int | None = None,
                files: list[dict[str, object]] | None = None,
                images: list[dict[str, object]] | None = None
                ) -> dict[str, object]:
        self.calls.append(query)
        return {"task_id": "t", "done": True, "result": "   "}


@pytest.fixture(autouse=True)
def _clean_cache():
    """每条测试都从空缓存起步——模块级状态，不清会跨测试串味。"""
    ai_cache.reset_cache()
    yield
    ai_cache.reset_cache()


# ---------------------------------------------------------------------------
# 缓存键：数据一变就必须换键（正确性生死线）
# ---------------------------------------------------------------------------
def test_key_is_stable_for_identical_inputs():
    first = ai_cache.cache_key("2024 GDP", FACTS, "zh", "InfiniSynapseAnalyzer")
    second = ai_cache.cache_key("2024 GDP", FACTS, "zh", "InfiniSynapseAnalyzer")
    assert first == second


def test_key_changes_when_the_facts_change():
    """同一句话、底层数字变了 -> 必须换键，否则旧解读会被派给新数据。"""
    base = ai_cache.cache_key("2024 GDP", FACTS, "zh", "M")
    changed = ai_cache.cache_key(
        "2024 GDP",
        [{"name": "facts.json", "content": '{"year": 2024, "gdp": 19.1}'}],
        "zh", "M")
    assert base != changed


def test_key_covers_question_lang_model_and_file_name():
    base = ai_cache.cache_key("q", FACTS, "zh", "M")
    assert base != ai_cache.cache_key("q2", FACTS, "zh", "M")
    assert base != ai_cache.cache_key("q", FACTS, "en", "M")
    assert base != ai_cache.cache_key("q", FACTS, "zh", "OtherModel")
    renamed = ai_cache.cache_key("q", [{"name": "other.json", "content": "1"}],
                                 "zh", "M")
    assert base != renamed
    assert base != ai_cache.cache_key("q", None, "zh", "M")


# ---------------------------------------------------------------------------
# analyze_cached：命中不打云端
# ---------------------------------------------------------------------------
def test_repeat_question_is_served_without_calling_the_analyzer():
    az = _FakeAnalyzer()
    first, cached_first = ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    second, cached_second = ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")

    assert len(az.calls) == 1, "第二次必须命中缓存，不能再打一次云端"
    assert cached_first is False and cached_second is True
    assert first["result"] == second["result"] == "answer 1"
    assert "from_cache" not in first
    assert second["from_cache"] is True
    assert second["task_id"] == "t-1", "命中的仍是当初那次真实调用的 task_id"


def test_changed_facts_force_a_fresh_call():
    az = _FakeAnalyzer()
    ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    out, cached = ai_cache.analyze_cached(
        az, "q", files=[{"name": "facts.json", "content": "changed"}], lang="zh")
    assert cached is False
    assert len(az.calls) == 2
    assert out["result"] == "answer 2"


def test_failed_call_is_not_cached():
    """云端抖动不能被粘住：失败一律不写缓存。"""
    az = _FlakyAnalyzer()
    for _ in range(2):
        with pytest.raises(RuntimeError):
            ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    out, cached = ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    assert cached is False
    assert out["result"] == "finally"
    assert len(az.calls) == 3


def test_result_without_text_is_not_cached():
    az = _SilentAnalyzer()
    ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    _, cached = ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    assert cached is False
    assert len(az.calls) == 2


def test_cache_hit_returns_a_copy_every_time():
    az = _FakeAnalyzer()
    stored, _ = ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    hit_a, _ = ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    hit_b, _ = ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    assert hit_a is not stored and hit_b is not stored
    assert hit_a is not hit_b, "每次命中返回副本，调用方改写不会污染缓存"
    assert "from_cache" not in stored


# ---------------------------------------------------------------------------
# 开关 / 过期 / 淘汰 / 降级
# ---------------------------------------------------------------------------
def test_cache_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("QU_STAT_AI_CACHE", "0")
    az = _FakeAnalyzer()
    ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    _, cached = ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    assert cached is False
    assert len(az.calls) == 2
    assert ai_cache.cache_stats()["enabled"] is False


def test_unparseable_toggle_falls_back_to_enabled(monkeypatch):
    """环境变量写错时保持默认（开启），而不是静默把缓存关掉。"""
    monkeypatch.setenv("QU_STAT_AI_CACHE", "maybe")
    assert ai_cache.enabled() is True


def test_entries_expire_after_ttl(monkeypatch):
    monkeypatch.setattr(ai_cache, "ttl_seconds", lambda: 0)
    az = _FakeAnalyzer()
    ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    _, cached = ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    assert cached is False
    assert len(az.calls) == 2


def test_lru_evicts_the_oldest_entry(monkeypatch):
    monkeypatch.setenv("QU_STAT_AI_CACHE_MAX", "2")
    az = _FakeAnalyzer()
    for i in range(3):
        ai_cache.analyze_cached(az, f"q{i}", files=FACTS, lang="zh")
    assert ai_cache.cache_stats()["l1_size"] == 2
    ai_cache.analyze_cached(az, "q0", files=FACTS, lang="zh")
    assert len(az.calls) == 4, "q0 已被淘汰，必须重新真调"
    _, cached = ai_cache.analyze_cached(az, "q2", files=FACTS, lang="zh")
    assert cached is True
    assert len(az.calls) == 4


def test_kv_failure_only_degrades(monkeypatch):
    """Redis 抖动不能影响主链路：L1 照常接住，指标里留下 kv_errors。"""
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("redis is down")

    monkeypatch.setattr(kv_store, "kv_available", lambda: True)
    monkeypatch.setattr(kv_store, "kv_get_json", boom)
    monkeypatch.setattr(kv_store, "kv_set_json", boom)
    az = _FakeAnalyzer()
    ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    _, cached = ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    assert cached is True
    assert len(az.calls) == 1
    assert ai_cache.cache_stats()["kv_errors"] >= 2


def test_kv_round_trip_is_usable(monkeypatch):
    """L2 命中后要回填 L1，之后的请求连 Redis 都不用问。"""
    store: dict[str, object] = {}
    monkeypatch.setattr(kv_store, "kv_available", lambda: True)
    monkeypatch.setattr(kv_store, "kv_set_json",
                        lambda key, value: bool(store.__setitem__(key, value)))
    monkeypatch.setattr(kv_store, "kv_get_json", lambda key: store.get(key))
    az = _FakeAnalyzer()
    ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    ai_cache.reset_cache()   # 抹掉 L1，只剩 L2
    _, cached = ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    assert cached is True
    assert len(az.calls) == 1
    stats = ai_cache.cache_stats()
    assert stats["kv_hits"] == 1
    assert stats["l1_size"] == 1, "L2 命中应回填 L1"


def test_stale_kv_payload_is_ignored(monkeypatch):
    """Redis 里已过期的条目不命中（自己带 _expires_at，不依赖 Redis TTL）。"""
    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("过期条目应被本地判定拦掉，不该去问 Redis")

    monkeypatch.setattr(kv_store, "kv_available", lambda: True)
    monkeypatch.setattr(kv_store, "kv_get_json", boom)
    az = _FakeAnalyzer()
    out, cached = ai_cache.analyze_cached(az, "q", files=FACTS, lang="zh")
    assert cached is False
    assert out["result"] == "answer 1"


def test_cache_stats_shape():
    stats = ai_cache.cache_stats()
    assert {"hits", "misses", "kv_hits", "kv_errors", "writes",
            "enabled", "ttl_seconds", "l1_size", "l1_max", "kv"} <= set(stats)


# ---------------------------------------------------------------------------
# 接线：/api/ask 与统计公报
# ---------------------------------------------------------------------------
def test_api_ask_serves_repeat_questions_from_cache(monkeypatch, seeded_client):
    from src import analyzer

    az = _FakeAnalyzer()
    monkeypatch.setattr(analyzer, "get_analyzer", lambda lang=None: az)
    url = "/api/ask?text=2024 GDP&cloud=1&lang=zh"
    first = seeded_client.get(url).get_json()
    second = seeded_client.get(url).get_json()

    assert len(az.calls) == 1, "同一个问题只应打一次云端"
    assert first["AI 解读"] == second["AI 解读"] == "answer 1"
    assert "cached" not in first
    assert second["cached"] is True


def test_api_ask_cache_flag_survives_english_localization(monkeypatch,
                                                         seeded_client):
    """lang=en 会重命名结构键，新增的 cached 标记必须原样穿过去。"""
    from src import analyzer

    monkeypatch.setattr(analyzer, "get_analyzer", lambda lang=None: _FakeAnalyzer())
    url = "/api/ask?text=2024 GDP&cloud=1&lang=en"
    seeded_client.get(url).get_json()
    second = seeded_client.get(url).get_json()
    assert second["cached"] is True
    assert second["ai_interpretation"] == "answer 1"


def test_local_only_ask_never_builds_an_analyzer(monkeypatch, seeded_client):
    """不勾「AI 云端解读」时不构造分析器，缓存也就无从介入。"""
    from src import analyzer

    def _fail(lang: str | None = None) -> None:
        pytest.fail("本地统计不应调用云端")

    monkeypatch.setattr(analyzer, "get_analyzer", _fail)
    payload = seeded_client.get("/api/ask?text=2024 GDP&lang=zh").get_json()
    assert "AI 解读" not in payload
    assert "cached" not in payload


def test_report_marks_a_cached_interpretation(monkeypatch, seeded_client):
    from src import analyzer

    az = _FakeAnalyzer()
    monkeypatch.setattr(analyzer, "get_analyzer", lambda lang=None: az)
    url = ("/api/report?format=json&year=2024&dimension="
           "%E4%B8%AD%E5%9B%BD&lang=zh&cloud=1")
    first = seeded_client.get(url).get_json()
    second = seeded_client.get(url).get_json()
    assert len(az.calls) == 1
    assert first["ai_cached"] is False
    assert second["ai_cached"] is True
    assert first["ai"] == second["ai"] == "answer 1"
