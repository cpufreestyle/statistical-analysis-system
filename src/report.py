"""报表 / 统计公报文本生成，支持「本地统计 + 云端 AI 解读」混合模式。

公报内容完全由库中的**真实公开数据**生成（世界银行 Open Data /
国家统计局 / 海关总署），中英双语输出，便于对外展示。
"""
from __future__ import annotations

import json
from typing import cast

from src.db import query_indicators
from src.stats import indicators as ind
from src.stats.core import yoy, fmt_pct
from src import knowledge

_L = {
    "en": {
        "title": "{dim} · Economic and Social Development Statistical Bulletin (Summary) — {year}",
        "source": "Sources: World Bank Open Data · National Bureau of Statistics · General Administration of Customs (all public)",
        "section": "Section",
        "kb_head": "Annex: caliber notes from the local knowledge base",
        "yoy": "YoY",
        "dim": "Region",
    },
    "zh": {
        "title": "{dim} · 国民经济和社会发展统计公报（摘要）— {year}年",
        "source": "数据来源：世界银行 Open Data · 国家统计局 · 海关总署（均为公开数据）",
        "section": "项目",
        "kb_head": "附：相关统计口径（来自本地知识库）",
        "yoy": "同比",
        "dim": "维度",
    },
}


def _fmt_num(v: float) -> str:
    return f"{v:,.2f}" if abs(v) < 1e6 else f"{v:,.0f}"


# 比率类单位不做「同比」（增长率的同比没有统计意义）
_RATIO_UNITS = {"%", "岁"}


def build_bulletin_data(year: int, dimension: str = "亚太",
                        lang: str = "en") -> dict[str, object]:
    """结构化公报数据（供前端按当前语言渲染，避免服务端硬编码文案）。

    返回 sections[].rows[] 里的指标名 / 单位 / 专业都是中文原值，
    前端用同一份 i18n 字典翻译，保证中英文都不漏译。
    """
    rows = query_indicators(year=year, dimension=dimension)
    sections: list[dict[str, object]] = []
    for category in ind.CATEGORY_PRIORITY:
        cat_rows = [r for r in rows if r["category"] == category]
        if not cat_rows:
            continue
        items: list[dict[str, object]] = []
        for r in sorted(cat_rows, key=lambda x: x["indicator"]):
            rate = None
            if r["unit"] not in _RATIO_UNITS:
                prev = ind.value_of(year - 1, r["category"], r["indicator"], dimension)
                rate = yoy(r["value"], prev) if prev is not None else None
            items.append({
                "indicator": r["indicator"],
                "value": _fmt_num(r["value"]),
                "unit": r["unit"],
                "yoy": fmt_pct(rate) if rate is not None else "",
                "note": r["note"],
            })
        sections.append({"category": category, "rows": items})

    kb_rows = knowledge.search_knowledge(
        "GDP industry trade investment population statistics caliber",
        limit=4, lang=lang)
    return {
        "year": year,
        "dimension": dimension,
        "sections": sections,
        "knowledge": [{"title": k["title"], "source": k["source"],
                       "content": k["content"]} for k in kb_rows],
    }


def _render_text(data: dict[str, object], year: int, dimension: str,
                 lang: str) -> str:
    """把结构化公报渲染成纯文本（CLI / 云端 prompt 上下文使用）。

    结构化数据里的标识符是中文规范键；这里按 ``lang`` 本地化，
    因此 ``--lang en`` 输出的是英文专业 / 指标 / 单位，不会夹中文。
    """
    from src import labels

    t = _L["zh"] if lang.startswith("zh") else _L["en"]
    lines: list[str] = [
        t["title"].format(dim=labels.label("dimension", dimension, lang), year=year),
        "=" * 64,
        t["source"],
        "",
    ]
    idx = 0
    for section in cast("list[dict[str, object]]", data["sections"]):
        lines.append(f"[{labels.label('category', str(section['category']), lang)}]")
        for row in cast("list[dict[str, object]]", section["rows"]):
            idx += 1
            suffix = (f"  ({t['yoy']} {row['yoy']})" if row["yoy"] else "")
            indicator = labels.label("indicator", str(row["indicator"]), lang)
            unit = labels.label("unit", str(row["unit"]), lang)
            lines.append(f"{idx:>2}. {indicator}: {row['value']} {unit}{suffix}")
        lines.append("")
    kb_rows = cast("list[dict[str, object]]", data["knowledge"])
    if kb_rows:
        lines.append(t["kb_head"])
        lines.append("-" * 64)
        for k in kb_rows:
            head = f"· {k['title']}"
            if k["source"]:
                head += f" ({k['source']})"
            lines.append(head)
            lines.append(f"  {k['content']}")
    return "\n".join(lines)


def generate_bulletin(year: int, dimension: str = "亚太", lang: str = "en") -> str:
    """用真实数据生成统计公报摘要（纯文本，供 CLI / 导出使用）。"""
    return _render_text(build_bulletin_data(year, dimension, lang), year, dimension, lang)


def _extract_cloud_text(result: object) -> str:
    """尽力从云端返回结构里抽取可读文本。"""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        mapped: dict[str, object] = cast("dict[str, object]", result)
        for key in ("answer", "content", "text", "summary", "result"):
            v = mapped.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for key in ("messages", "data"):
            v = mapped.get(key)
            if isinstance(v, list) and v:
                last = v[-1]
                if isinstance(last, dict):
                    last_m: dict[str, object] = cast("dict[str, object]", last)
                    for k in ("content", "text", "message"):
                        val = last_m.get(k)
                        if isinstance(val, str):
                            return val
    return json.dumps(result, ensure_ascii=False)


def _cloud_interpret(bulletin: str, lang: str) -> tuple[str, str, bool]:
    """调用云端 AI 对公报做解读。返回 (解读文本, 备注/错误, 是否命中缓存)。"""
    en = not lang.startswith("zh")
    from src.analyzer import get_analyzer, AgentInfiniError
    try:
        az = get_analyzer(lang=lang)
        if az is None:
            return ("", "Cloud AI is not enabled; local bulletin only." if en
                    else "云端分析未启用，仅输出本地统计公报。", False)
        kb_ctx = knowledge.retrieve_context(bulletin, limit=5, lang=lang)
        knowledge_block = (f"\n\n[Knowledge-base caliber notes]\n{kb_ctx}\n"
                           if (kb_ctx and en) else
                           (f"\n\n【本地知识库参考口径】\n{kb_ctx}\n" if kb_ctx else ""))
        if en:
            prompt = (
                "You are a senior statistical analyst. Based only on the bulletin and "
                "caliber notes below, write 3-5 highlights and 1-2 structural risks with "
                "a brief recommendation. Reply in English with short Markdown bullets; "
                "do not invent figures.\n\n" + bulletin + knowledge_block
            )
        else:
            prompt = (
                "你是资深统计分析师。请基于以下统计公报与统计口径说明，"
                "提炼 3-5 条经济亮点，并指出 1-2 个需关注的结构性问题与建议：\n\n"
                + bulletin + knowledge_block
            )
        bulletin_file = [{"name": ("统计公报.md" if not en else "bulletin.md"),
                          "content": bulletin + knowledge_block}]
        from src import ai_cache
        out, cached = ai_cache.analyze_cached(az, prompt, files=bulletin_file, lang=lang)
        return (_extract_cloud_text(out.get("result")), "", cached)
    except AgentInfiniError as e:
        return ("", f"Cloud interpretation failed: {e}" if en
                else f"云端解读失败：{e}", False)


def build_report(year: int, use_cloud: bool = False, dimension: str = "亚太",
                 lang: str = "en") -> dict[str, object]:
    """结构化报告：公报数据 + 可选 AI 解读（前端按当前语言渲染）。"""
    data = build_bulletin_data(year, dimension, lang)
    data["ai"] = ""
    data["ai_note"] = ""
    data["ai_cached"] = False
    if use_cloud:
        text = _render_text(data, year, dimension, lang)
        data["ai"], data["ai_note"], data["ai_cached"] = _cloud_interpret(text, lang)
    return data


def generate_report(year: int, use_cloud: bool = False,
                    dimension: str = "亚太", lang: str = "en") -> str:
    """生成纯文本报告（CLI 用）。use_cloud=True 时追加云端 AI 解读。"""
    bulletin = generate_bulletin(year, dimension=dimension, lang=lang)
    if not use_cloud:
        return bulletin
    en = not lang.startswith("zh")
    ai, note, _cached = _cloud_interpret(bulletin, lang)
    if note:
        return bulletin + ("\n\n[Note] " if en else "\n\n[注] ") + note
    head = "\n[AI Interpretation]\n" if en else "\n【AI 解读】\n"
    return bulletin + "\n" + "=" * 64 + head + ai


def export_csv(year: int, path: str) -> None:
    import csv
    rows = query_indicators(year=year)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["year", "category", "indicator",
                                          "dimension", "value", "unit", "note"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in w.fieldnames})
