"""Vercel Serverless 入口：启动时检测运行环境，初始化数据库并导出 Flask app。

Vercel 上仅 /tmp 可写，SQLite 数据不持久化（每次冷启动重建）。
演示/比赛用途已足够——评委可直接访问看板体验数据分析与知识库功能。
"""
import os
import sys

# Vercel 环境：数据库与配置缓存一律写入 /tmp
VERCEL_DB_DIR = "/tmp/data"
os.makedirs(VERCEL_DB_DIR, exist_ok=True)
os.environ["QU_STAT_DB_DIR"] = VERCEL_DB_DIR

# 将项目根路径加入 sys.path（Vercel 已自动包含，此处作为兜底）
_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj not in sys.path:
    sys.path.insert(0, _proj)

try:
    from src.web import app, _ensure_data  # noqa: E402

    # 冷启动时创建表：优先从 KV 恢复持久化数据，否则播种亚太示例数据
    _ensure_data()
except Exception:
    # 详情（堆栈含绝对路径与环境信息）只进运行日志，不回给访客；
    # Vercel 的函数日志面板里能看到完整原因
    import logging
    import traceback
    logging.getLogger(__name__).error("startup failed:\n%s", traceback.format_exc())
    from flask import Flask as _Flask
    app = _Flask(__name__)

    @app.route("/")
    @app.route("/<path:path>")
    def _startup_error(path: str = "") -> str:
        return ("Service temporarily unavailable. / 服务暂时不可用，请稍后重试。"), 500

# Vercel 需要的 WSGI 入口
application = app
