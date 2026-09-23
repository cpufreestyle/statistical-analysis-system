"""看板「数据洞察」：从本地公开数据算出**可复算**的年度变化（供 ``/api/insights``）。

与项目定位一致——只陈述真实数据、绝不编数：

- 只用本地 SQLite 里的真实行，不做任何模型推断或补数；
- 每条洞察都带两年数值与指标名，读者可以拿 ``/api/indicators`` 自己复算；
- 同比口径与看板卡片一致（同维度、同指标、相邻两年）；上一年缺失或为 0 时
  该指标不进入榜单（宁缺毋滥，而不是给一个误导性的百分比）。

本地化不在这里做：本模块一律返回中文规范键 + 数值，由 ``src/web.py`` 经
``src/labels.py`` 统一本地化（见交接文档约定 2）。
"""
from __future__ import annotations

from src.db import query_indicators

#: 每个榜单的默认条数：看板一屏放得下，也不至于把用户埋进数字里
DEFAULT_LIMIT = 5


def _pct(cur: float, prev: float) -> float | None:
    """同比变化百分比（保留 1 位小数）；上一年为 0 时无法定义，返回 ``None``。"""
    if prev == 0:
        return None
    return round((cur - prev) / abs(prev) * 100.0, 1)


def _series(year: int, dimension: str | None) -> dict[tuple[str, str, str], float]:
    """``(维度, 指标, 单位) -> 数值`` 的当年快照。"""
    out: dict[tuple[str, str, str], float] = {}
    for row in query_indicators(year=year, dimension=dimension):
        out[(str(row["dimension"]), str(row["indicator"]), str(row["unit"]))] = float(row["value"])
    return out


def movers(year: int, dimension: str, limit: int = DEFAULT_LIMIT) -> list[dict[str, object]]:
    """该维度同比变化最大的指标（按变化幅度降序，上行与下行都收）。"""
    cur = _series(year, dimension)
    prev = _series(year - 1, dimension)
    out: list[dict[str, object]] = []
    for key, value in cur.items():
        before = prev.get(key)
        if before is None:
            continue
        pct = _pct(value, before)
        if pct is None:
            continue
        dim, indicator, unit = key
        out.append({
            "indicator": indicator,
            "unit": unit,
            "dimension": dim,
            "value": value,
            "prev_value": before,
            "change_pct": pct,
        })
    out.sort(key=lambda m: (-abs(float(m["change_pct"])), str(m["indicator"])))
    return out[:limit]


def rank_shifts(year: int, limit: int = DEFAULT_LIMIT) -> dict[str, object]:
    """在**覆盖经济体最多**的指标上，名次同比变化最大的几个经济体。

    指标不写死：选当年覆盖最广的那个。这样库里补了新指标、换了主打指标，
    结论依然成立，代码不用改。
    """
    cur_rows = query_indicators(year=year)
    counts: dict[str, int] = {}
    for row in cur_rows:
        counts[str(row["indicator"])] = counts.get(str(row["indicator"]), 0) + 1
    if not counts:
        return {"indicator": None, "unit": None, "rows": []}
    indicator = max(sorted(counts), key=lambda k: counts[k])

    def _ranked(y: int) -> dict[str, tuple[int, float]]:
        rows = [r for r in query_indicators(year=y, indicator=indicator)]
        rows.sort(key=lambda r: -float(r["value"]))
        return {str(r["dimension"]): (i + 1, float(r["value"])) for i, r in enumerate(rows)}

    now = _ranked(year)
    before = _ranked(year - 1)
    unit = next((str(r["unit"]) for r in cur_rows if str(r["indicator"]) == indicator), "")
    rows: list[dict[str, object]] = []
    for dim, (rank_now, value) in now.items():
        prev_rank = before.get(dim, (None, 0.0))[0]
        if prev_rank is None:
            continue
        rows.append({
            "dimension": dim,
            "rank_now": rank_now,
            "rank_prev": prev_rank,
            "delta": prev_rank - rank_now,   # 正数 = 名次上升
            "value": value,
        })
    rows.sort(key=lambda s: (-abs(int(s["delta"])), str(s["dimension"])))
    return {"indicator": indicator, "unit": unit, "rows": rows[:limit]}


def coverage(year: int, dimension: str | None = None) -> dict[str, int]:
    """本维度当年的真实覆盖规模——这些计数本身就是洞察（数据到底有多全）。"""
    rows = query_indicators(year=year, dimension=dimension)
    prev_keys = {(str(r["dimension"]), str(r["indicator"]))
                 for r in query_indicators(year=year - 1, dimension=dimension)}
    cur_keys = {(str(r["dimension"]), str(r["indicator"])) for r in rows}
    return {
        "rows": len(rows),
        "economies": len({str(r["dimension"]) for r in rows}),
        "indicators": len({str(r["indicator"]) for r in rows}),
        "comparable": len(cur_keys & prev_keys),
    }


def build(year: int, dimension: str, limit: int = DEFAULT_LIMIT) -> dict[str, object]:
    """组装一份完整洞察（``/api/insights`` 的数据源）。"""
    return {
        "year": year,
        "prev_year": year - 1,
        "dimension": dimension,
        "movers": movers(year, dimension, limit),
        "rank_shifts": rank_shifts(year, limit),
        "coverage": coverage(year, dimension),
    }