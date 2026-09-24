"""冷启动导入卫生：Web 入口不该为一次都用不到的依赖付费。

Vercel 是 Serverless，每个冷容器都要完整跑一遍 ``import src.web``，所以模块**顶层**
的 import 在这里是实打实的启动开销（实测 ``import src.web`` 约 330ms CPU）。
Python 的 import 只分「顶层」和「函数内」两种写法，没有按需加载的中间态，
因此可选依赖必须放进真正调用它的函数里——``src/stats/sql_engine.py`` 早有先例。

本文件用**子进程在全新解释器**里断言导入图：pytest 自身（以及
``tests/test_analyzer.py``）已经加载过 requests / PyYAML，在进程内查
``sys.modules`` 是查不出问题的。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 只在 Upstash KV / 云端 AI 的 HTTP 调用里才用得到的依赖树
_HTTP_ONLY_DEPS = ("requests", "urllib3")


@lru_cache(maxsize=1)
def _vercel_form_modules() -> list[str]:
    """Vercel 形态（``QU_STAT_DB_DIR`` 已设）下 import src.web 加载的顶层包名。"""
    db_dir = os.environ.get("QU_STAT_DB_DIR") or tempfile.mkdtemp(
        prefix="qu_stat_coldstart_")
    return _imported_top_levels({"QU_STAT_DB_DIR": db_dir})


@lru_cache(maxsize=1)
def _local_form_modules() -> list[str]:
    """本地形态（无 ``QU_STAT_DB_DIR``）下 import src.web 加载的顶层包名。"""
    return _imported_top_levels({"QU_STAT_DB_DIR": ""})


def _check_ran(proc: subprocess.CompletedProcess[str], code: str) -> None:
    """子进程非 0 退出时把 stderr 尾部抛出来——否则只看到 CalledProcessError。

    惰性 import 被误删时子进程会抛 NameError，直接把 stderr 翻出来才看得出根因。
    """
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        raise AssertionError(
            f"子进程执行失败（exit {proc.returncode}）：{' | '.join(tail)}\n"
            f"执行的代码：{code}"
        )


def _imported_top_levels(env_extra: dict[str, str]) -> list[str]:
    """在干净子进程里 import src.web，返回已加载的顶层包名列表。"""
    code = (
        "import json, sys\n"
        "import src.web\n"
        "print(json.dumps(sorted({m.split('.')[0] for m in sys.modules})))\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=ROOT, env=env,
    )
    _check_ran(proc, code)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_vercel_form_does_not_pull_http_stack():
    """KV 未配置时，requests + urllib3 整棵树都不该进冷启动。

    它们只在 ``src/kv_store.py::_request`` 里用得到，而所有 KV 公开函数都先查
    ``kv_available()``——本地与未接 Upstash 的部署里 ``_request`` 一次都不会跑。
    """
    tops = _vercel_form_modules()
    leaked = sorted(d for d in _HTTP_ONLY_DEPS if d in tops)
    assert not leaked, (
        f"import src.web 拉起了 {leaked}；它们只在 KV 可用时才用得到，"
        "应改为函数内延迟导入"
    )


def test_vercel_form_does_not_load_pyyaml():
    """Vercel 分支不解析 config.yaml，PyYAML 也不该进冷启动。

    ``src/db.py`` 在 ``QU_STAT_DB_DIR`` 存在时直接以 ``CONFIG = {}`` 兜底，
    ``src/stats/custom.py`` 也只在读写 custom_analysis.yaml 时才需要它。
    """
    assert "yaml" not in _vercel_form_modules(), (
        "PyYAML 应延迟到真正解析 yaml 文件时才导入"
    )


def test_local_form_still_loads_pyyaml_but_not_http_stack():
    """反向兜底：本地形态必须仍解析 config.yaml，惰性导入不能把功能改坏。

    只断言「没加载 requests」是不够的——万一 ``src/db.py`` 里的惰性 ``import yaml``
    被删掉，本地分支会抛 NameError，而上面两个「不该加载」的测试反而还是绿的。
    """
    tops = _local_form_modules()
    assert "yaml" in tops, "本地形态不走 QU_STAT_DB_DIR 分支，理应解析 config.yaml"
    assert not any(d in tops for d in _HTTP_ONLY_DEPS)


def test_local_form_config_is_actually_parsed():
    """惰性导入后的 config.yaml 必须真的解析出了数据库 URL。"""
    code = (
        "import src.db as d\n"
        "print(d.DB_URL)\n"
        "print('HAS_CONFIG' if d.CONFIG else 'EMPTY')\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["QU_STAT_DB_DIR"] = ""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=ROOT, env=env,
    )
    _check_ran(proc, code)
    db_url, flag = proc.stdout.strip().splitlines()[-2:]
    assert flag == "HAS_CONFIG", "config.yaml 没被解析：惰性 import yaml 很可能被删了"
    assert "qu_stat" in db_url, f"数据库 URL 不像从 config.yaml 读到的：{db_url}"
