"""通用统计工具：同比、占比、排名、汇总。"""
from __future__ import annotations

from collections.abc import Iterable


def yoy(current: float | None, previous: float | None) -> float | None:
    """同比增长率(%)。基数为 0/None 返回 None。"""
    if previous in (0, None) or current is None:
        return None
    return round((current - previous) / previous * 100, 2)


def share(part: float | None, total: float | None) -> float | None:
    """占比(%)。"""
    if total is None or part is None or not total:
        return None
    return round(part / total * 100, 2)


def rank_items(items: Iterable[tuple[str, float]], reverse: bool = True) -> list[tuple[str, float, int]]:
    """返回 [(维度, 值, 排名)]。"""
    ordered = sorted(items, key=lambda x: x[1], reverse=reverse)
    return [(name, val, i + 1) for i, (name, val) in enumerate(ordered)]


def summarize(values: list[float]) -> dict[str, object]:
    if not values:
        return {"count": 0, "sum": 0.0, "mean": 0.0, "max": 0.0, "min": 0.0}
    return {
        "count": len(values),
        "sum": round(sum(values), 2),
        "mean": round(sum(values) / len(values), 2),
        "max": max(values),
        "min": min(values),
    }


def fmt_pct(v: float | None) -> str:
    return "—" if v is None else f"{v:+.2f}%"
