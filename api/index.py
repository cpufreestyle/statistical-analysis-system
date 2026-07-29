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

from src.web import app  # noqa: E402

# 冷启动时创建表并注入示例数据 + 种子知识
from src.db import init_db  # noqa: E402
init_db()

from src import knowledge as kb  # noqa: E402
kb.seed_default_knowledge()

from src.loader import generate_sample_data  # noqa: E402
generate_sample_data(2024)

# Vercel 需要的 WSGI 入口
application = app
