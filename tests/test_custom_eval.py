"""自定义分析表达式的 AST 白名单求值器审核回归。

历史实现用「空 __builtins__ 的 eval」，可沿属性链逃逸成任意代码执行：
``().__class__.__bases__[0].__subclasses__()`` 可达 os/subprocess。
本文件钉住：逃逸面全部封死 + 正常公式不受影响 + 入库校验（长度/条数/变量结构）。
"""
from __future__ import annotations

import pytest

from src.stats import custom as cust


# ---------------------------------------------------------------------------
# _safe_eval：正常表达式
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("expr,ns,expect", [
    ("x + y", {"x": 1.0, "y": 2.0}, 3.0),
    ("x / y * 100", {"x": 3.0, "y": 4.0}, 75.0),
    ("-x ** 2", {"x": 3.0}, -9.0),
    ("max(x, y) + abs(-2)", {"x": 1.0, "y": 2.0}, 4.0),
    ("round(x / y, 2)", {"x": 1.0, "y": 3.0}, 0.33),
])
def test_eval_normal_arithmetic(expr, ns, expect):
    assert cust._safe_eval(expr, ns) == pytest.approx(expect)


def test_eval_float_result():
    """int 输入也要产出 float（接口契约：返回值恒为 float）。"""
    assert isinstance(cust._safe_eval("x + 1", {"x": 1}), float)


# ---------------------------------------------------------------------------
# _safe_eval：逃逸与越权全部封死
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [
    "().__class__.__name__",
    "().__class__.__bases__[0].__subclasses__()",
    "().__class__.__mro__[1].__subclasses__()[104].__init__.__globals__['os'].system('echo pwn')",
    "__import__('os').system('echo pwn')",
    "open('/etc/passwd').read()",
    "(lambda: 1)()",
    "[x for x in range(3)]",
    "{'a': 1}.keys()",
    "'a' + 'b'",
    "globals()",
    "x.__class__",
    "min(x, y, key=len)",           # 关键字参数收紧
    "x if x else y",                 # 条件表达式
    "f'{x}'",                        # f-string
])
def test_eval_blocks_escapes(bad):
    with pytest.raises(Exception):
        cust._safe_eval(bad, {"x": 1.0, "y": 2.0})


def test_eval_rejects_unknown_name():
    with pytest.raises(ValueError, match="unknown name"):
        cust._safe_eval("nope + 1", {"x": 1.0})


def test_eval_syntax_error():
    with pytest.raises(ValueError):
        cust._safe_eval("x +* y", {"x": 1.0})


# ---------------------------------------------------------------------------
# add_custom：入库校验（防止脏条目落盘后每次查询 500）
# ---------------------------------------------------------------------------
@pytest.fixture()
def custom_file(tmp_path, monkeypatch):
    """CUSTOM_PATH 指到临时文件；KV 本地不可用，写路径不会外发。"""
    path = tmp_path / "custom_analysis.yaml"
    path.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(cust, "CUSTOM_PATH", path)
    return path


def test_add_custom_ok(custom_file):
    ok, err = cust.add_custom({
        "name": "测试分析", "expr": "x / y * 100",
        "variables": {"x": ["生产", "GDP"], "y": ["总量", "人口", "亚太"]},
    })
    assert ok, err
    assert len(cust.load_custom()) == 1


def test_add_custom_rejects_bad_variable_shape(custom_file):
    """变量值不是 [专业, 指标, 维度?] 字符串列表 → 拒收（旧版会落盘脏条目）。"""
    for variables in (
        {"x": 5},
        {"x": ["只有一截"]},
        {"x": ["专业", "指标", 3]},
        {"x": ["专业", "指标", "维度", "多出来的"]},
        {"": ["专业", "指标"]},
        {"x": "生产,GDP"},
    ):
        ok, _err = cust.add_custom({"name": "n", "expr": "x + 1", "variables": variables})
        assert not ok, variables
    assert cust.load_custom() == []


def test_add_custom_rejects_oversize(custom_file):
    ok, _err = cust.add_custom({"name": "n" * 81, "expr": "x + 1",
                                "variables": {"x": ["a", "b"]}})
    assert not ok
    ok, _err = cust.add_custom({"name": "n", "expr": "1+" * 300,
                                "variables": {"x": ["a", "b"]}})
    assert not ok
    assert cust.load_custom() == []


def test_add_custom_rejects_nonsense_expr(custom_file):
    """预校验用占位值跑 AST 求值器：逃逸语法在入库前就被拦下。"""
    ok, _err = cust.add_custom({"name": "n", "expr": "().__class__.__name__",
                                "variables": {"x": ["a", "b"]}})
    assert not ok
    assert cust.load_custom() == []
