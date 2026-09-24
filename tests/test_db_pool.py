"""连接池契约：连接必须被**复用**，而不是每次查询新建一条。

背景：``src/db.py`` 早先在 Vercel / Serverless 形态（``QU_STAT_DB_DIR`` 已设）下用
``NullPool``，理由是「避免跨请求句柄残留」——但那是**远程库**的经验
（连接可能被服务端回收）。本项目的 SQLite 库文件就在同一个实例自己的 /tmp 里，
不存在服务端回收；真有失效也由 ``pool_pre_ping=True`` 兜住。

代价却是每次查询都新建一条 SQLite 连接。同库、同查询的 A/B 实测
**1.57ms → 0.17ms**（约 9 倍）；按端点算（同一基准脚本、只切 poolclass）：

    /api/insights        4.77ms -> 0.99ms
    /api/overview        3.79ms -> 0.80ms
    /api/stats           3.60ms -> 0.98ms
    POST /api/knowledge  4.49ms -> 0.60ms

本文件把两件事钉住：
1. **池类别**：默认 QueuePool（本地与 Vercel 一致），``QU_STAT_DB_POOL=null`` 可退回；
2. **行为**：连续多次查询只新建极少数连接——这是优化的本体，比断言类名更重要。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from sqlalchemy import event

from src.db import engine, init_db, query_indicators

ROOT = Path(__file__).resolve().parents[1]

#: 连续查询多少次
_N_QUERIES = 25
#: 容忍新建几条连接（池会预热 / 溢出时扩容，但绝不等于查询次数）
_MAX_NEW_CONNECTIONS = 5


def _run_in_subprocess(code: str, env_extra: dict[str, str]) -> str:
    """在干净子进程里执行代码并回传 stdout（用于断言**导入期**的引擎形态）。

    ``src.db.engine`` 在模块加载时就按环境变量定型，进程内改环境变量没用，
    必须像 ``tests/test_cold_start.py`` 那样起新解释器。
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=ROOT, env=env,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        raise AssertionError(
            f"子进程执行失败（exit {proc.returncode}）：{' | '.join(tail)}\n"
            f"执行的代码：{code}"
        )
    return proc.stdout.strip()


def _pool_name(env_extra: dict[str, str]) -> str:
    return _run_in_subprocess(
        "import src.db\n"
        "print(type(src.db.engine.pool).__name__)\n",
        env_extra,
    )


# ---------------------------------------------------------------------------
# 池类别：默认复用，应急开关可退回
# ---------------------------------------------------------------------------
def test_vercel_form_uses_a_reusable_pool_by_default():
    """Vercel 形态（QU_STAT_DB_DIR 已设）默认必须是 QueuePool。

    这条是本次优化的核心断言：改回 NullPool 会直接红。
    """
    assert _pool_name({"QU_STAT_DB_DIR": tempfile.mkdtemp()}) == "QueuePool"


def test_local_form_uses_a_reusable_pool():
    """本地形态（无 QU_STAT_DB_DIR）同样是 QueuePool。"""
    assert _pool_name({"QU_STAT_DB_DIR": ""}) == "QueuePool"


def test_escape_hatch_falls_back_to_null_pool():
    """``QU_STAT_DB_POOL=null`` 保留退回 NullPool 的应急通道（线上免改代码）。"""
    db_dir = tempfile.mkdtemp()
    assert _pool_name(
        {"QU_STAT_DB_DIR": db_dir, "QU_STAT_DB_POOL": "null"}
    ) == "NullPool"


def test_escape_hatch_is_case_insensitive():
    """应急开关不挑大小写——排查时少一个坑。"""
    db_dir = tempfile.mkdtemp()
    assert _pool_name(
        {"QU_STAT_DB_DIR": db_dir, "QU_STAT_DB_POOL": "NULL"}
    ) == "NullPool"


def test_unknown_pool_value_falls_back_to_reuse():
    """拼错值不能静默变成 NullPool——按「复用」这个安全默认走。"""
    db_dir = tempfile.mkdtemp()
    assert _pool_name(
        {"QU_STAT_DB_DIR": db_dir, "QU_STAT_DB_POOL": "quue"}
    ) == "QueuePool"


def test_a_pooled_connection_works_from_another_thread():
    """``check_same_thread=False`` 必须仍在。

    Flask 默认多线程处理请求，池里的连接可能被交给创建它的那个线程之外的线程。
    少了这个参数，sqlite3 会抛
    ``ProgrammingError: SQLite objects created in a thread can only be used in that
    same thread``——行为级断言比查 private 属性更贴近真实故障。
    """
    init_db()
    with engine.connect() as conn:
        assert conn.exec_driver_sql("select 1").scalar() == 1
        errors: list[BaseException] = []

        def _use_from_other_thread() -> None:
            try:
                assert conn.exec_driver_sql("select 1").scalar() == 1
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        worker = threading.Thread(target=_use_from_other_thread)
        worker.start()
        worker.join()
        assert not errors, errors


def test_pre_ping_recovers_from_a_stale_connection():
    """``pool_pre_ping=True`` 必须仍在。

    Serverless 实例会被冻结再解冻，池里的连接可能已失效；探活失败的连接应被
    静默换掉，而不是把异常抛给调用方。（换成 NullPool 时这条也会红——
    NullPool 不复用连接，谈不上探活自愈。）
    """
    init_db()
    with engine.connect() as conn:
        # 直接关掉底层 sqlite3 连接，模拟「池里还在、实际已失效」
        conn.connection.dbapi_connection.close()
    # 下一次取用必须拿到一条能用的连接
    with engine.connect() as conn:
        assert conn.exec_driver_sql("select 1").scalar() == 1


def test_connections_are_reused_across_queries():
    """连续 N 次查询只应新建极少数连接——这是优化的本体。

    用 ``connect`` 事件数**真实 DBAPI 连接**的创建次数。NullPool 下这个数
    会等于查询次数（每次都新建），所以这条用例同时是「没悄悄退回 NullPool」的
    行为级守卫。
    """
    init_db()
    created: list[int] = []

    def _on_connect(dbapi_conn, connection_record):  # noqa: ANN001, ARG001
        created.append(1)

    event.listen(engine, "connect", _on_connect)
    try:
        for _ in range(_N_QUERIES):
            query_indicators(year=2024)
    finally:
        event.remove(engine, "connect", _on_connect)

    assert len(created) <= _MAX_NEW_CONNECTIONS, (
        f"{_N_QUERIES} 次查询新建了 {len(created)} 条连接，连接没有被复用"
    )


def test_no_connection_leaks_after_queries():
    """查询全部结束后不能有连接卡在 checkedout 状态（否则池会被抽干）。"""
    init_db()
    for _ in range(_N_QUERIES):
        query_indicators(year=2024)
    assert engine.pool.checkedout() == 0
