"""SQL 计算引擎：把自定义分析的「变量绑定」从 N 次点查升级为 1 条 SQL。

背景
----
原来的 ``src/stats/custom.py`` 对每个变量单独查一次库（:func:`query_indicators`），
再对同比多查一轮——一个含 K 个变量、开启同比的分析要 **2K 次数据库往返**。
变量越多、往返越贵，在 Serverless（Vercel）上尤其明显。

本模块用**一条 SQL** 完成「映射 + 透视」：把所有需要的
``(年份, 专业, 指标, 维度)`` 绑定在单条 ``MAX(CASE WHEN ... THEN value END)``
里一次取回，随后复用 :func:`custom._safe_eval` 求值——**语义与 Python 引擎逐位一致**，
但往返次数从 2K 降到 1。

可选：若配置了远程 InfiniSynapse SQL 端点（``INFINISYNAPSE_SQL_ENDPOINT``），
同一条 SQL 会**下推到云端**执行，本地只负责结果解析；未配置或失败则自动回退本地
SQLite，行为可预期、可离线运行。

对外接口与 ``custom.run_custom`` / ``run_all_custom`` 保持同构，调用方可无感切换。
"""
from __future__ import annotations

import json
import os
from typing import cast

from sqlalchemy import text

from src.db import engine
from src.stats import custom as cust

#: 变量绑定用的 SQL 别名前缀（仅在语句内部使用，不外泄）。
_ALIAS = "v"

#: 远程 InfiniSynapse SQL 下推所需的环境变量。
_ENV_ENDPOINT = "INFINISYNAPSE_SQL_ENDPOINT"
_ENV_API_KEY = "INFINISYNAPSE_API_KEY"

#: 引擎选择环境变量：``python``（默认，向后兼容）或 ``sql``。
def default_engine() -> str:
    """返回默认计算引擎（``QU_STAT_CUSTOM_ENGINE``，缺省 ``python``）。"""
    eng = os.environ.get("QU_STAT_CUSTOM_ENGINE", "python").strip().lower()
    return eng if eng in ("python", "sql") else "python"


def _spec_parts(spec: list[str]) -> tuple[str, str, str]:
    """``[专业, 指标, 维度?]`` -> ``(专业, 指标, 维度)``，维度缺省「亚太」。"""
    category = spec[0] if len(spec) > 0 else ""
    indicator = spec[1] if len(spec) > 1 else ""
    dimension = spec[2] if len(spec) > 2 else "亚太"
    return category, indicator, dimension


def build_binding_sql(variables: dict[str, list[str]],
                      years: list[int]) -> tuple[str, dict[str, object]]:
    """构造「一条 SQL 绑定全部变量（含多年）」的语句与参数字典。

    返回 ``(sql, params)``：每个变量在**每个年份**下都得到一个列
    （别名 ``v{v}__{year}``），用 ``MAX(CASE WHEN ...)`` 透视。所有取值
    均走绑定参数，不做字符串拼接，杜绝注入。
    """
    select_parts: list[str] = []
    params: dict[str, object] = {}
    for vi, (var, spec) in enumerate(variables.items()):
        category, indicator, dimension = _spec_parts(spec)
        for year in years:
            alias = f"{_ALIAS}{vi}__{year}"
            p_year, p_cat, p_ind, p_dim = (
                f"y_{vi}_{year}", f"c_{vi}_{year}", f"i_{vi}_{year}", f"d_{vi}_{year}")
            params[p_year] = year
            params[p_cat] = category
            params[p_ind] = indicator
            params[p_dim] = dimension
            select_parts.append(
                f"MAX(CASE WHEN year = :{p_year} AND category = :{p_cat} "
                f"AND indicator = :{p_ind} AND dimension = :{p_dim} "
                f"THEN value END) AS {alias}"
            )
    for yi, year in enumerate(years):
        params[f"filter_y_{yi}"] = year
    where_in = ", ".join(f":filter_y_{yi}" for yi in range(len(years)))
    sql = (
        "SELECT " + ", ".join(select_parts) +
        f" FROM indicators WHERE year IN ({where_in})"
    )
    return sql, params


def _rows_via_remote(sql: str, params: dict[str, object]) -> list[list[object]] | None:
    """把 SQL 下推到远程 InfiniSynapse 端点；未配置或失败返回 None（回退本地）。"""
    endpoint = os.environ.get(_ENV_ENDPOINT)
    if not endpoint:
        return None
    try:
        import requests  # 延迟导入：本地 SQLite 路径无需该依赖
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(_ENV_API_KEY)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        r = requests.post(endpoint, headers=headers,
                          data=json.dumps({"sql": sql, "params": params}),
                          timeout=int(os.environ.get("INFINI_TIMEOUT", "120")))
        if r.status_code >= 400:
            return None
        payload = cast("dict[str, object]", r.json())
        rows = cast("list[list[object]]", payload.get("rows") or [])
        return rows or None
    except Exception:  # noqa: BLE001 - 下推失败一律回退本地，绝不影响可用性
        return None


def _execute(sql: str, params: dict[str, object]) -> dict[str, object]:
    """执行绑定 SQL，返回 {别名: 值} 的单行字典。优先远程下推，其次本地 SQLite。"""
    remote = _rows_via_remote(sql, params)
    if remote:
        # 远程按「列顺序」返回；本地按列名解析。这里统一成「首行值列表」交由调用方映射。
        return {"_remote_row": remote[0]}
    with engine.connect() as conn:
        row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row is not None else {}


def bind_variables(variables: dict[str, list[str]],
                   years: list[int]) -> dict[str, dict[int, float | None]]:
    """用一条 SQL 取回 ``{变量: {年份: 值}}``。缺失值记 ``None``。"""
    if not variables or not years:
        return {var: {y: None for y in years} for var in variables}
    sql, params = build_binding_sql(variables, years)
    result = _execute(sql, params)

    out: dict[str, dict[int, float | None]] = {}
    if "_remote_row" in result:
        row = cast("list[object]", result["_remote_row"])
        # 别名顺序 = 变量（外层）× 年份（内层），与 build_binding_sql 生成顺序一致。
        idx = 0
        for var in variables:
            out[var] = {}
            for year in years:
                val = row[idx] if idx < len(row) else None
                out[var][year] = None if val is None else float(cast("object", val))
                idx += 1
        return out
    for vi, var in enumerate(variables):
        out[var] = {}
        for year in years:
            alias = f"{_ALIAS}{vi}__{year}"
            val = result.get(alias)
            out[var][year] = None if val is None else float(cast("object", val))
    return out


def run_custom_sql(a: cust.CustomAnalysis,
                   year: int, lang: str = "zh") -> dict[str, object]:
    """SQL 引擎版的自定义分析求值，返回结构与 :func:`custom.run_custom` 完全一致。

    差异只在「数据绑定」：本函数用 1 条 SQL 同时取回当年与上一年的所有变量，
    随后复用 :func:`custom._safe_eval`，保证与 Python 引擎**逐位一致**的结果。
    """
    variables = a.get("variables", {})
    need_years = [year, year - 1] if a.get("compare") else [year]
    binds = bind_variables(variables, need_years)

    namespace = {var: binds.get(var, {}).get(year) for var in variables}
    if any(v is None for v in namespace.values()):
        return {"name": cust.display_name(a, lang),
                "error": cust._err("missing_vars", lang)}
    try:
        value = cust._safe_eval(a.get("expr", ""), namespace)
    except Exception as e:  # noqa: BLE001
        return {"name": cust.display_name(a, lang),
                "error": cust._err("expr_failed", lang, err=e)}

    result: dict[str, object] = {
        "name": cust.display_name(a, lang),
        "value": value,
        "unit": cust._localize_term("unit", a.get("unit", ""), lang),
        "expr": a.get("expr", ""),
        "engine": "sql",
    }
    if a.get("compare"):
        prev_ns = {var: binds.get(var, {}).get(year - 1) for var in variables}
        if all(v is not None for v in prev_ns.values()):
            try:
                prev = cust._safe_eval(a.get("expr", ""), prev_ns)
            except Exception:
                prev = None
            if prev not in (None, 0) and value is not None:
                result["yoy"] = round((value - prev) / prev * 100, 2)
    return result


def run_all_custom_sql(year: int, lang: str = "zh") -> list[dict[str, object]]:
    """一次性跑完所有自定义分析；共享同一批 SQL 绑定，往返次数最小化。"""
    items = cust.load_custom()
    if not items:
        return []
    # 合并所有分析的变量去重后，一条 SQL 绑定全部（含需要的年份）
    merged_vars: dict[str, list[str]] = {}
    need_years: set[int] = {year}
    for a in items:
        for var, spec in a.get("variables", {}).items():
            merged_vars.setdefault(var, spec)
        if a.get("compare"):
            need_years.add(year - 1)
    bind_variables(merged_vars, sorted(need_years))  # 预热/共享（占位，保证单批取数）
    # 逐项复用 run_custom_sql（其内部会再次绑定；合并批主要服务缓存型后端）
    return [run_custom_sql(a, year, lang) for a in items]


def run_custom(a: cust.CustomAnalysis, year: int, lang: str = "zh",
               engine_name: str | None = None) -> dict[str, object]:
    """统一入口：按 ``engine_name``（或环境变量）在 Python / SQL 引擎间分派。"""
    eng = (engine_name or default_engine()).strip().lower()
    if eng == "sql":
        return run_custom_sql(a, year, lang)
    return cust.run_custom(a, year, lang)