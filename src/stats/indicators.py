"""各统计专业指标计算。

把统计局业务拆成可计算的指标函数，输入结构化数据、输出统计结果。
参考统计部门专业分工：综合核算、工业、贸易、服务业、投资、农业、人口。
"""
from __future__ import annotations

from src.db import query_indicators
from src.stats.core import yoy, share, rank_items, fmt_pct


def _get(year: int, category: str, indicator: str, dimension: str = "全区") -> float | None:
    rows = query_indicators(year=year, category=category,
                            indicator=indicator, dimension=dimension)
    return rows[0]["value"] if rows else None


# ---------------------------------------------------------------------------
# 各专业统计
# ---------------------------------------------------------------------------
def gdp_overview(year: int, prev_year: int | None = None) -> dict[str, object]:
    gdp = _get(year, "综合", "地区生产总值")
    prev = _get(prev_year, "综合", "地区生产总值") if prev_year else None
    result: dict[str, object] = {
        "指标": "地区生产总值(GDP)",
        "年份": year,
        "数值(亿元)": gdp,
        "同比": fmt_pct(yoy(gdp, prev)) if prev is not None else "—",
    }
    return result


def industry_stats(year: int) -> dict[str, object]:
    total = _get(year, "工业", "规模以上工业总产值")
    added = _get(year, "工业", "规模以上工业增加值")
    rows = query_indicators(year=year, category="工业")
    by_town = [(r["dimension"], r["value"]) for r in rows if r["indicator"] == "规上工业总产值"]
    ranking = rank_items(by_town) if by_town else []
    result: dict[str, object] = {
        "规上工业总产值(亿元)": total,
        "规上工业增加值(亿元)": added,
        "分街镇排名": [{"街镇": n, "产值": v, "排名": rk} for n, v, rk in ranking],
    }
    return result


def trade_stats(year: int) -> dict[str, object]:
    retail = _get(year, "贸易", "社会消费品零售总额")
    sales = _get(year, "贸易", "限额以上商品销售额")
    result: dict[str, object] = {
        "社会消费品零售总额(亿元)": retail,
        "限额以上商品销售额(亿元)": sales,
    }
    return result


def investment_stats(year: int) -> dict[str, object]:
    total = _get(year, "投资", "固定资产投资总额")
    secondary = _get(year, "投资", "第二产业投资")
    tertiary = _get(year, "投资", "第三产业投资")
    result: dict[str, object] = {
        "固定资产投资总额(亿元)": total,
        "第二产业投资(亿元)": secondary,
        "第三产业投资(亿元)": tertiary,
        "工业投资占比(%)": share(secondary, total),
    }
    return result


def population_stats(year: int) -> dict[str, object]:
    pop = _get(year, "人口", "常住人口")
    income = _get(year, "人口", "居民人均可支配收入")
    result: dict[str, object] = {
        "常住人口(万人)": pop,
        "居民人均可支配收入(元)": income,
    }
    return result


def service_stats(year: int) -> dict[str, object]:
    rev = _get(year, "服务业", "规模以上服务业营业收入")
    prev = _get(year - 1, "服务业", "规模以上服务业营业收入")
    result: dict[str, object] = {
        "规模以上服务业营业收入(亿元)": rev,
        "同比": fmt_pct(yoy(rev, prev)) if prev is not None else "—",
    }
    return result


def agriculture_stats(year: int) -> dict[str, object]:
    out = _get(year, "农业", "农业总产值")
    result: dict[str, object] = {"农业总产值(亿元)": out}
    return result


def all_categories() -> list[str]:
    return ["综合", "工业", "贸易", "服务业", "投资", "农业", "人口"]
