"""数据层：用 SQLAlchemy 管理本地 SQLite 统计数据。

参考 agent_infini 的 `db` 子命令思路，但本地化实现，
无需云端后端即可运行。
"""
from __future__ import annotations

from pathlib import Path
import yaml
from sqlalchemy import (
    create_engine, Column, String, Float, Integer, MetaData, Table,
)
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import TypedDict


class IndicatorRow(TypedDict):
    """指标宽表的一行（与 indicators 表字段对应）。"""
    year: int
    category: str
    indicator: str
    dimension: str
    value: float
    unit: str
    note: str

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"

with CONFIG_PATH.open(encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

_DB_URL_RAW = CONFIG["database"]["url"]
if isinstance(_DB_URL_RAW, str):
    # 把相对路径解析到项目 data 目录
    if _DB_URL_RAW.startswith("sqlite:///") and not _DB_URL_RAW.startswith("sqlite:////"):
        DB_URL = "sqlite:///" + str(BASE_DIR / _DB_URL_RAW[len("sqlite:///"):])
    else:
        DB_URL = _DB_URL_RAW
else:
    DB_URL = "sqlite:///" + str(BASE_DIR / "data" / "qu_stat.db")

engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, future=True)
Base = declarative_base()


class Indicator(Base):
    """指标宽表：一条记录 = 某年某专业某指标某维度的值。"""
    __tablename__ = "indicators"
    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    category = Column(String(32), nullable=False, index=True)   # 工业/贸易/...
    indicator = Column(String(64), nullable=False, index=True)  # 指标名
    dimension = Column(String(64), nullable=False, default="全区")  # 街镇/园区
    value = Column(Float, nullable=False)
    unit = Column(String(16), default="")
    note = Column(String(128), default="")


def init_db() -> None:
    BASE_DIR.joinpath("data").mkdir(exist_ok=True)
    Base.metadata.create_all(engine)


def upsert_indicators(rows: list[IndicatorRow]) -> int:
    """批量写入指标；相同 (year,category,indicator,dimension) 覆盖更新。"""
    init_db()
    meta = MetaData()
    meta.reflect(bind=engine)
    table: Table = meta.tables["indicators"]
    with engine.begin() as conn:
        for r in rows:
            stmt = table.delete().where(
                (table.c.year == r["year"])
                & (table.c.category == r["category"])
                & (table.c.indicator == r["indicator"])
                & (table.c.dimension == r["dimension"])
            )
            conn.execute(stmt)
            conn.execute(table.insert().values(**r))
    return len(rows)


def query_indicators(year: int | None = None, category: str | None = None,
                      indicator: str | None = None,
                      dimension: str | None = None) -> list[IndicatorRow]:
    """按条件查询指标。使用 Core 表直读，避免 ORM 描述符类型推断问题。"""
    init_db()
    meta = MetaData()
    meta.reflect(bind=engine)
    table: Table = meta.tables["indicators"]
    stmt = table.select()
    if year is not None:
        stmt = stmt.where(table.c.year == year)
    if category is not None:
        stmt = stmt.where(table.c.category == category)
    if indicator is not None:
        stmt = stmt.where(table.c.indicator == indicator)
    if dimension is not None:
        stmt = stmt.where(table.c.dimension == dimension)
    with engine.connect() as conn:
        result = conn.execute(stmt)
        rows: list[IndicatorRow] = []
        for row in result:
            m = row._mapping
            rows.append(IndicatorRow(
                year=int(m["year"]),
                category=str(m["category"]),
                indicator=str(m["indicator"]),
                dimension=str(m["dimension"]),
                value=float(m["value"]),
                unit=str(m["unit"]),
                note=str(m["note"]),
            ))
        return rows
