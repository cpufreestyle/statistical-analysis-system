"""数据层：用 SQLAlchemy Core 管理本地 SQLite 指标宽表。

参考 agent_infini 的 `db` 子命令思路，本地化实现，无需云端后端。

附带数据库层优化（对外签名与返回结构保持不变）：
- **索引**：自然键复合唯一索引 ``ux_indicators_key(year,category,indicator,dimension)``
  + 维度索引 ``ix_indicators_dimension``；**保留**窄单列 ``ix_indicators_year``
  （实测：纯按年查询用窄索引更快，删之会带来 by_year 回退；写入代价极小）。

- **写入**：``upsert_indicators`` 采用 ``INSERT ... ON CONFLICT DO UPDATE``（写次数减半）。
- **连接调优**：SQLite 逐项设置 WAL / synchronous=NORMAL / 内存临时表 /
  大页缓存 / mmap / busy_timeout 等 PRAGMA（逐条容错，受限环境自动跳过）。
- **幂等迁移**：``init_db()`` 建表后执行 ``_ensure_indexes()``，全部 ``IF NOT EXISTS``，
  重复执行安全；若历史数据存在重复自然键，则跳过唯一索引创建、不抛错。
"""
from __future__ import annotations

from pathlib import Path
import os
from sqlalchemy import (
    create_engine, Column, String, Float, Integer, MetaData, Table, Text,
    event, func, select, text,
)
from sqlalchemy.pool import NullPool, QueuePool
from typing import Any, TypedDict



class IndicatorRow(TypedDict):
    """指标宽表的一行（与 indicators 表字段对应）。"""
    year: int
    category: str
    indicator: str
    dimension: str
    value: float
    unit: str
    note: str


class DbInfo(TypedDict):
    """:func:`db_info` 的返回结构。字段类型各异，用精确类型而非 ``dict[str, object]``，
    好让 ``int(info["indicator_rows"])`` 这类消费点在类型层面可查。"""
    url: str
    path: str
    exists: bool
    size_bytes: int
    engine: str
    tables: list[str]
    indicator_rows: int
    knowledge_rows: int


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"

_VERCEL_DB_DIR = os.environ.get("QU_STAT_DB_DIR")
if _VERCEL_DB_DIR:
    # Vercel / Serverless：仅 /tmp 可写，经环境变量 QU_STAT_DB_DIR 指定路径
    _vercel_data = Path(_VERCEL_DB_DIR)
    _vercel_data.mkdir(parents=True, exist_ok=True)
    DB_URL = "sqlite:///" + str(_vercel_data / "qu_stats.db")
    CONFIG: dict[str, Any] = {}  # Vercel 环境无 config.yaml，用空字典兜底
else:
    # 延迟导入 PyYAML：Vercel 分支（QU_STAT_DB_DIR）不读 config.yaml，
    # 冷启动不必为一次都不会执行的解析加载整个 yaml 包。
    import yaml

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

# 连接池（D1）：显式声明，避免默认值在 Serverless / 多线程下的隐性开销。
# - check_same_thread=False：允许 Flask 多线程请求复用连接（标准做法）。
# - pool_pre_ping=True：取用前探活，规避长时间空闲后的失效连接。
# - Vercel（QU_STAT_DB_DIR 存在，落在 /tmp）：用 NullPool，避免跨请求句柄残留。
# - 本地/容器：QueuePool，复用连接（5 + 10 溢出）。
_IS_SQLITE = DB_URL.startswith("sqlite")
_engine_kwargs: dict[str, Any] = {"future": True}
if _IS_SQLITE:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["pool_pre_ping"] = True
    if _VERCEL_DB_DIR:
        _engine_kwargs["poolclass"] = NullPool
    else:
        _engine_kwargs["poolclass"] = QueuePool
        _engine_kwargs["pool_size"] = 5
        _engine_kwargs["max_overflow"] = 10

engine = create_engine(DB_URL, **_engine_kwargs)
METADATA = MetaData()

INDICATORS = Table(
    "indicators", METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # 注：year 的窄索引在 _ensure_indexes() 中以显式 SQL 建立（保持查询计划最优）。
    Column("year", Integer, nullable=False, index=False),

    Column("category", String(32), nullable=False, index=True),   # 工业/贸易/...
    Column("indicator", String(64), nullable=False, index=True),  # 指标名
    Column("dimension", String(64), nullable=False, default="亚太"),  # 经济体/国家/亚太
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


# ---------------------------------------------------------------------------
# 连接级 PRAGMA 调优（仅 SQLite；逐条容错，失败静默，绝不影响可用性）
# ---------------------------------------------------------------------------
if engine.dialect.name == "sqlite":
    _SQLITE_PRAGMAS: tuple[str, ...] = (
        "PRAGMA journal_mode=WAL",       # 读写并发（读不阻塞写，写不阻塞读）
        "PRAGMA synchronous=NORMAL",     # 速度与安全平衡（WAL 下推荐）
        "PRAGMA temp_store=MEMORY",      # 临时表 / 排序走内存
        "PRAGMA cache_size=-64000",      # 约 64MB 页缓存（负值 = KB 单位）
        "PRAGMA mmap_size=268435456",    # 256MB 内存映射（支持时生效）
        "PRAGMA busy_timeout=30000",     # 30s 锁等待，缓解 "database is locked"
        "PRAGMA foreign_keys=ON",        # 外键约束（防御性，当前表无 FK）
    )

    @event.listens_for(engine, "connect")
    def _apply_sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:  # noqa: ANN401
        """每条 PRAGMA 独立 try/except：只读库 / 内存库 / 受限文件系统下自动跳过。"""
        try:
            cur = dbapi_conn.cursor()
        except Exception:  # noqa: BLE001
            return
        for pragma in _SQLITE_PRAGMAS:
            try:
                cur.execute(pragma)
            except Exception:  # noqa: BLE001 - 单条失败不影响其余
                continue
        try:
            cur.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# 幂等索引迁移
# ---------------------------------------------------------------------------
_UNIQUE_KEY_INDEX = "ux_indicators_key"
_DIM_INDEX = "ix_indicators_dimension"
_YEAR_INDEX = "ix_indicators_year"



def _index_exists(conn: Any, name: str) -> bool:  # noqa: ANN401
    try:
        row = conn.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='index' AND name=:n"),
            {"n": name},
        ).first()
        return row is not None
    except Exception:  # noqa: BLE001
        return False


def _has_duplicate_natural_keys(conn: Any) -> bool:  # noqa: ANN401
    """自然键是否有重复——有重复则不建唯一索引（避免迁移失败）。"""
    try:
        dup = conn.execute(
            text("SELECT COUNT(*) FROM (SELECT 1 FROM indicators "
                 "GROUP BY year, category, indicator, dimension HAVING COUNT(*) > 1)")
        ).scalar()
        return bool(dup)
    except Exception:  # noqa: BLE001
        return True  # 无法判定时按「有重复」处理，保守跳过


def _ensure_indexes() -> None:
    """建/调索引（幂等）。仅 SQLite；任何失败都静默，保证既有部署不受影响。"""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        # 1) 自然键复合唯一索引（同时强制唯一性）
        if not _has_duplicate_natural_keys(conn):
            try:
                conn.execute(text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {_UNIQUE_KEY_INDEX} "
                    "ON indicators (year, category, indicator, dimension)"))
            except Exception:  # noqa: BLE001
                pass
        # 2) 维度索引：消除 WHERE dimension=? 的全表扫描
        try:
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS {_DIM_INDEX} ON indicators (dimension)"))
        except Exception:  # noqa: BLE001
            pass
        # 3) 保留窄单列年索引：实测纯按年查询用窄索引更快（删之会带来 by_year 回退），
        #    写入代价极小（2000 行仅 +0.5ms），故确保其存在。
        try:
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS {_YEAR_INDEX} ON indicators (year)"))
        except Exception:  # noqa: BLE001
            pass



#: 进程内初始化标志（R1）。热请求跳过 create_all/索引检查；Vercel 冷启动是新进程，
#: 标志位自然重置 → 仍会建表（期望行为）。如需运行期重建，调用 init_db(force=True)。
_INITIALIZED = False


def init_db(force: bool = False) -> None:
    global _INITIALIZED
    if _INITIALIZED and not force:
        return
    if not _VERCEL_DB_DIR:
        # 本地环境：确保 data 目录存在；Vercel /tmp 已在模块加载时创建
        BASE_DIR.joinpath("data").mkdir(exist_ok=True)
    METADATA.create_all(engine)
    _ensure_indexes()
    _INITIALIZED = True



def _sync_indicators_to_kv() -> None:
    """将 indicators 全量导出到 Vercel KV。"""
    from src.kv_store import kv_available, kv_set_json
    if not kv_available():
        return
    with engine.connect() as conn:
        rows = [
            dict(r._mapping)
            for r in conn.execute(INDICATORS.select())
        ]
    kv_set_json("qu_stat_ap:indicators", rows)


def upsert_indicators(rows: list[IndicatorRow]) -> int:
    """批量写入指标；相同 (year,category,indicator,dimension) 覆盖更新。

    SQLite 且唯一索引可用时走 ``ON CONFLICT DO UPDATE``（单次写入）；
    其余情况回退「删除+插入」，语义完全一致。
    """
    init_db()
    from sqlalchemy.dialects.sqlite import insert as _sqlite_insert

    use_conflict = False
    if engine.dialect.name == "sqlite":
        with engine.connect() as probe:
            use_conflict = _index_exists(probe, _UNIQUE_KEY_INDEX)

    with engine.begin() as conn:
        for r in rows:
            if use_conflict:
                try:
                    stmt = _sqlite_insert(INDICATORS).values(**r)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["year", "category", "indicator", "dimension"],
                        set_={"value": stmt.excluded.value,
                              "unit": stmt.excluded.unit,
                              "note": stmt.excluded.note},
                    )
                    conn.execute(stmt)
                    continue
                except Exception:  # noqa: BLE001 - 冲突升级时回退
                    pass
            # 回退：先删后插（原行为）
            conn.execute(
                INDICATORS.delete().where(
                    (INDICATORS.c.year == r["year"])
                    & (INDICATORS.c.category == r["category"])
                    & (INDICATORS.c.indicator == r["indicator"])
                    & (INDICATORS.c.dimension == r["dimension"])
                )
            )
            conn.execute(INDICATORS.insert().values(**r))
    _sync_indicators_to_kv()
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


def db_info() -> DbInfo:
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