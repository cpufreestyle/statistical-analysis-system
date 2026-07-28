"""用户自定义分析：基于已有指标做任意公式计算。

用户在 `custom_analysis.yaml` 中声明分析项，每项给出：
  - name        分析名称
  - unit        结果单位
  - description 说明
  - variables   变量名 -> [专业, 指标, 维度(可省略，默认"全区")]
  - expr        表达式，可用变量名及 min/max/abs/round/sum
  - compare     是否计算同比(true/false)

引擎把变量绑定为对应指标值后，在受限命名空间内求值，避免任意代码执行。
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TypedDict, cast

import yaml

from src.db import query_indicators

CUSTOM_PATH = Path(__file__).resolve().parent.parent.parent / "custom_analysis.yaml"

# 仅放行的内置函数，杜绝 __import__ / open 等危险调用。
_SAFE_BUILTINS: dict[str, object] = {
    "min": min, "max": max, "abs": abs,
    "round": round, "sum": sum, "float": float, "int": int,
}


class CustomAnalysis(TypedDict, total=False):
    name: str
    unit: str
    description: str
    variables: dict[str, list[str]]
    expr: str
    compare: bool


def load_custom() -> list[CustomAnalysis]:
    if not CUSTOM_PATH.exists():
        return []
    with CUSTOM_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    return cast("list[CustomAnalysis]", data)


def _save(items: list[CustomAnalysis]) -> None:
    with CUSTOM_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(items, f, allow_unicode=True, sort_keys=False)


def _var_value(spec: list[str], year: int) -> float | None:
    dim = spec[2] if len(spec) > 2 else "全区"
    rows = query_indicators(year=year, category=spec[0],
                            indicator=spec[1], dimension=dim)
    return rows[0]["value"] if rows else None


def _safe_eval(expr: str, namespace: Mapping[str, object]) -> float | None:
    result = eval(expr, {"__builtins__": {}}, {**_SAFE_BUILTINS, **namespace})  # noqa: S307
    return float(result) if result is not None else None


def run_custom(a: CustomAnalysis, year: int) -> dict[str, object]:
    """对单个自定义分析求值，返回结构化结果。"""
    namespace = {
        var: _var_value(spec, year) for var, spec in a.get("variables", {}).items()
    }
    if any(v is None for v in namespace.values()):
        return {"name": a.get("name", ""), "error": "缺少部分变量数据"}
    try:
        value = _safe_eval(a.get("expr", ""), namespace)
    except Exception as e:  # noqa: BLE001 - 把表达式错误原样返回给调用方
        return {"name": a.get("name", ""), "error": f"表达式求值失败：{e}"}

    result: dict[str, object] = {
        "name": a.get("name", ""),
        "value": value,
        "unit": a.get("unit", ""),
        "expr": a.get("expr", ""),
    }
    if a.get("compare"):
        prev_ns = {
            var: _var_value(spec, year - 1)
            for var, spec in a.get("variables", {}).items()
        }
        if all(v is not None for v in prev_ns.values()):
            try:
                prev = _safe_eval(a.get("expr", ""), prev_ns)
            except Exception:
                prev = None
            if prev not in (None, 0) and value is not None:
                result["yoy"] = round((value - prev) / prev * 100, 2)
    return result


def run_all_custom(year: int) -> list[dict[str, object]]:
    return [run_custom(a, year) for a in load_custom()]


def add_custom(data: dict[str, object]) -> tuple[bool, str]:
    """校验并追加一条自定义分析到 yaml。返回 (成功?, 错误信息)。"""
    name = str(data.get("name", "")).strip()
    expr = str(data.get("expr", "")).strip()
    if not name or not expr:
        return (False, "name 与 expr 必填")
    variables = data.get("variables", {})
    if not isinstance(variables, dict) or not variables:
        return (False, "variables 必须是非空对象")

    item: CustomAnalysis = {
        "name": name,
        "unit": str(data.get("unit", "")),
        "description": str(data.get("description", "")),
        "variables": cast("dict[str, list[str]]", variables),
        "expr": expr,
        "compare": bool(data.get("compare", False)),
    }
    # 用占位值预校验表达式可求值
    probe = {k: 1.0 for k in item["variables"]}
    try:
        _safe_eval(item["expr"], probe)
    except Exception as e:
        return (False, f"表达式无效：{e}")

    items = load_custom()
    if any(x.get("name") == name for x in items):
        return (False, f"已存在同名分析：{name}")
    items.append(item)
    _save(items)
    return (True, "")
