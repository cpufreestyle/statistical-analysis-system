"""pytest 公共 fixture：把测试库隔离到临时目录，并提供 Flask app 与离线播种。

为什么需要这个文件
------------------
``src.db`` 在导入时按 ``config.yaml`` 的 ``database.url`` 把 SQLite 落到
``data/qu_stats.db``（被 .gitignore 忽略，CI 上没有它）。为了让测试：
1. 不污染开发者本机真实的 ``data/qu_stats.db``；
2. 在 CI 上从零自建、且完全离线（种子数据来自被跟踪的 data/*.csv），

这里在**导入任何 src 模块之前**设置 ``QU_STAT_DB_DIR``（``db.py`` 认识这个变量，
会改用给定目录下的 SQLite，且 CONFIG 退化为空字典——更接近 Vercel 生产形态）。
"""
from __future__ import annotations

import os
import tempfile

# 必须在 import src.* 之前设置，否则 db.py 在模块加载时就锁定了数据库路径。
os.environ.setdefault("QU_STAT_DB_DIR", tempfile.mkdtemp(prefix="qu_stat_test_"))


import pytest


@pytest.fixture()
def app():
    """导入 Flask app（模块级单例）。"""
    from src import web

    return web.app


@pytest.fixture()
def client(app):
    """Flask 测试客户端（不真正起 socket）。"""
    return app.test_client()


@pytest.fixture()
def seeded_app(app):
    """确保测试库已播种真实公开数据（离线、幂等）。

    ``data/qu_stats.db`` 在 CI 上不存在 → count==0 → 从 data/*.csv 灌入；
    本机已有数据则跳过，不覆盖。返回 app 供测试客户端使用。
    """
    from src.db import count_indicators
    from src.loader import load_seed_data

    if count_indicators() == 0:
        load_seed_data()
    return app


@pytest.fixture()
def seeded_client(seeded_app):
    return seeded_app.test_client()
