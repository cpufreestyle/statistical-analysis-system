"""用户自定义分析：基于已有指标做任意公式计算。

用户在 `custom_analysis.yaml` 中声明分析项，每项给出：
  - name        分析名称
  - unit        结果单位
  - description 说明
  - variables   变量名 -> [专业, 指标, 维度(可省略，默认"亚太")]
  - expr        表达式，可用变量名及 min/max/abs/round/sum
  - compare     是否计算同比(true/false)

引擎把变量绑定为对应指标值后，在受限命名空间内求值，避免任意代码执行。
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TypedDict, cast

from src.db import query_indicators

CUSTOM_PATH = Path(__file__).resolve().parent.parent.parent / "custom_analysis.yaml"
_CUSTOM_KV_KEY = "qu_stat_ap:custom"


def _load_custom_from_kv() -> list[CustomAnalysis] | None:
    """从 Vercel KV 读取自定义分析配置。KV 不可用或为空时返回 None。"""
    from src.kv_store import kv_available, kv_get_json
    if not kv_available():
        return None
    data = kv_get_json(_CUSTOM_KV_KEY)
    if data and isinstance(data, list):
        return cast("list[CustomAnalysis]", data)
    return None


def _save_custom_to_kv(items: list[CustomAnalysis]) -> None:
    """将自定义分析配置保存到 Vercel KV。"""
    from src.kv_store import kv_available, kv_set_json
    if kv_available():
        kv_set_json(_CUSTOM_KV_KEY, items)

# 仅放行的内置函数，杜绝 __import__ / open 等危险调用。
_SAFE_BUILTINS: dict[str, object] = {
    "min": min, "max": max, "abs": abs,
    "round": round, "sum": sum, "float": float, "int": int,
}


class CustomAnalysis(TypedDict, total=False):
    name: str
    name_en: str
    unit: str
    description: str
    description_en: str
    variables: dict[str, list[str]]
    expr: str
    compare: bool


#: 求值期错误信息（中 / 英）。自定义分析的名字与说明由用户配置，
#: 不机器翻译；但引擎自己产生的错误必须双语，否则英文接口会漏出中文。
_ERRORS: dict[str, dict[str, str]] = {
    "missing_vars": {"zh": "缺少部分变量数据", "en": "Missing data for some variables"},
    "expr_failed": {"zh": "表达式求值失败：{err}",
                    "en": "Expression evaluation failed: {err}"},
    "name_expr_required": {"zh": "name 与 expr 必填", "en": "name and expr are required"},
    "vars_required": {"zh": "variables 必须是非空对象",
                      "en": "variables must be a non-empty object"},
    "expr_invalid": {"zh": "表达式无效：{err}", "en": "Invalid expression: {err}"},
    "duplicate": {"zh": "已存在同名分析：{name}",
                  "en": "An analysis with this name already exists: {name}"},
}


def _err(key: str, lang: str = "zh", **kw: object) -> str:
    table = _ERRORS[key]
    template = table["zh"] if str(lang).startswith("zh") else table["en"]
    return template.format(**kw)


def _is_zh(lang: str) -> bool:
    return str(lang).startswith("zh")


def _localize_term(kind: str, key: str, lang: str) -> str:
    """把数据词条（单位等）翻成目标语言；未登记则原样返回。"""
    if not key:
        return ""
    try:
        from src import labels
    except Exception:  # 标签层不可用不应影响自定义分析
        return key
    return labels.label(kind, key, lang)


def display_name(a: CustomAnalysis, lang: str = "zh") -> str:
    """分析名称。``name_en`` 缺失时回退中文名——用户配置的内容不做机器翻译。"""
    if _is_zh(lang):
        return a.get("name", "")
    return a.get("name_en") or a.get("name", "")


def display_description(a: CustomAnalysis, lang: str = "zh") -> str:
    if _is_zh(lang):
        return a.get("description", "")
    return a.get("description_en") or a.get("description", "")


def find_custom(name: str) -> CustomAnalysis | None:
    """按名称查分析项；中文名与英文名（不分大小写）都能命中。"""
    if not name:
        return None
    want = name.strip().lower()
    for a in load_custom():
        for candidate in (a.get("name", ""), a.get("name_en", "")):
            if candidate and candidate.strip().lower() == want:
                return a
    return None


def list_custom(lang: str = "zh") -> list[dict[str, str]]:
    """分析列表（名称 / 说明 / 单位按语言本地化），供下拉选择。

    ``name_key`` 是配置里的规范中文名（可能为空），供需要稳定标识的调用方使用；
    ``name`` 才是展示用名称，也是查询时可直接回传的入参（:func:`find_custom` 中英都认）。
    """
    out: list[dict[str, str]] = []
    for a in load_custom():
        raw_unit = a.get("unit", "")
        out.append({
            "name": display_name(a, lang),
            "name_key": a.get("name", ""),
            "description": display_description(a, lang),
            "unit": _localize_term("unit", raw_unit, lang),
        })
    return out


def load_custom() -> list[CustomAnalysis]:
    # Vercel 环境优先从 KV 恢复
    kv_data = _load_custom_from_kv()
    if kv_data is not None:
        return kv_data
    if not CUSTOM_PATH.exists():
        return []
    import yaml  # 延迟导入：读配置才需要 PyYAML，别让冷启动为它付费

    with CUSTOM_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    return cast("list[CustomAnalysis]", data)


def _save(items: list[CustomAnalysis]) -> None:
    import yaml  # 延迟导入：仅在写入自定义分析配置时才需要 PyYAML

    with CUSTOM_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(items, f, allow_unicode=True, sort_keys=False)
    _save_custom_to_kv(items)


def _var_value(spec: list[str], year: int) -> float | None:
    dim = spec[2] if len(spec) > 2 else "亚太"
    rows = query_indicators(year=year, category=spec[0],
                            indicator=spec[1], dimension=dim)
    return rows[0]["value"] if rows else None


def _safe_eval(expr: str, namespace: Mapping[str, object]) -> float | None:
    result = eval(expr, {"__builtins__": {}}, {**_SAFE_BUILTINS, **namespace})  # noqa: S307
    return float(result) if result is not None else None


def run_custom(a: CustomAnalysis, year: int, lang: str = "zh") -> dict[str, object]:
    """对单个自定义分析求值，返回结构化结果（名称与错误信息按 ``lang`` 本地化）。"""
    namespace = {
        var: _var_value(spec, year) for var, spec in a.get("variables", {}).items()
    }
    if any(v is None for v in namespace.values()):
        return {"name": display_name(a, lang), "error": _err("missing_vars", lang)}
    try:
        value = _safe_eval(a.get("expr", ""), namespace)
    except Exception as e:  # noqa: BLE001 - 把表达式错误原样返回给调用方
        return {"name": display_name(a, lang),
                "error": _err("expr_failed", lang, err=e)}

    result: dict[str, object] = {
        "name": display_name(a, lang),
        "value": value,
        "unit": _localize_term("unit", a.get("unit", ""), lang),
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


def run_all_custom(year: int, lang: str = "zh") -> list[dict[str, object]]:
    return [run_custom(a, year, lang) for a in load_custom()]


def add_custom(data: dict[str, object], lang: str = "zh") -> tuple[bool, str]:
    """校验并追加一条自定义分析到 yaml。返回 (成功?, 错误信息)。"""
    name = str(data.get("name", "")).strip()
    expr = str(data.get("expr", "")).strip()
    if not name or not expr:
        return (False, _err("name_expr_required", lang))
    variables = data.get("variables", {})
    if not isinstance(variables, dict) or not variables:
        return (False, _err("vars_required", lang))

    item: CustomAnalysis = {
        "name": name,
        "name_en": str(data.get("name_en", "")).strip(),
        "unit": str(data.get("unit", "")),
        "description": str(data.get("description", "")),
        "description_en": str(data.get("description_en", "")).strip(),
        "variables": cast("dict[str, list[str]]", variables),
        "expr": expr,
        "compare": bool(data.get("compare", False)),
    }
    # 用占位值预校验表达式可求值
    probe = {k: 1.0 for k in item["variables"]}
    try:
        _safe_eval(item["expr"], probe)
    except Exception as e:
        return (False, _err("expr_invalid", lang, err=e))

    items = load_custom()
    if any(x.get("name") == name for x in items):
        return (False, _err("duplicate", lang, name=name))
    items.append(item)
    _save(items)
    return (True, "")
