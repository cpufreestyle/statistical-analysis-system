"""自然语言式查询：把中文问句解析为统计口径（本地规则，无需云端）。

参考 agent_infini 的 `task ask` 多轮分析思路，但用本地关键词路由实现。
支持类似：
  "2024年GDP多少"
  "工业总产值"
  "各街镇工业排名"
  "固定资产投资构成"
"""
from __future__ import annotations

import re
from typing import Callable

from src.stats import indicators as ind
from src.stats import custom as cust
from src import knowledge


# 每个关键词 -> (输出键, 单参数统计函数)。gdp 需要两年对比，用 lambda 包一层。
CATEGORY_MAP: dict[str, tuple[str, Callable[[int], dict[str, object]]]] = {
    "gdp": ("GDP", lambda y: ind.gdp_overview(y, y - 1)),
    "工业": ("工业", ind.industry_stats),
    "规上工业": ("工业", ind.industry_stats),
    "贸易": ("贸易", ind.trade_stats),
    "社零": ("贸易", ind.trade_stats),
    "消费": ("贸易", ind.trade_stats),
    "投资": ("投资", ind.investment_stats),
    "固定资产": ("投资", ind.investment_stats),
    "人口": ("人口", ind.population_stats),
    "居民": ("人口", ind.population_stats),
    "服务业": ("服务业", ind.service_stats),
    "规上服务业": ("服务业", ind.service_stats),
    "农业": ("农业", ind.agriculture_stats),
}


def parse_year(text: str, default: int = 2024) -> int:
    m = re.search(r"(20\d{2})", text)
    return int(m.group(1)) if m else default


def ask(text: str, default_year: int = 2024, with_knowledge: bool = True) -> dict[str, object]:
    year = parse_year(text, default_year)
    result = _ask_core(text, year)
    if with_knowledge:
        ctx = knowledge.retrieve_context(text)
        if ctx:
            result["知识库参考"] = ctx
    return result


def _match_indicators(text: str, year: int) -> list[dict[str, object]]:
    """在指标库中查找名称被问句直接提及的指标，返回该年数值。"""
    from src.db import query_indicators

    rows = query_indicators(year=year)
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, object]] = []
    for r in rows:
        name = r["indicator"]
        if not name or name not in text:
            continue
        key = (name, r["dimension"])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "指标": name,
            "维度": r["dimension"],
            "数值": r["value"],
            "单位": r["unit"],
            "说明": r["note"],
        })
    return out


def _ask_core(text: str, year: int) -> dict[str, object]:
    t = text.lower()
    # 自定义分析优先：命中名称即按用户定义公式求值
    for a in cust.load_custom():
        if a.get("name", "") and a.get("name", "").lower() in t:
            return {"年份": year, a.get("name", ""): cust.run_custom(a, year)}
    for kw, (key, fn) in CATEGORY_MAP.items():
        if kw.lower() in t:
            return {"年份": year, key: fn(year)}
    # 具体指标名命中：问到「社会消费品零售总额」这类也能答到点
    hits = _match_indicators(text, year)
    if hits:
        return {"年份": year, "匹配指标": hits}
    # 默认返回综合概览
    return {
        "年份": year,
        "GDP": ind.gdp_overview(year, year - 1),
        "工业": ind.industry_stats(year),
        "贸易": ind.trade_stats(year),
        "投资": ind.investment_stats(year),
        "人口": ind.population_stats(year),
    }
