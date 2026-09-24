"""代码分割的结构守卫。

app.js 拆成 core + app.charts.js + app.palette.js 之后，真正会悄悄坏掉的只有两件事：

1. **同一个函数出现在两个文件里**——后加载的覆盖先加载的，行为随加载顺序漂移，
   而且肉眼看不出异常；
2. **core 引用了只属于分块的声明**——分块还没拉下来时就执行，直接 ReferenceError
   （或者更糟：被 try/catch 吞掉，整块功能静默失效）。

行为由 tests/frontend_behavior.mjs 的 6 条哨兵把守；这里钉住结构，让它没法退化。
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC = BASE_DIR / "public"

#: core 与两个分块：key 是文件名，value 是人类可读的名字。
SPLIT_FILES = {
    "app.js": "core",
    "app.charts.js": "charts",
    "app.palette.js": "palette",
}

#: 顶层声明：函数声明 + const/let/var 赋值。分块之间只靠这些互相可达。
_DECL_RE = re.compile(
    r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"
    r"|^(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=",
    re.M,
)
_IDENT_RE = re.compile(r"[A-Za-z_$][\w$]*")


@pytest.fixture(scope="module")
def node() -> str:
    exe = shutil.which("node")
    if not exe:
        pytest.skip("未找到 node，分块语法检查跳过（CI 的 test 作业已通过 setup-node 保证可用）")
    return exe


def _decls(text: str) -> set[str]:
    return {a or b for a, b in _DECL_RE.findall(text)}


def _read(name: str) -> str:
    """归一化成 LF：public/ 在 git 索引里是 LF，工作区是 CRLF。"""
    raw = (PUBLIC / name).read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n")


def _function_body(text: str, decl: str) -> str:
    """从 decl 的起点做花括号配对，取出完整函数体（含签名）。

    比「下一个函数名」当边界稳：文件里函数顺序调整过也不会莫名抛 ValueError。
    """
    start = text.index(decl)
    depth = 0
    for i in range(text.index("{", start), len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AssertionError(f"没能配平 {decl} 的花括号")


def _strip_comments(text: str) -> str:
    """去掉 // 与 /* */ 注释：注释里提到的名字是文档，不是引用。"""
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)


def _is_guarded(text: str, name: str) -> bool:
    """typeof X === 'function' 特特性探测：分块没拉下来就跳过，不会抛 ReferenceError。"""
    return bool(re.search(r"typeof\s+" + re.escape(name) + r"\b", text))


def test_no_declaration_is_defined_twice() -> None:
    """同一个名字出现在两个文件里，后加载的会静默覆盖先加载的。"""
    texts = {label: _read(name) for name, label in SPLIT_FILES.items()}
    seen: dict[str, set[str]] = {}
    for label, text in texts.items():
        for decl in _decls(text):
            seen.setdefault(decl, set()).add(label)
    dupes = {k: sorted(v) for k, v in seen.items() if len(v) > 1}
    assert not dupes, f"同名声明出现在多个文件里（后者会静默覆盖前者）：{dupes}"


def test_chunks_do_not_reference_each_other() -> None:
    """分块之间一旦互相引用，就多出一条加载顺序约束：先打开的面板会把
    后一个分块的函数拖下来，懒加载名存实亡。这里钉死「彼此不可见」。"""
    charts = _read("app.charts.js")
    palette = _read("app.palette.js")
    pal_decls = _decls(palette)
    chart_decls = _decls(charts)
    bad = sorted(n for n in _IDENT_RE.findall(charts) if n in pal_decls)
    assert not bad, f"app.charts.js 引用了命令面板分块的声明：{bad}"
    bad = sorted(n for n in _IDENT_RE.findall(palette) if n in chart_decls)
    assert not bad, f"app.palette.js 引用了图表分块的声明：{bad}"


def test_core_only_references_chunk_code_where_it_is_safe() -> None:
    """core 引用分块函数只有两个安全位置，别处出现都是加载顺序地雷：

    1. ``openTab()`` 的 ``.then`` 回调里——那时分块已经加载完；
    2. 被 ``typeof X === 'function'`` 探测过的地方——没加载就跳过，不会抛。

    写在上面的注释不算。首屏路径上一踩就是 ReferenceError；而被 try/catch 吞掉的
    更糟——整块功能静默失效。"""
    core = _read("app.js")
    open_body = _function_body(core, "function openTab(tabId) {")
    rest = _strip_comments(core.replace(open_body, "", 1))

    chunk_decls = _decls(_read("app.charts.js")) | _decls(_read("app.palette.js"))
    leaks = sorted(
        {
            n
            for n in _IDENT_RE.findall(rest)
            if n in chunk_decls and not _is_guarded(rest, n)
        }
    )
    assert not leaks, f"core 在不受保护的位置引用了分块专属声明（加载顺序地雷）：{leaks}"


def test_chunk_urls_are_versioned_in_the_dashboard() -> None:
    """分块带 immutable 一年缓存，URL 不带内容哈希就永远顶不失效。"""
    html = _read("app.html")
    for stem in ("app.charts.js", "app.palette.js"):
        assert "/" + stem + "?v=__" in html, f"app.html 没有给 {stem} 带版本号占位符"


def test_behavior_harness_really_executes_chunks() -> None:
    """harness 的 DOM 桩不会真的加载 <script>；如果它什么都不做，
    loadChunk() 的 Promise 永远不兑现，「按需加载」就被测不到了。"""
    src = (BASE_DIR / "tests" / "frontend_behavior.mjs").read_text(encoding="utf-8")
    assert "CHUNK_FILES" in src, "harness 没有登记分块文件"
    assert "runInContext(read(CHUNK_FILES[key])" in src, (
        "harness 没有在 vm 里真正执行分块——懒加载会被测成空转"
    )
    assert "if (c.onload) c.onload()" in src, (
        "harness 执行完分块后没有兑现 onload"
    )


def test_chunk_files_are_not_empty_and_parse(node: str) -> None:
    """空分块或语法坏掉的分块都要红——后者在浏览器里要到点击才炸。"""
    for name in SPLIT_FILES:
        proc = subprocess.run([node, "--check", str(PUBLIC / name)], capture_output=True, text=True)
        assert proc.returncode == 0, f"{name} 语法错误：{proc.stderr}"
        assert (PUBLIC / name).stat().st_size > 2000, f"{name} 小得不像一个分块"
