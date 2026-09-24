"""字典 / 样式拆分后的不变式守卫。

背景：``public/i18n.js`` 原本把 332 条中英字典和运行时打成一个文件，两个页面都整包下载，
而落地页其实只引用其中 69 条；同时 ``index.html`` 内联了 622 行 ``<style>``，
而页面 HTML 的 Cache-Control 是 no-store——这两部分每次都跟着整页重下。

于是拆成四份：``i18n-dict.js``（全量，看板 /app 用）、``i18n-dict-landing.js``
（子集，落地页 / 用）、``i18n.js``（只剩运行时）、``landing.css``（从 index.html 抽出）。

本文件盯住的正是「拆完之后不许悄悄长回去」：
  · i18n.js 不得再出现内联字典；
  · 落地页字典的键集合必须与 index.html 的 data-i18n* 引用逐一对应；
  · 落地页字典的取值必须与全量字典逐字相同；
  · 两个页面的加载顺序都必须是「字典 → 运行时」；
  · embed_pages.py / web._ASSET_FILES 两处资产登记必须一致。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

#: 双引号字符——本文件的 JS 片段与正则都要拼它，避免层层转义看花眼。
DQ = chr(34)

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC = BASE_DIR / "public"
I18N_JS = PUBLIC / "i18n.js"
FULL_DICT = PUBLIC / "i18n-dict.js"
LANDING_DICT = PUBLIC / "i18n-dict-landing.js"


@pytest.fixture(scope="module")
def node() -> str:
    exe = shutil.which("node")
    if not exe:
        pytest.skip("未找到 node，字典拆分检查跳过（CI 的 test 作业已通过 setup-node 保证可用）")
    return exe


def _load_dict(node: str, path: Path) -> dict[str, str]:
    """在 Node 里执行字典文件、取回 window.ZH2EN。

    用真解析而不是正则：字典里有跨行取值与注释，正则一旦和格式脱钩就会静默漏条，
    那比不检查更糟。
    """
    script = (
        "const fs=require(" + DQ + "fs" + DQ + "),vm=require(" + DQ + "vm" + DQ + ");"
        "const sb={};"
        "vm.runInNewContext(" + DQ + "var window={};" + DQ + "+fs.readFileSync(process.argv[1]," + DQ + "utf8" + DQ + "),sb);"
        "process.stdout.write(JSON.stringify(sb.window.ZH2EN));"
    )
    proc = subprocess.run([node, "-e", script, str(path)],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, f"无法加载 {path.name}：{proc.stderr}"
    return json.loads(proc.stdout)


def _landing_referenced_keys() -> list[str]:
    """index.html 里 data-i18n / -html / -ph 引用的键，按文档顺序去重。"""
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    out: list[str] = []
    for key in re.findall(r"data-i18n(?:-html|-ph)?=" + DQ + "([^" + DQ + "]+)" + DQ, html):
        if key not in out:
            out.append(key)
    return out


def test_i18n_js_has_no_inline_dictionary() -> None:
    """运行时文件不得再背字典——长回去就等于优化白做。

    体积那条是关键兜底：光靠「没有 var ZH2EN = {」能被人用别的写法绕过去
    （例如 ``var ZH2EN = window.ZH2EN || {…}``），但字典一长回来文件就会接近
    甚至超过全量字典的大小，这条怎么绕不过。
    """
    runtime = I18N_JS.read_text(encoding="utf-8")
    full = FULL_DICT.read_text(encoding="utf-8")
    assert "var ZH2EN = {" not in runtime, "i18n.js 又内联了字典，请拆回 i18n-dict*.js"
    assert "window.ZH2EN" in runtime, "i18n.js 没有从 window.ZH2EN 读取字典"
    assert len(runtime) < len(full), (
        f"i18n.js 有 {len(runtime)} 字符，已不小于全量字典的 {len(full)} 字符，"
        "字典很可能又内联回运行时文件了"
    )
    # 运行时仍需自带的部件（结构键表与单位词表）不能一起被拆丢
    for kept in ("ASK_KEY_LABELS", "UNIT_TERMS", "DATA_TERMS"):
        assert kept in runtime, f"i18n.js 丢了 {kept}"


def test_dict_files_are_loadable_and_sized(node: str) -> None:
    full = _load_dict(node, FULL_DICT)
    landing = _load_dict(node, LANDING_DICT)
    assert len(full) > 300, f"全量字典条数异常：{len(full)}"
    assert len(landing) > 30, f"落地页字典条数异常：{len(landing)}"
    assert len(landing) < len(full) * 0.4, (
        f"落地页字典 {len(landing)} 条已接近全量 {len(full)} 条，拆分的意义没了"
    )


def test_landing_dict_keys_exactly_match_index_html(node: str) -> None:
    """多一条是白下载，少一条是英文界面裸显中文——必须逐一对应。"""
    landing = _load_dict(node, LANDING_DICT)
    referenced = _landing_referenced_keys()
    extra = sorted(set(landing) - set(referenced))
    missing = sorted(set(referenced) - set(landing))
    assert not extra, f"落地页字典多出 index.html 没引用的键：{extra}"
    assert not missing, f"index.html 引用了落地页字典里没有的键：{missing}"


def test_landing_dict_values_are_verbatim_from_full_dict(node: str) -> None:
    """子集不只是键要对，取值也得和全量逐字相同——否则同一句中英两页说法不一。"""
    full = _load_dict(node, FULL_DICT)
    landing = _load_dict(node, LANDING_DICT)
    drift = {k: (full[k], landing[k]) for k in landing if full.get(k) != landing[k]}
    assert not drift, f"落地页字典与全量字典取值不一致：{drift}"


def test_dashboard_loads_dict_before_runtime(client) -> None:
    html = client.get("/app").get_data(as_text=True)
    i_dict = html.index("/i18n-dict.js?v=")
    i_run = html.index("/i18n.js?v=")
    assert i_dict < i_run, "看板把 i18n.js 排在 i18n-dict.js 前面了"
    assert "/i18n-dict-landing.js?v=" not in html, "看板不该加载落地页字典子集"


def test_landing_loads_dict_before_runtime(client) -> None:
    html = client.get("/").get_data(as_text=True)
    i_dict = html.index("/i18n-dict-landing.js?v=")
    i_run = html.index("/i18n.js?v=")
    assert i_dict < i_run, "落地页把 i18n.js 排在 i18n-dict-landing.js 前面了"
    assert "/i18n-dict.js?v=" not in html, "落地页不该加载全量字典"


def test_landing_page_has_no_inline_style(client) -> None:
    """落地页样式必须留在抽出来的 /landing.css 里，不能长回 HTML。"""
    html = client.get("/").get_data(as_text=True)
    assert "<style>" not in html, "index.html 又内联了样式表"
    assert "/landing.css?v=" in html, "index.html 没有引用 /landing.css"


def test_behavior_harness_loads_dict_before_runtime() -> None:
    """前端行为 harness 也必须先灌字典再灌运行时，否则它会拿着空字典跑。"""
    src = (BASE_DIR / "tests" / "frontend_behavior.mjs").read_text(encoding="utf-8")
    anchor = src.index("vm.runInContext(read(I18N_DICT_JS)")
    tail = src[anchor:]
    assert "read(I18N_DICT_JS)" in tail and "read(I18N_JS)" in tail
    assert tail.index("read(I18N_DICT_JS)") < tail.index("read(I18N_JS)"), (
        "frontend_behavior.mjs 里字典排在运行时之后了"
    )


def test_asset_registrations_are_consistent() -> None:
    """embed_pages.py 的 FILES 与 web._ASSET_FILES 必须登记同一批资产。

    新增前端文件要同时改这两处外加一条路由；漏一处不会立刻炸，只会在下次
    加资产时变成查不出来的怪味，所以在这里钉死。
    """
    from src import web

    src = (BASE_DIR / "scripts" / "embed_pages.py").read_text(encoding="utf-8")
    block = src.split("FILES = {", 1)[1].split("}", 1)[0]
    embedded = set(re.findall(DQ + "([A-Z0-9_]+)" + DQ + r"\s*:", block))
    # HTML 整页由 _render_page 现场渲染，Cache-Control 是 no-store，
    # 不走「内容哈希版本号 + immutable」那套，故不参与资产登记比对。
    embedded -= {"PAGE_INDEX", "PAGE_APP"}
    registered = set(web._ASSET_NAMES)
    assert embedded == registered, (
        f"资产登记不一致：只在 embed_pages：{sorted(embedded - registered)}；"
        f"只在 web._ASSET_FILES：{sorted(registered - embedded)}"
    )
