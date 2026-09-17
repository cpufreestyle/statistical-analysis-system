"""i18n 标签层契约测试（纯数据、离线、无网络）。

覆盖 src.labels 的关键路径：语言归一化、单词条 label/slug/term、入参反向解析
key_of（含未登记兜底）、整行 localize_indicator 的 *_key/_slug 并列、来源说明
localize_note（世界银行 + 国家统计局两种形态）、以及 /api/ask 载荷的
localize_payload 结构键重命名。

词条取自 data/labels.csv（被跟踪，CI 可用）。未登记键一律原样返回、绝不抛异常
——这是「向前兼容」的硬约定，单独测了。
"""
from __future__ import annotations

import pytest

from src import labels


# ---------------------------------------------------------------------------
# 语言解析
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("zh-CN", "zh"),
    ("zh_CN", "zh"),
    ("zh", "zh"),
    ("en", "en"),
    ("en_US", "en"),
    ("en-US", "en"),
    ("fr", "en"),       # 无法识别 -> 默认 en
    (None, "en"),
    ("", "en"),
])
def test_normalize_lang(raw, expected):
    assert labels.normalize_lang(raw) == expected


@pytest.mark.parametrize("header,expected", [
    ("zh-CN,zh;q=0.9", "zh"),
    ("zh,en;q=0.8", "zh"),
    ("en-US,en;q=0.9", "en"),
    ("en-GB,en;q=0.9", "en"),
    (None, None),
    ("fr-FR,fr;q=0.9", None),
])
def test_lang_from_accept_language(header, expected):
    assert labels.lang_from_accept_language(header) == expected


# ---------------------------------------------------------------------------
# 单词条
# ---------------------------------------------------------------------------
def test_label_zh_returns_canonical_key():
    # lang=zh 永远给中文规范键（key 即展示值）
    assert labels.label("dimension", "中国", "zh") == "中国"
    assert labels.label("indicator", "GDP增长率", "zh") == "GDP增长率"


def test_label_en_localizes():
    assert labels.label("dimension", "中国", "en") == "China"
    assert labels.label("indicator", "GDP增长率", "en") == "GDP Growth"
    assert labels.label("category", "综合", "en") == "National Accounts"


def test_label_unregistered_passthrough():
    # 未登记键原样返回，绝不抛异常（向前兼容）
    assert labels.label("dimension", "火星殖民区", "en") == "火星殖民区"
    assert labels.label("indicator", "尚未定义指标", "en") == "尚未定义指标"


def test_slug_registered_and_fallback():
    assert labels.slug("dimension", "中国") == "china"
    assert labels.slug("indicator", "GDP增长率") == "gdp_growth"
    assert labels.slug("indicator", "社会消费品零售总额") == "retail_sales_consumer_goods"
    # 未登记且含非 ASCII -> 兜底层直接原样返回（不猜测）
    assert labels.slug("dimension", "火星殖民区") == "火星殖民区"


def test_term_triple():
    t = labels.term("indicator", "GDP增长率", "en")
    assert t == {"label": "GDP Growth", "key": "GDP增长率", "slug": "gdp_growth"}


# ---------------------------------------------------------------------------
# 入参反向解析（英文标签 / slug 与中文规范键等价）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("kind,value,expected", [
    ("dimension", "China", "中国"),
    ("dimension", "china", "中国"),
    ("dimension", "中国", "中国"),
    ("indicator", "GDP Growth", "GDP增长率"),
    ("indicator", "gdp_growth", "GDP增长率"),
])
def test_key_of_equivalence(kind, value, expected):
    assert labels.key_of(kind, value) == expected


def test_key_of_unknown_passthrough_not_guessed():
    # 未知维度原样透传，不静默换成默认值（硬约定）
    assert labels.key_of("dimension", "亚特兰蒂斯") == "亚特兰蒂斯"


# ---------------------------------------------------------------------------
# 整行本地化：展示值 + *_key + *_slug 并列
# ---------------------------------------------------------------------------
def test_localize_indicator_parallel_keys_en():
    row = {
        "year": 2024, "category": "综合", "indicator": "GDP增长率",
        "dimension": "中国", "value": 5.0, "unit": "%",
        "note": "来源：世界银行OpenData(NY.GDP.MKTP.KD.ZG)",
    }
    out = labels.localize_indicator(row, "en")
    assert out["category"] == "National Accounts"
    assert out["indicator"] == "GDP Growth"
    assert out["dimension"] == "China"
    # 规范键原样保留（跨语言稳定连接键）
    assert out["indicator_key"] == "GDP增长率"
    assert out["dimension_key"] == "中国"
    # ASCII 稳定键供程序消费
    assert out["indicator_slug"] == "gdp_growth"
    assert out["dimension_slug"] == "china"
    # 原始非展示字段不丢
    assert out["year"] == 2024 and out["value"] == 5.0


def test_localize_indicator_zh_keeps_canonical():
    row = {
        "year": 2024, "category": "综合", "indicator": "GDP增长率",
        "dimension": "中国", "value": 5.0, "unit": "%", "note": "",
    }
    out = labels.localize_indicator(row, "zh")
    assert out["indicator"] == "GDP增长率"
    assert out["indicator_key"] == "GDP增长率"
    assert out["indicator_slug"] == "gdp_growth"


def test_localize_indicators_list():
    rows = [
        {"year": 2024, "category": "综合", "indicator": "GDP增长率",
         "dimension": "中国", "value": 5.0, "unit": "%", "note": ""},
        {"year": 2024, "category": "贸易", "indicator": "货物服务出口总额",
         "dimension": "中国", "value": 1.0, "unit": "亿美元", "note": ""},
    ]
    out = labels.localize_indicators(rows, "en")
    assert [r["indicator"] for r in out] == ["GDP Growth", "Exports of Goods & Services"]
    assert all(r["indicator_key"] for r in out)


# ---------------------------------------------------------------------------
# 来源说明 localize_note
# ---------------------------------------------------------------------------
def test_localize_note_world_bank():
    note = "来源：世界银行OpenData(NY.GDP.MKTP.KD.ZG)"
    out = labels.localize_note(note, "en")
    assert out == "Source: World Bank Open Data (NY.GDP.MKTP.KD.ZG)"


def test_localize_note_nbs_translated():
    note = "来源：国家统计局2024年国民经济运行情况"
    out = labels.localize_note(note, "en")
    # 关键中文词条被翻译，且不再残留「国家统计局」
    assert "China NBS" in out
    assert "National Economic Performance" in out
    assert "国家统计局" not in out


def test_localize_note_zh_passthrough():
    note = "来源：世界银行OpenData(NY.GDP.MKTP.KD.ZG)"
    assert labels.localize_note(note, "zh") == note


# ---------------------------------------------------------------------------
# UI 状载荷（/api/ask）结构键重命名
# ---------------------------------------------------------------------------
def test_localize_payload_renames_keys_en():
    payload = {
        "年份": 2024,
        "维度": "中国",
        "matched_indicators": [{"指标": "GDP增长率", "数值": 5.0}],
    }
    out = labels.localize_payload(payload, "en")
    assert "year" in out and out["year"] == 2024
    assert out["dimension"] == "China"
    assert out["matched_indicators"][0]["indicator"] == "GDP Growth"
    assert out["matched_indicators"][0]["value"] == 5.0


def test_localize_payload_zh_unchanged():
    payload = {"年份": 2024, "维度": "中国"}
    assert labels.localize_payload(payload, "zh") == payload
