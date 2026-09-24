"""导入与批量写入契约：upsert_indicators 的 executemany 路径 + load_file 校验。

背景：upsert_indicators 原先**逐行** execute，每一行都要重走一遍 SQLAlchemy 的
语句编译，729 行种子数据实测 206.6ms。改为单条 ``ON CONFLICT DO UPDATE`` 的
executemany 后降到 8.9ms（约 23 倍）。性能改动最容易悄悄改坏语义，所以这里把
「写了多少行 / 重写是否幂等 / 同自然键是更新还是新增 / 无唯一索引时的回退路径」
逐条钉住。

load_file 侧钉住另一类回归：原先它把 DataFrame 记录**直接 cast** 成 IndicatorRow，
用户传错文件时会在数据库层炸出原始异常，或者更糟——静默写入垃圾。
"""
from __future__ import annotations

import logging

import pytest

from src.db import (
    INDICATORS, count_indicators, engine, init_db, query_indicators,
    upsert_indicators,
)
from src.loader import _coerce_row, load_file, load_seed_data
from sqlalchemy import delete, text


@pytest.fixture()
def clean_indicators():
    """清空 indicators 表；用例结束后重新灌入真实种子数据。

    先 ``init_db()``：单独跑本文件时还没人建过表，直接 DELETE 会报 no such table。
    本文件多个用例会改写表内容，显式恢复比依赖 seeded_client 的自愈更稳。
    """
    init_db()
    with engine.begin() as conn:
        conn.execute(delete(INDICATORS))
    yield
    load_seed_data()


def _row(year: int, value: float, *, category: str = "国民经济",
         indicator: str = "GDP", dimension: str = "中国") -> dict[str, object]:
    return {"year": year, "category": category, "indicator": indicator,
            "dimension": dimension, "value": value, "unit": "%", "note": "t"}


def _natural_key(row: dict[str, object]) -> tuple[object, ...]:
    return (row["year"], row["category"], row["indicator"], row["dimension"])


# ---------------------------------------------------------------------------
# upsert_indicators —— executemany 路径
# ---------------------------------------------------------------------------
def test_upsert_empty_input_is_a_noop(clean_indicators):
    """空输入必须短路返回 0，不能为了「走一遍流程」去连库建事务。"""
    assert upsert_indicators([]) == 0
    assert count_indicators() == 0


def test_upsert_writes_every_row(clean_indicators):
    rows = [_row(2024, 1.0), _row(2024, 2.0, indicator="CPI"), _row(2023, 3.0)]
    assert upsert_indicators(rows) == 3
    assert count_indicators() == 3
    assert sorted(r["value"] for r in query_indicators()) == [1.0, 2.0, 3.0]


def test_upsert_is_idempotent(clean_indicators):
    """同一批数据重复写入：行数不变、载荷逐字段一致（不能悄悄翻倍或漂移）。"""
    rows = [_row(2024, 1.0), _row(2024, 2.0, indicator="CPI"), _row(2023, 3.0)]
    upsert_indicators(rows)
    def snapshot():
        return sorted((r["year"], r["category"], r["indicator"], r["dimension"],
                       r["value"], r["unit"], r["note"])
                      for r in query_indicators())

    before = snapshot()
    assert upsert_indicators(rows) == 3
    assert count_indicators() == 3
    assert before == snapshot()


def test_upsert_updates_existing_natural_key(clean_indicators):
    """同 (year,category,indicator,dimension) 必须**更新**，不能新增一行。"""
    base = _row(2024, 1.0)
    upsert_indicators([base])
    assert count_indicators() == 1

    assert upsert_indicators([dict(base, value=99.5, unit="ZZ", note="patched")]) == 1
    assert count_indicators() == 1, "同自然键被写成了第二行"
    stored = query_indicators()[0]
    assert stored["value"] == 99.5 and stored["unit"] == "ZZ"
    assert stored["note"] == "patched"


def test_upsert_fallback_path_matches_conflict_path(clean_indicators):
    """唯一索引不存在时的「逐行删除+插入」回退路径必须与 ON CONFLICT 路径等价。"""
    rows = [_row(2024, 1.0), _row(2024, 2.0, indicator="CPI")]
    upsert_indicators(rows)
    patched = dict(_row(2024, 99.5), unit="ZZ", note="patched")

    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ux_indicators_key"))
    try:
        before = count_indicators()
        assert upsert_indicators([patched]) == 1
        after = count_indicators()
        stored = [r for r in query_indicators()
                  if _natural_key(r) == _natural_key(patched)]
    finally:
        init_db(force=True)  # 重建索引，别把无索引状态留给后续用例

    assert before == after, "回退路径也没有新增行"
    assert stored and stored[0]["value"] == 99.5
    assert stored and stored[0]["unit"] == "ZZ"


# ---------------------------------------------------------------------------
# _coerce_row / load_file —— 导入校验
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [
    {"year": "x", "category": "c", "indicator": "i", "dimension": "d", "value": "1"},
    {"year": "2024", "category": "c", "indicator": "i", "dimension": "d", "value": "x"},
    {"year": "2024", "category": "c", "indicator": "i", "dimension": "d", "value": "inf"},
    {"year": "2024", "category": "c", "indicator": "i", "dimension": "d", "value": "nan"},
    {"year": "2024", "category": "c", "indicator": "i", "value": "1"},
    {"category": "c", "indicator": "i", "dimension": "d", "value": "1"},
    {"year": "", "category": "c", "indicator": "i", "dimension": "d", "value": "1"},
])
def test_coerce_row_rejects_unusable_rows(bad):
    """必需列缺失 / 数值不可解析 / 数值非有限 → None（绝不写进库）。"""
    assert _coerce_row(bad) is None


def test_coerce_row_accepts_and_normalises():
    row = _coerce_row({"year": " 2024 ", "category": " 国民经济 ", "indicator": "GDP",
                       "dimension": "中国", "value": " 18.7 ", "unit": " % ",
                       "note": " World Bank "})
    assert row == {"year": 2024, "category": "国民经济", "indicator": "GDP",
                  "dimension": "中国", "value": 18.7, "unit": "%",
                  "note": "World Bank"}


def test_coerce_row_treats_pandas_nan_optional_columns_as_empty():
    """pandas 的缺失单元格是 float('nan')，必须归一成空串而不是字面量 nan。"""
    assert _coerce_row({"year": 2024, "category": "c", "indicator": "i",
                        "dimension": "d", "value": 1.0, "unit": float("nan"),
                        "note": float("nan")}) == {
        "year": 2024, "category": "c", "indicator": "i", "dimension": "d",
        "value": 1.0, "unit": "", "note": ""}


CSV_HEAD = "year,category,indicator,dimension,value,unit,note\n"
CSV_GOOD = CSV_HEAD + "2024,国民经济,GDP,中国,18.7,%,World Bank\n"
CSV_MIXED = CSV_HEAD + (
    "2024,国民经济,GDP,中国,18.7,%,ok\n"
    "notayear,国民经济,GDP,中国,1.0,%,bad year\n"
    "2024,国民经济,GDP,中国,notanumber,%,bad value\n"
    "2024,国民经济,GDP,中国,inf,%,non finite\n"
    "2024,国民经济,GDP,中国,,%,empty value\n"
    ",国民经济,GDP,中国,1.0,%,empty year\n"
    "2024,国民经济,GDP,中国,2.0,%,ok again\n"
)


def _write(tmp_path, name: str, body: str) -> str:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_load_file_skips_unusable_rows_and_logs_the_count(tmp_path, clean_indicators,
                                                         caplog):
    """坏行被跳过、好行照常写入，且**必须在日志里报数**——不能静默丢弃。"""
    path = _write(tmp_path, "mixed.csv", CSV_MIXED)
    with caplog.at_level(logging.WARNING, logger="src.loader"):
        written = load_file(path)
    assert written == 2  # 18.7 与 2.0（同自然键，后者覆盖前者）
    assert count_indicators() == 1
    assert [r["value"] for r in query_indicators()] == [2.0]
    assert "跳过" in caplog.text and "5 / 7" in caplog.text


def test_load_file_raises_when_nothing_is_usable(tmp_path, clean_indicators):
    """整份文件都不可用时抛 ValueError，而不是返回 0 让用户以为成功了。"""
    path = _write(tmp_path, "wrong.csv", "foo,bar\n1,2\n")
    with pytest.raises(ValueError, match="全部不可用"):
        load_file(path)
    assert count_indicators() == 0


def test_load_file_round_trips_clean_csv(tmp_path, clean_indicators):
    path = _write(tmp_path, "good.csv", CSV_GOOD)
    assert load_file(path) == 1
    stored = query_indicators()[0]
    assert stored["value"] == 18.7 and stored["unit"] == "%"
    assert stored["note"] == "World Bank"


def test_load_file_round_trips_excel(tmp_path, clean_indicators):
    """Excel 分支共用同一套校验，不能被漏掉。"""
    pd = pytest.importorskip("pandas")
    xlsx = tmp_path / "good.xlsx"
    pd.read_csv(_write(tmp_path, "src.csv", CSV_GOOD)).to_excel(xlsx, index=False)
    assert load_file(str(xlsx)) == 1
    assert query_indicators()[0]["value"] == 18.7

