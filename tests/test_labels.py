"""i18n 标签层契约测试（纯数据、离线、无网络）。

覆盖 src.labels 的关键路径：语言归一化、单词条 label/slug/term、入参反向解析
key_of（含未登记兜底）、整行 localize_indicator 的 *_key/_slug 并列、来源说明
localize_note（世界银行 + 国家统计局两种形态）、以及 /api/ask 载荷的
localize_payload 结构键重命名。

词条取自 data/labels.csv（被跟踪，CI 可用）。未登记键一律原样返回、绝不抛异常
——这是「向前兼容」的硬约定，单独测了。

文件末尾一段把关的是**双层英文口径**：前端 public/i18n.js 的 ZH2EN 字典与
labels.csv 的英文列，同名词条必须逐字一致（约定见 i18n.js 头部与 HANDOFF §4）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src import labels

BASE_DIR = Path(__file__).resolve().parent.parent


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
    assert labels.label("indicator", "GDP增长率", "en") == "GDP growth"
    assert labels.label("category", "综合", "en") == "National accounts"


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
    assert t == {"label": "GDP growth", "key": "GDP增长率", "slug": "gdp_growth"}


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
    assert out["category"] == "National accounts"
    assert out["indicator"] == "GDP growth"
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
    assert [r["indicator"] for r in out] == ["GDP growth", "Exports of goods and services"]
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
    assert out["matched_indicators"][0]["indicator"] == "GDP growth"
    assert out["matched_indicators"][0]["value"] == 5.0


def test_localize_payload_zh_unchanged():
    payload = {"年份": 2024, "维度": "中国"}
    assert labels.localize_payload(payload, "zh") == payload


# ---------------------------------------------------------------------------
# 前端字典 ↔ labels.csv 的逐字一致
# public/i18n.js 头部与本文件所在的服务端标签层都声明「英文口径逐字一致」，
# 此前只是散文约定：任一侧改措辞都不会被发现，接口英文与界面英文会静默分叉。
# ---------------------------------------------------------------------------
I18N_PATH = BASE_DIR / "public" / "i18n.js"

_DICT_RE = re.compile(r"var ZH2EN = \{(.*?)\n  \};", re.S)
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_PAIR_RE = re.compile(
    r'"((?:[^"\\]|\\.)*)"\s*:\s*(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\')',
    re.S,
)


def _js_string(raw: str) -> str:
    return (raw.replace('\\"', '"').replace("\\'", "'")
               .replace("\\\\", "\\").replace("\\n", "\n"))


def _frontend_dict() -> dict[str, str]:
    """取出 public/i18n.js 的 ZH2EN 字典（中文键 → 英文文案）。"""
    text = I18N_PATH.read_text(encoding="utf-8")
    block = _DICT_RE.search(text)
    assert block, "未能在 public/i18n.js 中定位 ZH2EN 字典，本检查已失效"
    entries = {
        _js_string(key): _js_string(dv or sv)
        for key, dv, sv in _PAIR_RE.findall(_COMMENT_RE.sub("", block.group(1)))
    }
    assert len(entries) > 200, f"ZH2EN 解析结果异常（仅 {len(entries)} 条）"
    return entries


def _registered_terms() -> dict[str, set[str]]:
    """labels.csv 已登记的 (中文规范键 -> 该键全部英文标签)。

    同一中文键可能在多个 kind 下登记（如指标与单位重名），因此取值集合：
    前端写法只要与其中任一条逐字相等即视为一致。
    """
    out: dict[str, set[str]] = {}
    for (_kind, key), entry in labels._table().items():
        out.setdefault(key, set()).add(entry["en"])
    return out


def test_frontend_dictionary_matches_labels_csv_verbatim():
    zh2en = _frontend_dict()
    terms = _registered_terms()
    shared = {key: en for key, en in terms.items() if key in zh2en}

    # 交集过小意味着某一侧的词条被批量改名/删除，比对就失去意义了
    assert len(shared) >= 40, f"前端字典与 labels.csv 只重合 {len(shared)} 条，请检查两侧词条"
    drift = {key: (sorted(candidates), zh2en[key])
             for key, candidates in shared.items() if zh2en[key] not in candidates}
    assert not drift, f"同名词条两侧不一致（labels.csv vs i18n.js）：{drift}"


def test_frontend_dictionary_has_no_conflicting_duplicate_keys():
    """JS 对象字面量里重复键会静默覆盖——同一中文键两个英文写法正是双层漂移的典型形态。"""
    text = I18N_PATH.read_text(encoding="utf-8")
    block = _DICT_RE.search(text)
    assert block
    seen: dict[str, str] = {}
    clashes: list[tuple[str, str, str]] = []
    for key, dv, sv in _PAIR_RE.findall(_COMMENT_RE.sub("", block.group(1))):
        k, v = _js_string(key), _js_string(dv or sv)
        if k in seen and seen[k] != v:
            clashes.append((k, seen[k], v))
        seen[k] = v
    assert not clashes, f"ZH2EN 中同名键给出不同英文：{clashes}"

# ---------------------------------------------------------------------------
# 前端静态文案的字典覆盖
# ``data-i18n`` / ``-html`` / ``-ph`` 的属性值，与 ``tr()`` / ``trData()`` 的字面量
# 参数，都必须是 ZH2EN 的键——否则英文界面会裸显中文。``applyLang`` 的三个处理器
# （见 i18n.js）都只做精确查表，没有 trData 兜底，所以「字典里没有」就等于「不翻译」。
# 这类泄漏 scripts/check_i18n.py 查不到：它只审 API 响应，不看 DOM 与前端拼装串。
# 曾因此让自定义分析的两个英文输入框占位符、以及命令面板的「示例问题」分组标签
# 在英文下一直显示中文（2026-09-24 修）。
# ---------------------------------------------------------------------------
_I18N_ATTR_RE = re.compile(r'data-i18n(?:-html|-ph)?\s*=\s*"([^"]*)"')
_TR_CALL_RE = re.compile(
    r"""\btr(?:Data)?\(\s*(?:"([^"\\\n]*)"|'([^'\\\n]*)')\s*[,)]""")


def _public_texts() -> list[tuple[str, str]]:
    """public/ 下全部 .html / .js 的 (文件名, 文本)——静态文案与前端拼装串都在这里。"""
    out: list[tuple[str, str]] = []
    for path in sorted((BASE_DIR / "public").iterdir()):
        if path.suffix in (".html", ".js"):
            out.append((path.name, path.read_text(encoding="utf-8")))
    assert out, "未在 public/ 找到 .html/.js，本检查已失效"
    return out


def test_static_i18n_attributes_are_dictionary_keys():
    """data-i18n / -html / -ph 的值必须命中字典。"""
    zh2en = _frontend_dict()
    missing: dict[str, set[str]] = {}
    for name, text in _public_texts():
        for raw in _I18N_ATTR_RE.findall(text):
            key = raw.strip()
            if key and key not in zh2en:
                missing.setdefault(name, set()).add(key)
    assert not missing, (
        f"data-i18n* 的值不在 ZH2EN 字典里，英文界面将裸显中文：{missing}"
    )


def test_dynamic_tr_calls_are_dictionary_keys():
    """tr() / trData() 的字面量参数同理（命令面板、空态提示等动态文案）。"""
    zh2en = _frontend_dict()
    missing: set[str] = set()
    for name, text in _public_texts():
        for dquoted, squoted in _TR_CALL_RE.findall(text):
            key = dquoted or squoted
            if key and key not in zh2en:
                missing.add(f"{name}:{key}")
    assert not missing, (
        f"tr()/trData() 的字面量参数不在 ZH2EN 字典里，英文界面将裸显中文：{sorted(missing)}"
    )
