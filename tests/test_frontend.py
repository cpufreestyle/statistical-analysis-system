"""前端逻辑的可执行检查（出海批次最高风险面的机器防线）。

``public/app.js`` 与 ``public/i18n.js`` 由 ``src/web.py`` 直接服务，承载看板兜底、
维度键判断、语言切换等行为；此前 ``tests/test_embed.py`` 只断言常量存在，
真实行为只能靠人工在浏览器里点。

这里用 Node 的 ``vm`` 在沙箱里执行**仓库里那份原始 JS**（零依赖、零构建、
无 package.json），由 ``tests/frontend_behavior.mjs`` 驱动并断言输出。
JS 侧细节改坏了会在 ``.mjs`` 里报出具体场景；本机 / CI 无 node 时整节跳过。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
HARNESS = BASE_DIR / "tests" / "frontend_behavior.mjs"

# 场景清单：任一条被删掉都意味着覆盖面缩水
SCENARIOS = [
    "空看板给出英文兜底文案",
    "兜底带切回亚太的出口",
    "可见文案不残留中文原词",
    "按 dimension_key 判重，STATE 仍是展示标签",
    "亚太口径空态不再给出口按钮",
    "亚太口径空态仍有说明",
    "中文界面兜底为中文",
    "有数据渲染指标卡",
    "有数据时不出现空态兜底",
    "取数失败渲染失败态",
    "取数失败不留骨架屏",
]


@pytest.fixture(scope="module")
def node() -> str:
    exe = shutil.which("node")
    if not exe:
        pytest.skip("未找到 node，前端行为检查跳过（CI 的 test 作业已通过 setup-node 保证可用）")
    return exe


def test_frontend_behavior_checks_pass(node: str) -> None:
    proc = subprocess.run(
        [node, str(HARNESS)], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120, cwd=str(BASE_DIR),
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, f"前端行为检查未通过：\n{output}"
    assert "0 项未通过" in output, output
    for name in SCENARIOS:
        assert f"[PASS] {name}" in output, f"缺少场景结果「{name}」：\n{output}"


def test_harness_goes_red_when_the_empty_state_guard_is_broken(node: str, tmp_path: Path) -> None:
    """harness 本身必须可失败：改坏空态兜底条件时要红，而不是静默少跑。

    用临时副本 + ``QU_STAT_APP_JS`` 注入，绝不改写被跟踪的 public/app.js
    （那会让约定 1 的内嵌页与源码瞬间失同步）。
    """
    original = (BASE_DIR / "public" / "app.js").read_text(encoding="utf-8")
    guard = "var back = (d.dimension_key || STATE.dimension) !== '亚太'"
    assert guard in original, "public/app.js 的空态兜底语句已变化，请同步本测试"

    broken = tmp_path / "app_broken.js"
    broken.write_text(original.replace(guard, "var back = false"), encoding="utf-8")

    proc = subprocess.run(
        [node, str(HARNESS)], capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, cwd=str(BASE_DIR),
        env={**os.environ, "QU_STAT_APP_JS": str(broken)},
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0, "破坏空态兜底后 harness 仍全绿，检查已失去防线作用"
    assert "[FAIL] 兜底带切回亚太的出口" in output, output
