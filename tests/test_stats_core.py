"""纯统计函数与公报数据构建的边界测试（离线，不起 socket）。

HANDOFF §6 曾把 ``yoy`` / ``share`` / ``rank_items`` / ``fmt_pct`` 标为「仍需补」——
这些函数直接决定对外数字，且边界（None / 除零 / 负数 / 并列）最容易出错，
一旦回归不会有任何报错，只会让页面上悄悄出现「—」或错位排名，因此值得单独锁住契约。
"""
from __future__ import annotations

import pytest

from src.stats.core import fmt_pct, rank_items, share, yoy


# ---------------------------------------------------------------------------
# yoy —— 同比增长率
# ---------------------------------------------------------------------------
def test_yoy_basic():
    assert yoy(110, 100) == 10.0
    assert yoy(100, 100) == 0.0


def test_yoy_rounds_to_two_decimals():
    assert yoy(1, 3) == pytest.approx(-66.67)


def test_yoy_none_and_zero_base():
    """基数为 0 / None，或被比较值缺失 → None（而不是抛 ZeroDivisionError）。"""
    assert yoy(100, 0) is None
    assert yoy(100, None) is None
    assert yoy(None, 100) is None


def test_yoy_negative_base():
    """负基数照常计算（-50 相对 -100 是 -50%），不因符号翻转而失真。"""
    assert yoy(-50, -100) == pytest.approx(-50.0)


# ---------------------------------------------------------------------------
# share —— 占比
# ---------------------------------------------------------------------------
def test_share_basic():
    assert share(25, 100) == 25.0
    assert share(1, 3) == pytest.approx(33.33)


def test_share_zero_total_is_none():
    assert share(10, 0) is None


def test_share_missing_parts():
    assert share(None, 100) is None
    assert share(10, None) is None


# ---------------------------------------------------------------------------
# rank_items —— 排名
# ---------------------------------------------------------------------------
def test_rank_items_descending_by_default():
    got = rank_items([("a", 1), ("b", 3), ("c", 2)])
    assert got == [("b", 3, 1), ("c", 2, 2), ("a", 1, 3)]


def test_rank_items_ascending():
    got = rank_items([("a", 1), ("b", 3), ("c", 2)], reverse=False)
    assert got == [("a", 1, 1), ("c", 2, 2), ("b", 3, 3)]


def test_rank_items_ties_get_sequential_ranks():
    """并列值按出现顺序拿 1、2 名（当前契约：不产生同名次）。

    决定这条行为的是「稳定排序 + enumerate」，改动实现时若需要竞赛排名语义
    （1,1,3）必须同步改这里，避免排行榜出现两人同名次却无人发现。
    """
    got = rank_items([("a", 5), ("b", 5), ("c", 1)])
    assert [r for _, _, r in got] == [1, 2, 3]
    assert [n for n, _, _ in got] == ["a", "b", "c"]


def test_rank_items_accepts_any_iterable():
    """入参是 Iterable（生成器也应可用），不要求 list。"""
    got = rank_items((n, v) for n, v in [("x", 2), ("y", 9)])
    assert got == [("y", 9, 1), ("x", 2, 2)]


def test_rank_items_empty():
    assert rank_items([]) == []


# ---------------------------------------------------------------------------
# fmt_pct —— 百分比展示
# ---------------------------------------------------------------------------
def test_fmt_pct_signs():
    assert fmt_pct(None) == "—"
    assert fmt_pct(10.0) == "+10.00%"
    assert fmt_pct(-3.5) == "-3.50%"
    # 零也带符号，保持列对齐
    assert fmt_pct(0) == "+0.00%"


# ---------------------------------------------------------------------------
# report.build_bulletin_data —— 结构化公报契约
# ---------------------------------------------------------------------------
def test_bulletin_data_structure(seeded_app):
    from src import report

    data = report.build_bulletin_data(2024, "中国", lang="en")
    assert data["year"] == 2024
    assert data["dimension"] == "中国"
    assert isinstance(data["sections"], list)
    assert data["sections"], "播种后 2024 年中国的公报不应为空"

    for sec in data["sections"]:  # type: ignore[union-attr]
        assert sec["category"] and isinstance(sec["rows"], list)
        for row in sec["rows"]:  # type: ignore[union-attr]
            assert set(row) == {"indicator", "value", "unit", "yoy", "note"}
            assert row["indicator"]
            # value 已格式化为带千分位的字符串，不是原始 float
            assert isinstance(row["value"], str)


def test_bulletin_data_ratio_unit_skips_yoy(seeded_app):
    """比例类单位（% 等）本身已是增速，不应再算一次同比 → yoy 留空字符串。"""
    from src import report

    data = report.build_bulletin_data(2024, "中国", lang="en")
    ratio_rows = [row for sec in data["sections"]  # type: ignore[union-attr]
                  for row in sec["rows"] if row["unit"] == "%"]
    assert ratio_rows, "中国 2024 应含百分比类指标（如 GDP 增速）"
    assert all(row["yoy"] == "" for row in ratio_rows)


def test_bulletin_data_unknown_dimension_is_empty_not_error(seeded_app):
    """未登记的维度原样透传 → 查不到数据 → 返回空 sections，绝不抛异常。

    与「未登记词条原样返回」是同一条向前兼容约定。
    """
    from src import report

    data = report.build_bulletin_data(2024, "Atlantis", lang="en")
    assert data["sections"] == []


def test_fmt_num_threshold():
    """< 1e6 保留两位小数，≥ 1e6 取整（避免长数字挤爆表格列）。"""
    from src import report

    assert report._fmt_num(1234.567) == "1,234.57"
    assert report._fmt_num(999999.5) == "999,999.50"
    assert report._fmt_num(2500000.0) == "2,500,000"
