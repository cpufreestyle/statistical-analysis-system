"""知识库引擎：语义召回契约 + 检索行为。

为什么值得单独测
--------------
``search_knowledge`` 是 ``/api/ask``、统计公报与 ``/api/knowledge`` 的共同上游，
也是「AI 不得编造数字」链条上的第一环——召回不到口径，云端解读就只能凭问题文字猜。
改成中英概念映射前，它在 35 条真实提问上 **17 条完全召回不到**、top-1 只有 18/35，
而这些行为此前一条测试都没有。
"""
from __future__ import annotations

import pytest

from src import knowledge as kb


@pytest.fixture()
def seeded_kb():
    """灌入中英种子知识；测试结束后把 knowledge 表还原成原样。

    还原是必须的：本文件按字母序排在 ``test_web`` 之前，加行不清理会改变
    后续测试看到的 ``knowledge_rows``。
    """
    from src.db import KNOWLEDGE, engine, init_db

    init_db()
    kb.seed_default_knowledge()
    before = kb.list_knowledge()
    yield kb
    with engine.begin() as conn:
        conn.execute(KNOWLEDGE.delete())
        for row in before:
            conn.execute(KNOWLEDGE.insert().values(**row))


def _titles(rows) -> list[str]:
    return [r["title"] for r in rows]


# ---------------------------------------------------------------------------
# 跨语言召回 —— 本次改动的核心
# ---------------------------------------------------------------------------
#: (查询, 期望命中的条目标题片段)。改写前这 11 例全部落空：``_extract_grams``
#: 只做字面匹配，``retail`` 与「社会消费品零售总额」之间没有任何共同字符。
CROSS_CASES = [
    ("retail", "社会消费品零售总额定义"),
    ("fixed asset", "固定资产投资统计口径"),
    ("per capita", "常住人口与人均可支配收入"),
    ("population", "常住人口与人均可支配收入"),
    ("disposable income", "常住人口与人均可支配收入"),
    ("industry value added", "规模以上工业统计范围"),
    ("汇率", "Cross-economy"),
    ("同比", "YoY"),
    ("排名", "Cross-economy"),
    ("数据来源", "World Bank"),
    ("修订", "China NBS"),
]


@pytest.mark.parametrize(("query", "want"), CROSS_CASES)
def test_cross_lingual_recall(seeded_kb, query, want):
    """英文提问必须召回中文条目，中文提问必须召回英文条目。"""
    rows = kb.search_knowledge(query, limit=10)
    assert any(want in t for t in _titles(rows)), (query, _titles(rows))


#: (查询, 期望排第一的条目标题)。测的是排序而不只是召回。
TOP1_CASES = [
    ("GDP", "地区生产总值(GDP)口径"),
    ("GDP 是什么意思", "地区生产总值(GDP)口径"),
    ("社零", "社会消费品零售总额定义"),
    ("固定资产", "固定资产投资统计口径"),
    ("人均", "常住人口与人均可支配收入"),
    ("工业增加值", "规模以上工业统计范围"),
    ("经济增长率怎么算", "YoY vs. contribution share"),
    ("贡献率", "YoY vs. contribution share"),
    ("ranking", "Cross-economy comparison caveats"),
    ("data source", "World Bank Open Data (Asia-Pacific aggregates)"),
    ("revised", "China NBS and Customs data caliber"),
]


@pytest.mark.parametrize(("query", "want"), TOP1_CASES)
def test_top1_is_the_entry_about_it(seeded_kb, query, want):
    """标题即命中的条目要排在「正文顺带一提」的条目前面。"""
    rows = kb.search_knowledge(query, limit=10)
    assert rows, query
    assert rows[0]["title"] == want, (query, _titles(rows))


def test_member_density_beats_an_incidental_mention(seeded_kb):
    """命中多个成员的条目应压过只中一个两字成员的条目。

    「主营业务收入」里的「收入」曾让「规模以上工业」抢到 ``disposable income``
    的首位——所以同一概念命中越多成员，加分越高。
    """
    rows = kb.search_knowledge("disposable income", limit=5)
    assert rows[0]["title"] == "常住人口与人均可支配收入", _titles(rows)


def test_source_field_participates_in_matching(seeded_kb):
    """出处是强相关信号：早先 ``search_knowledge`` 根本没把它拼进待匹配文本。"""
    kb.add_knowledge(title="Zzz 独有条目", category="测试", tags="",
                     content="这一段里没有任何可匹配的词汇。", source="世界银行")
    rows = kb.search_knowledge("数据来源", limit=20)
    assert "Zzz 独有条目" in _titles(rows), _titles(rows)


def test_concept_table_excludes_meta_words(seeded_kb):
    """「口径 / 定义」这类元词不能进概念表——否则所有条目一起加分，排序失效。"""
    for concept in kb._CONCEPTS:
        assert "口径" not in concept
        assert "定义" not in concept


# ---------------------------------------------------------------------------
# 既有契约不能被改坏
# ---------------------------------------------------------------------------
def test_lang_filter_still_restricts_the_corpus(seeded_kb):
    """概念映射只改「同一语料库里谁更相关」，不改「给谁看」的语种过滤。"""
    en = kb.search_knowledge("GDP", lang="en", limit=20)
    assert en and all("lang:en" in r["tags"].lower() for r in en)
    zh = kb.search_knowledge("GDP", lang="zh", limit=20)
    assert zh and all("lang:en" not in r["tags"].lower() for r in zh)


def test_lang_open_lets_a_query_cross_the_language_boundary(seeded_kb):
    """``lang`` 缺省（``/api/knowledge`` 的用法）时才跨语言。"""
    rows = kb.search_knowledge("retail", limit=20)
    assert "社会消费品零售总额定义" in _titles(rows)


def test_empty_and_garbage_queries_are_safe(seeded_kb):
    for q in ["", "   ", "!!!", "龘龘龘"]:
        assert kb.search_knowledge(q) == []


def test_limit_is_respected(seeded_kb):
    assert len(kb.search_knowledge("GDP", limit=1)) == 1


def test_writes_are_immediately_visible(seeded_kb):
    """不做结果缓存——增删必须立刻反映在检索结果里。"""
    kb.add_knowledge(title="独有测试条目xyz", category="测试", tags="",
                     content="独有测试内容xyz", source="")
    assert "独有测试条目xyz" in _titles(kb.search_knowledge("独有测试条目xyz"))
    kid = next(r["id"] for r in kb.list_knowledge()
               if r["title"] == "独有测试条目xyz")
    assert kb.delete_knowledge(kid) is True
    assert "独有测试条目xyz" not in _titles(kb.search_knowledge("独有测试条目xyz"))


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------
def test_concept_ids_match_across_languages_and_compact_form():
    """多词成员要能在被拆开 / 多空格隔开时仍然命中（紧凑形态比对）。"""
    assert 0 in kb._concept_ids("GDP")
    assert "gross domestic product" in [m.lower() for m in kb._CONCEPTS[0]]
    assert kb._concept_ids("gross domestic\nproduct") != set()
    assert kb._concept_ids("汇率") != set()


def test_extract_grams_keeps_chinese_bigrams_and_english_words():
    grams = kb._extract_grams("GDP 增长率 2024")
    assert {"GDP", "2024", "增长", "长率"} <= set(grams)


# ---------------------------------------------------------------------------
# retrieve_context —— 喂给云端 AI 的那一层
# ---------------------------------------------------------------------------
def test_retrieve_context_renders_head_source_and_content(seeded_kb):
    ctx = kb.retrieve_context("GDP 是什么", limit=2)
    assert "地区生产总值(GDP)口径" in ctx
    assert "来源：" in ctx
    assert "\n\n" in ctx


def test_retrieve_context_is_empty_when_nothing_matches(seeded_kb):
    assert kb.retrieve_context("龘龘龘") == ""
