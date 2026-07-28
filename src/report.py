"""报表 / 统计公报文本生成，支持「本地统计 + 云端 AI 解读」混合模式。"""
from __future__ import annotations

import json
from typing import cast

from src.stats import indicators as ind
from src.db import query_indicators
from src import knowledge


def generate_bulletin(year: int) -> str:
    gdp = ind.gdp_overview(year, year - 1)
    indus = ind.industry_stats(year)
    trade = ind.trade_stats(year)
    inv = ind.investment_stats(year)
    pop = ind.population_stats(year)

    lines = [
        f"{year}年{'全国'}国民经济和社会发展统计公报（摘要）",
        "=" * 40,
        f"一、综合：地区生产总值 {gdp['数值(亿元)']} 亿元，同比 {gdp['同比']}。",
        f"二、工业：规上工业总产值 {indus['规上工业总产值(亿元)']} 亿元，"
        f"增加值 {indus['规上工业增加值(亿元)']} 亿元。",
        f"三、贸易：社会消费品零售总额 {trade['社会消费品零售总额(亿元)']} 亿元，"
        f"限上商品销售额 {trade['限额以上商品销售额(亿元)']} 亿元。",
        f"四、投资：固定资产投资总额 {inv['固定资产投资总额(亿元)']} 亿元，"
        f"工业投资占比 {inv['工业投资占比(%)']}%。",
        f"五、人口：常住人口 {pop['常住人口(万人)']} 万人，"
        f"居民人均可支配收入 {pop['居民人均可支配收入(元)']} 元。",
    ]
    # 附：本地知识库中与本年度口径相关的条目（离线可用，无需联网）
    related = knowledge.search_knowledge(
        "GDP 工业 贸易 投资 人口 消费品零售 固定资产", limit=3
    )
    if related:
        lines.append("")
        lines.append("附：相关统计口径（来自本地知识库）")
        lines.append("-" * 40)
        for k in related:
            head = f"· {k['title']}"
            if k["source"]:
                head += f"（{k['source']}）"
            lines.append(head)
            lines.append(f"  {k['content']}")
    return "\n".join(lines)


def _extract_cloud_text(result: object) -> str:
    """尽力从 agent_infini 的 task show 结果里抽取可读文本。"""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        mapped: dict[str, object] = cast("dict[str, object]", result)
        for key in ("answer", "content", "text", "summary", "result"):
            v = mapped.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # 尝试 messages/卷宗式结构
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


def generate_report(year: int, use_cloud: bool = False) -> str:
    """生成报告。use_cloud=True 时追加云端 AI 解读（失败自动回退仅本地）。"""
    bulletin = generate_bulletin(year)
    if not use_cloud:
        return bulletin

    from src.analyzer import get_analyzer, AgentInfiniError
    try:
        az = get_analyzer()
        if az is None:
            return bulletin + "\n\n[注] 云端分析未启用，仅输出本地统计公报。"
        # 召回本地知识库作为上下文，让 AI 解读紧扣本区统计口径
        kb_ctx = knowledge.retrieve_context(bulletin, limit=5)
        knowledge_block = (
            "\n\n【本地知识库参考口径】\n" + kb_ctx + "\n"
            if kb_ctx else ""
        )
        prompt = (
            "你是资深统计分析师。请基于以下全国统计公报与统计口径说明，"
            "提炼 3-5 条经济亮点，并指出 1-2 个需关注的结构性问题与建议：\n\n"
            + bulletin + knowledge_block
        )
        out = az.analyze(prompt)
        interpretation = _extract_cloud_text(out.get("result"))
        return bulletin + "\n\n" + "=" * 40 + "\n【AI 解读】\n" + interpretation
    except AgentInfiniError as e:
        return bulletin + f"\n\n[注] 云端解读失败：{e}\n已仅输出本地统计公报。"


def export_csv(year: int, path: str) -> None:
    import csv
    rows = query_indicators(year=year)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["year", "category", "indicator",
                                          "dimension", "value", "unit", "note"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in w.fieldnames})
