"""数据层：用 SQLAlchemy Core 管理本地 SQLite 指标宽表。

参考 agent_infini 的 `db` 子命令思路，本地化实现，无需云端后端。
"""
from __future__ import annotations

from pathlib import Path
import os
import yaml
from sqlalchemy import (
    create_engine, Column, String, Float, Integer, MetaData, Table, Text,
    func, select,
)
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

_VERCEL_DB_DIR = os.environ.get("QU_STAT_DB_DIR")
if _VERCEL_DB_DIR:
    # Vercel / Serverless：仅 /tmp 可写，经环境变量 QU_STAT_DB_DIR 指定路径
    _vercel_data = Path(_VERCEL_DB_DIR)
    _vercel_data.mkdir(parents=True, exist_ok=True)
    DB_URL = "sqlite:///" + str(_vercel_data / "qu_stats.db")
else:
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
METADATA = MetaData()
INDICATORS = Table(
    "indicators", METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("year", Integer, nullable=False, index=True),
    Column("category", String(32), nullable=False, index=True),   # 工业/贸易/...
    Column("indicator", String(64), nullable=False, index=True),  # 指标名
    Column("dimension", String(64), nullable=False, default="全国"),  # 省份/国家/全国
    Column("value", Float, nullable=False),
    Column("unit", String(16), default=""),
    Column("note", String(128), default=""),
)

# 知识库表：存放指标口径、统计定义、政策与方法论说明等结构化文档。
# 与 indicators 共用同一 SQLite 库，便于「数据 + 知识」本地一体化。
KNOWLEDGE = Table(
    "knowledge", METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("title", String(128), nullable=False),
    Column("category", String(32), nullable=False, default="通用", index=True),
    Column("tags", String(128), default=""),          # 逗号分隔的关键词，供检索
    Column("content", Text, nullable=False),
    Column("source", String(64), default=""),         # 出处（如：统计公报/制度方法）
)


def init_db() -> None:
    BASE_DIR.joinpath("data").mkdir(exist_ok=True)
    METADATA.create_all(engine)


def upsert_indicators(rows: list[IndicatorRow]) -> int:
    """批量写入指标；相同 (year,category,indicator,dimension) 覆盖更新。"""
    init_db()
    with engine.begin() as conn:
        for r in rows:
            conn.execute(
                INDICATORS.delete().where(
                    (INDICATORS.c.year == r["year"])
                    & (INDICATORS.c.category == r["category"])
                    & (INDICATORS.c.indicator == r["indicator"])
                    & (INDICATORS.c.dimension == r["dimension"])
                )
            )
            conn.execute(INDICATORS.insert().values(**r))
    return len(rows)


def query_indicators(year: int | None = None, category: str | None = None,
                      indicator: str | None = None,
                      dimension: str | None = None) -> list[IndicatorRow]:
    """按条件查询指标（Core 表直读，避免 ORM 描述符类型推断问题）。"""
    init_db()
    stmt = INDICATORS.select()
    if year is not None:
        stmt = stmt.where(INDICATORS.c.year == year)
    if category is not None:
        stmt = stmt.where(INDICATORS.c.category == category)
    if indicator is not None:
        stmt = stmt.where(INDICATORS.c.indicator == indicator)
    if dimension is not None:
        stmt = stmt.where(INDICATORS.c.dimension == dimension)
    with engine.connect() as conn:
        return [
            IndicatorRow(
                year=int(m["year"]),
                category=str(m["category"]),
                indicator=str(m["indicator"]),
                dimension=str(m["dimension"]),
                value=float(m["value"]),
                unit=str(m["unit"]),
                note=str(m["note"]),
            )
            for m in (row._mapping for row in conn.execute(stmt))
        ]


def count_indicators() -> int:
    """指标宽表当前行数（用于 db info 展示）。"""
    init_db()
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(INDICATORS)).scalar() or 0)


def db_info() -> dict[str, object]:
    """返回数据库运行状态概览（路径、引擎、大小、各表行数）。"""
    init_db()
    # 解析 sqlite 文件路径（相对 url 已在前处理为绝对）
    path = DB_URL[len("sqlite:///"):] if DB_URL.startswith("sqlite:///") else ""
    size = os.path.getsize(path) if path and os.path.exists(path) else 0
    with engine.connect() as conn:
        kcount = int(conn.execute(select(func.count()).select_from(KNOWLEDGE)).scalar() or 0)
    return {
        "url": DB_URL,
        "path": path,
        "exists": bool(path and os.path.exists(path)),
        "size_bytes": size,
        "engine": engine.dialect.name,
        "tables": ["indicators", "knowledge"],
        "indicator_rows": count_indicators(),
        "knowledge_rows": kcount,
    }
