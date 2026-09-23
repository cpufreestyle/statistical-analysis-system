"""前端逻辑的可执行检查（出海批次最高风险面的机器防线）。

``public/app.js`` 与 ``public/i18n.js`` 由 ``src/web.py`` 直接服务，承载看板兜底、
维度键判断、语言切换等行为；此前 ``tests/test_embed.py`` 只断言常量存在，
真实行为只能靠人工在浏览器里点。

这里用 Node 的 ``vm`` 在沙箱里执行**仓库里那份原始 JS**（零依赖、零构建、
无 package.json），由 ``tests/frontend_behavior.mjs`` 驱动并断言输出。
JS 侧细节改坏了会在 ``.mjs`` 里报出具体场景；本机 / CI 无 node 时整节跳过。

``public/index.html`` 是自包含页面（不引 app.js），它的主题三态在文件末尾的内联
``<script>`` 里，由 ``tests/landing_theme_behavior.mjs`` 单独抽取执行——落地页与
看板必须共用同一套主题约定（同一个 ``qu_theme_v1`` 键、同一个三态顺序），
单测看板会漏掉只改首页造成的回归。
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
    # 工作台增强批次（命令面板 / 快捷键 / 主题 / 迷你趋势）
    "默认主题为 auto",
    "系统浅色时解析为 light",
    "系统深色时 auto 解析为 dark",
    "手动浅色优先于系统深色",
    "主题循环顺序 auto/light/dark",
    "主题选择已持久化",
    "命令面板打开后可见",
    "命令列表渲染 option",
    "命令含年份项",
    "命令含经济体项",
    "按年份过滤只留命中项",
    "无命中给出空态",
    "面板命令切到图表视图",
    "执行命令后面板关闭",
    "输入类控件被识别为打字目标",
    "帮助浮层可打开",
    "帮助渲染键帽与说明",
    "帮助浮层可关闭",
    "卡片含趋势容器",
    "有跨年序列时画出折线",
    "折线悬浮给出起止值",
    "单点序列不画折线",
    # 数据洞察区块
    "洞察渲染三张卡",
    "洞察含同比榜单",
    "洞察含名次变动",
    "洞察含覆盖计数",
    "无洞察给空态",
    # 加载期初始化顺序（app.js 末尾的增强能力初始化必须在所有 const 声明之后）
    "加载即同步主题按钮",
    "加载即落地 data-theme",
    "Ctrl+K 能打开命令面板",
    "Esc 能关闭命令面板",
    "问号键能打开帮助浮层",
    "Esc 能关闭帮助浮层",
]


# 落地页主题场景（public/index.html 自包含，不走 app.js，故单独一个 harness）
LANDING_HARNESS = BASE_DIR / "tests" / "landing_theme_behavior.mjs"

LANDING_SCENARIOS = [
    "落地页默认主题为 auto",
    "系统深色时 auto 解析为 dark",
    "手动浅色优先于系统深色",
    "手动深色优先于系统浅色",
    "主题按钮有可读标签",
    "落地页主题循环顺序 auto/light/dark",
    "深色档位落在 system 浅色下的 dark",
    "落地页主题选择已持久化",
    "落地页监听系统配色变化",
    "系统变深后 auto 跟随到 dark",
    "手动档位不跟随系统变化",
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


def test_landing_theme_behavior_checks_pass(node: str) -> None:
    """落地页（/）必须与看板（/app）同一套主题约定。

    落地页不引 app.js，主题三态实现在 index.html 末尾的内联脚本里；
    改动只落在 public/index.html 时同样要有机检，而不是靠人工点浏览器。
    """
    proc = subprocess.run(
        [node, str(LANDING_HARNESS)], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120, cwd=str(BASE_DIR),
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, f"落地页主题行为检查未通过：\n{output}"
    assert "0 项未通过" in output, output
    for name in LANDING_SCENARIOS:
        assert f"[PASS] {name}" in output, f"缺少落地页场景结果「{name}」：\n{output}"


def test_landing_harness_goes_red_when_persistence_is_broken(node: str, tmp_path: Path) -> None:
    """harness 本身必须可失败：改坏主题持久化时要红，而不是静默少跑。"""
    original = (BASE_DIR / "public" / "index.html").read_text(encoding="utf-8")
    guard = "localStorage.setItem(THEME_KEY, next)"
    assert guard in original, "public/index.html 的主题持久化语句已变化，请同步本测试"

    broken = tmp_path / "index_broken.html"
    broken.write_text(original.replace(guard, "/* persist disabled */"), encoding="utf-8")

    proc = subprocess.run(
        [node, str(LANDING_HARNESS)], capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, cwd=str(BASE_DIR),
        env={**os.environ, "QU_STAT_INDEX_HTML": str(broken)},
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0, "破坏主题持久化后 harness 仍全绿，检查已失去防线作用"
    assert "[FAIL] 落地页主题循环顺序 auto/light/dark" in output, output
