"""数据标识符的多语言标签层（label layer）。

背景
----
指标宽表里的 ``category`` / ``indicator`` / ``dimension`` / ``unit`` 存的是**中文规范键**，
这样数据文件本身可读、也能和官方统计口径逐字对齐。但中文键不能直接交给非中文消费方：
接口一出去，海外开发者 / 集成方拿到的就是 ``综合`` ``GDP增长率`` ``亿美元``。

原先的做法是在**浏览器**里用 ``public/i18n.js`` 的 ``trData()`` 逐个替换中文词条，
界面看起来是双语的，但 REST API 依然是单语，而且新增指标必须同步改前端字典，否则漏译。
本模块把这件事移回**服务端**：以 ``data/labels.csv`` 为唯一事实来源，按请求语言本地化。

字段约定
--------
每个词条返回三件东西：

- ``{field}``       本地化后的展示值（``lang=en`` 给英文，``lang=zh`` 给中文规范键）
- ``{field}_key``   原始中文规范键，跨语言稳定，适合做连接键
- ``{field}_slug``  稳定 ASCII 标识符，供程序消费（``gdp_growth`` / ``usd_100m``）

未在 ``data/labels.csv`` 登记的键**不会被翻译**，原样返回，绝不抛异常——保证向前兼容。
"""
from __future__ import annotations

import csv
import io
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
LABELS_PATH = BASE_DIR / "data" / "labels.csv"

KINDS = ("category", "indicator", "dimension", "unit")
LANGS = ("en", "zh")
DEFAULT_LANG = "en"

#: 指标行中需要本地化的字段
ROW_FIELDS = ("category", "indicator", "dimension", "unit")


# ---------------------------------------------------------------------------
# 语言解析
# ---------------------------------------------------------------------------
@lru_cache(maxsize=8)
def normalize_lang(value: str | None) -> str:
    """把 ``zh`` / ``zh-CN`` / ``zh_CN`` / ``en`` / ``en_US`` 归一为 ``zh`` / ``en``。

    按入参缓存：解析结果只有 ``zh`` / ``en`` 两种取值，而指标宽表每行要经它
    5 次（4 个字段调 :func:`label` + 1 次 :func:`localize_note`），
    strip/lower/replace 的重复劳动在 700+ 行的表上被放大成可测的开销。
    词条表变更由 :func:`reload` 统一失效缓存。
    """
    v = (value or "").strip().lower().replace("_", "-")
    if v.startswith("zh"):
        return "zh"
    if v.startswith("en"):
        return "en"
    return DEFAULT_LANG


def lang_from_accept_language(header: str | None) -> str | None:
    """从 ``Accept-Language`` 头里取第一个可识别的语言；无法识别返回 ``None``。"""
    if not header:
        return None
    for part in header.split(","):
        tag = part.split(";")[0].strip().lower()
        if not tag:
            continue
        if tag.startswith("zh"):
            return "zh"
        if tag.startswith("en"):
            return "en"
    return None


# ---------------------------------------------------------------------------
# 标签包加载
# ---------------------------------------------------------------------------
def _raw_text() -> str:
    """优先读 ``data/labels.csv``；Serverless 部署包内没有 data/，回退到内嵌常量。

    用 ``utf-8-sig`` 读取：编辑器（含部分 AI 工具）保存带 BOM 的 UTF-8 时，
    BOM 会让首行注释变成 CSV 表头，整个标签包静默失效——这里统一剥掉。
    """
    text = ""
    try:
        text = LABELS_PATH.read_text(encoding="utf-8-sig")
    except OSError:
        try:
            from src.seed_data import LABELS_CSV  # 由 scripts/embed_pages.py 生成

            text = str(LABELS_CSV)
        except Exception:
            return ""
    except Exception:
        return ""
    return text.lstrip("\ufeff")


@lru_cache(maxsize=1)
def _table() -> dict[tuple[str, str], dict[str, str]]:
    """``(kind, key) -> {slug, en}``。以 ``#`` 开头的行是注释。

    只接受 ``kind`` 属于 :data:`KINDS` 的行，因此即便标签包首行混入 BOM、
    表头或其它杂质，也不会污染映射表（垃圾行直接跳过）。
    """
    rows = [
        line.lstrip("\ufeff")
        for line in _raw_text().splitlines()
        if line.strip() and not line.lstrip("\ufeff").lstrip().startswith("#")
    ]
    table: dict[tuple[str, str], dict[str, str]] = {}
    if not rows:
        return table
    for row in csv.DictReader(io.StringIO("\n".join(rows))):
        kind = (row.get("kind") or "").strip()
        key = (row.get("key") or "").strip()
        if kind not in KINDS or not key:
            continue
        table[(kind, key)] = {
            "slug": (row.get("slug") or "").strip(),
            "en": (row.get("en") or "").strip(),
        }
    return table


def reload() -> None:
    """清空缓存，重新读取标签包（改完 labels.csv 后调用）。

    四个查表纯函数的缓存值同样由标签包内容决定，必须一起失效：漏清任何一个，
    改完 labels.csv 后接口都会继续返回上一版数据——缓存错误在这里
    等同于数据错误。:func:`normalize_lang` 不读表但同样在此一并清理，
    避免「有的清有的不清」让人以为漏写的是笔误。
    """
    _table.cache_clear()
    _reverse.cache_clear()
    normalize_lang.cache_clear()
    label.cache_clear()
    slug.cache_clear()
    localize_note.cache_clear()


def stats() -> dict[str, int]:
    """各 kind 已登记的词条数（供 ``db info`` 之类的自检使用）。"""
    out = {k: 0 for k in KINDS}
    for kind, _key in _table():
        out[kind] = out.get(kind, 0) + 1
    return out


# ---------------------------------------------------------------------------
# 单词条
# ---------------------------------------------------------------------------
@lru_cache(maxsize=2048)
def label(kind: str, key: str | None, lang: str = DEFAULT_LANG) -> str:
    """返回 ``key`` 在 ``lang`` 下的标签；未登记或空值时原样返回。

    纯查表函数，按 ``(kind, key, lang)`` 缓存；词条表变更走 :func:`reload`。
    """
    if not key:
        return key or ""
    if normalize_lang(lang) == "zh":
        return key
    entry = _table().get((kind, key))
    if entry and entry["en"]:
        return entry["en"]
    return key


def _fallback_slug(value: str) -> str:
    """未登记词条的兜底 slug：仅规整 ASCII 部分；含非 ASCII 则原样返回（不猜测）。"""
    out: list[str] = []
    for ch in value.strip().lower():
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch in " -_/&+":
            out.append("_")
        else:
            return value
    slug = re.sub(r"_{2,}", "_", "".join(out)).strip("_")
    return slug or value


@lru_cache(maxsize=2048)
def slug(kind: str, key: str | None) -> str:
    """返回 ``key`` 的稳定 ASCII 标识符；未登记时退回兜底规则。

    同 :func:`label`：纯查表（未登记时走 :func:`_fallback_slug`，同样是
    按入参决定的纯函数），按 ``(kind, key)`` 缓存；词条表变更走 :func:`reload`。
    """
    if not key:
        return key or ""
    entry = _table().get((kind, key))
    if entry and entry["slug"]:
        return entry["slug"]
    return _fallback_slug(key)


def term(kind: str, key: str | None, lang: str = DEFAULT_LANG) -> dict[str, str]:
    """把一个词条规范成 ``{label, key, slug}`` 三件套。"""
    raw = key or ""
    return {"label": label(kind, raw, lang), "key": raw, "slug": slug(kind, raw)}


@lru_cache(maxsize=8)
def _reverse(kind: str) -> dict[str, str]:
    """``英文标签 / slug（小写） -> 规范键``，供入参反向解析。"""
    out: dict[str, str] = {}
    for (k, key), entry in _table().items():
        if k != kind:
            continue
        if entry["en"]:
            out.setdefault(entry["en"].lower(), key)
        if entry["slug"]:
            out.setdefault(entry["slug"].lower(), key)
    return out


def key_of(kind: str, value: str) -> str:
    """把「英文标签 / slug / 中文规范键」统一解析为规范键。

    海外消费方很自然会写 ``?dimension=China`` 或 ``?dimension=china``，
    这里让它们与 ``?dimension=中国`` 等价。无法识别时**原样返回**，
    既不做猜测，也不把未知维度悄悄换成默认值。
    入参为必填 ``str``（空串原样返回）；调用方若可能拿到 ``None``，
    在入口处自行判空，不要传进来。
    """
    if not value:
        return value
    raw = value.strip()
    if not raw:
        return raw
    if (kind, raw) in _table():          # 已经是规范键
        return raw
    return _reverse(kind).get(raw.lower(), raw)


# ---------------------------------------------------------------------------
# note（数据来源说明）
# ---------------------------------------------------------------------------
#: 世界银行来源由脚本生成，格式固定，直接按结构重组，不做词条替换。
_WB_NOTE = re.compile(r"^来源：世界银行OpenData\((?P<code>[^,)]+)(?:,\s*(?P<iso>[^)]+))?\)$")

#: 国家统计局 / 海关总署是自由文本，按词条替换；长词在前，避免局部覆盖。
_NOTE_TERMS: tuple[tuple[str, str], ...] = (
    ("年国民经济运行情况", " National Economic Performance"),
    ("初步核算", "preliminary accounting"),
    ("不含农户", "excluding rural households"),
    ("年末", "end of year"),
    ("国家统计局", "China NBS"),
    ("海关总署", "China Customs"),
    ("出口", "exports"),
    ("进口", "imports"),
    ("（", " ("),
    ("）", ")"),
)


@lru_cache(maxsize=1024)
def localize_note(note: str | None, lang: str = DEFAULT_LANG) -> str:
    """把带中文来源前缀的 note 转为目标语言；无法识别时原样返回。

    只依赖正则与替换表，结果由入参完全决定，按 ``(note, lang)`` 缓存
    （库里 note 的取值高度重复，命中率接近 100%）；词条表变更走 :func:`reload`。
    """
    if not note:
        return note or ""
    if normalize_lang(lang) == "zh":
        return note

    matched = _WB_NOTE.match(note.strip())
    if matched:
        code = matched.group("code").strip()
        iso = (matched.group("iso") or "").strip()
        inside = f"{code}, {iso}" if iso else code
        return f"Source: World Bank Open Data ({inside})"

    out = note
    for zh, en in _NOTE_TERMS:
        out = out.replace(zh, en)
    # 中英混排后补上被吞掉的空格（如 "China NBS2024end" → "China NBS 2024 end"）
    out = re.sub(r"([A-Za-z])(\d)", r"\1 \2", out)
    out = re.sub(r"(\d)([A-Za-z])", r"\1 \2", out)
    return re.sub(r"\s{2,}", " ", out).strip()


# ---------------------------------------------------------------------------
# 整行 / 整批
# ---------------------------------------------------------------------------
def localize_indicator(row: Mapping[str, Any], lang: str = DEFAULT_LANG) -> dict[str, Any]:
    """把一行指标数据转成 API 输出。

    ``category`` / ``indicator`` / ``dimension`` / ``unit`` 被替换为本地化标签，
    同时并列给出 ``*_key``（中文规范键）与 ``*_slug``（ASCII 稳定键），
    因此消费方既可以按语言取展示文案，也可以按稳定键做程序处理。
    """
    out: dict[str, Any] = {
        k: v for k, v in row.items() if k not in ROW_FIELDS and k != "note"
    }
    for field in ROW_FIELDS:
        raw = str(row.get(field) or "")
        out[field] = label(field, raw, lang)
        out[f"{field}_key"] = raw
        out[f"{field}_slug"] = slug(field, raw)

    note = row.get("note")
    if note is not None:
        out["note"] = localize_note(str(note), lang)
        out["note_key"] = str(note)
    return out


def localize_indicators(rows: Sequence[Mapping[str, Any]],
                        lang: str = DEFAULT_LANG) -> list[dict[str, Any]]:
    return [localize_indicator(r, lang) for r in rows]


def localize_terms(kind: str, keys: list[str] | tuple[str, ...],
                   lang: str = DEFAULT_LANG) -> list[dict[str, str]]:
    """批量本地化一组同类词条（如维度下拉、专业下拉）。"""
    return [term(kind, k, lang) for k in keys if k]


# ---------------------------------------------------------------------------
# /api/ask 的 UI 状载荷
# ---------------------------------------------------------------------------
#: 结构键 → 英文键。只列「不是数据词条」的框架键；
#: 以指标名 / 专业名做键的（如 ``货物服务出口总额``）走 slug 规则，无需在此登记。
_ASK_KEY_MAP: dict[str, str] = {
    "年份": "year",
    "维度": "dimension",
    "匹配指标": "matched_indicators",
    "指标概览": "indicator_overview",
    "分经济体排名": "ranking_by_economy",
    "指标": "indicator",
    "指标名": "indicator_name",
    "数值": "value",
    "单位": "unit",
    "同比": "yoy",
    "排名": "rank",
    "经济体": "economy",
    "注": "note",
    "说明": "note",
    "备注": "remark",
    "知识库参考": "kb_reference",
    "AI 解读": "ai_interpretation",
    "指标值": "indicator_value",
    "数值(亿元)": "value_cny_100m",
    "数值(亿美元)": "value_usd_100m",
    "二产投资占比(%)": "secondary_industry_investment_share",
}

#: 「指标(单位)」形态的复合键，如 ``总人口(亿人)``、``失业率(%)``
_COMPOSED_KEY = re.compile(r"^(?P<head>[^()]+)\((?P<unit>[^()]*)\)$")


def _first_slug(key: str) -> str | None:
    """返回 key 在某类词条下的 slug；未登记时返回 None。"""
    for kind in KINDS:
        candidate = slug(kind, key)
        if candidate != key:
            return candidate
    return None


def ask_key(key: str, lang: str = DEFAULT_LANG) -> str:
    """把 ``/api/ask`` 的结构键转为 ASCII 键（``lang=zh`` 时原样返回）。

    依次尝试：显式映射 → 整键 slug → ``指标(单位)`` 复合键拆开分别 slug。
    因此「以指标名做键」得到 ``exports_goods_services``，
    「指标名(单位)」得到 ``total_population_hundred_million_people``。
    """
    if normalize_lang(lang) == "zh":
        return key
    if key in _ASK_KEY_MAP:
        return _ASK_KEY_MAP[key]

    whole = _first_slug(key)
    if whole:
        return whole

    matched = _COMPOSED_KEY.match(key)
    if matched:
        head = _first_slug(matched.group("head").strip())
        # 头部（指标名）识别不出时保持原键：只返回单位 slug 会产出
        # 「percent」这种丢掉语义的键，比保留中文更有害。
        if head:
            unit = _first_slug(matched.group("unit").strip())
            return "_".join(p for p in (head, unit) if p)
    return key


def _localize_string(value: str, lang: str) -> str:
    """本地化单个字符串：整串命名词条 → 整串翻译；否则做「长词优先」的组合串替换。"""
    if not value:
        return value
    if value.startswith(("来源：", "国家统计局", "海关总署")):
        return localize_note(value, lang)
    for kind in KINDS:
        translated = label(kind, value, lang)
        if translated != value:
            return translated

    # 组合串替换只对「像标签的短串」生效（如 货物服务出口总额(亿元)）。
    # 知识库正文等长文本是人工撰写内容，逐词替换会改坏语句，故整段跳过。
    if len(value) > 40 or "\n" in value:
        return value

    out = value
    for _kind, key in sorted(_table(), key=lambda kv: -len(kv[1])):
        english = label(_kind, key, lang)
        if english != key and key in out:
            out = out.replace(key, english)
    return out


def _walk(node: Any, lang: str) -> Any:
    if isinstance(node, dict):
        return {ask_key(str(k), lang): _walk(v, lang) for k, v in node.items()}
    if isinstance(node, list):
        return [_walk(x, lang) for x in node]
    if isinstance(node, tuple):
        return [_walk(x, lang) for x in node]
    if isinstance(node, str):
        return _localize_string(node, lang)
    return node


def localize_payload(payload: Any, lang: str = DEFAULT_LANG) -> Any:
    """把「UI 状」载荷（``/api/ask`` 结果、统计公报 JSON）整体转为目标语言。

    ``lang=en``：结构键重命名为 ASCII（``年份`` → ``year``），
    值按词条翻译（``GDP增长率`` → ``GDP growth``），来源说明走 :func:`localize_note`。
    ``lang=zh``：原样返回——中文键本身就是规范键。

    键重命名只作用于中文键；已经是 ASCII 的键（``category`` / ``indicator``）原样保留。
    """
    if normalize_lang(lang) == "zh":
        return payload
    return _walk(payload, lang)
