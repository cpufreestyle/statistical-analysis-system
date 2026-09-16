"""各统计专业指标计算。

把统计业务拆成可计算的指标函数，输入结构化数据、输出统计结果。
数据全部来自真实公开数据（世界银行 Open Data + 国家统计局 / 海关总署公开发布）。

维度（dimension）约定：
  亚太 / 亚太(发展中) / 中国 / 日本 / 韩国 / 印度 / 印度尼西亚 / 泰国 /
  越南 / 马来西亚 / 菲律宾 / 新加坡 / 澳大利亚 / 美国

`_get()` 按 `DIMENSION_PREFERENCE` 自动回退取数，避免某个维度缺指标时整块空掉。
"""
from __future__ import annotations

from src.db import query_indicators
from src.stats.core import yoy, share, rank_items, fmt_pct

# 取数时的维度回退顺序：默认看亚太，亚太没有的指标落到中国口径
DIMENSION_PREFERENCE: tuple[str, ...] = ("亚太", "中国", "全国", "全区")

# 通用取数优先的专业顺序（用于「按维度挑卡片指标」）
CATEGORY_PRIORITY: tuple[str, ...] = ("综合", "贸易", "投资", "工业", "人口", "服务业", "农业")

# 各维度看板卡片要展示的指标（按展示优先级）
CARD_INDICATORS: dict[str, list[tuple[str, str]]] = {
    "亚太": [
        ("综合", "国内生产总值(GDP)"),
        ("综合", "人均GDP"),
        ("贸易", "货物服务出口总额"),
        ("工业", "工业增加值"),
        ("人口", "总人口"),
    ],
    "中国": [
        ("综合", "地区生产总值"),
        ("综合", "社会消费品零售总额"),
        ("投资", "固定资产投资总额"),
        ("贸易", "货物进出口总额"),
        ("人口", "常住人口"),
    ],
}

CARD_COUNT = 5


def _find(year: int, category: str, indicator: str,
          dimension: str | None = None) -> tuple[float | None, str | None]:
    """按维度回退顺序取一个指标值，返回 (值, 实际命中的维度)。"""
    candidates: list[str] = []
    if dimension:
        candidates.append(dimension)
    candidates += [d for d in DIMENSION_PREFERENCE if d not in candidates]
    for dim in candidates:
        rows = query_indicators(year=year, category=category,
                                indicator=indicator, dimension=dim)
        if rows:
            return rows[0]["value"], dim
    # 最后兜底：不限维度（用户导入的自定义维度也能取到）
    rows = query_indicators(year=year, category=category, indicator=indicator)
    if rows:
        return rows[0]["value"], rows[0]["dimension"]
    return None, None


def _pick(year: int, pairs: list[tuple[str, str]],
          dimension: str | None = None) -> tuple[str | None, str | None, str | None]:
    """在候选指标中挑出第一个有数据的，返回 (维度, 专业, 指标)。

    这是各专业统计函数的「锚点」：**先确定维度，再在该维度内取值**。
    绝不允许同一个结果里混用不同维度的数字（否则同比会算出跨口径的荒谬值）。
    """
    dims: list[str] = []
    if dimension:
        dims.append(dimension)
    dims += [d for d in DIMENSION_PREFERENCE if d not in dims]
    for dim in dims:
        for category, indicator in pairs:
            rows = query_indicators(year=year, category=category,
                                    indicator=indicator, dimension=dim)
            if rows:
                return dim, category, indicator
    return None, None, None


def _in(year: int, category: str, indicator: str,
        dimension: str | None) -> float | None:
    """严格在指定维度内取值（不做回退），保证口径一致。"""
    if not dimension:
        return None
    rows = query_indicators(year=year, category=category,
                            indicator=indicator, dimension=dimension)
    return rows[0]["value"] if rows else None


def _unit(year: int, category: str, indicator: str,
          dimension: str | None) -> str:
    """该行数据的实际单位。

    结果的键里带单位（如 ``工业增加值(亿美元)``），单位必须来自数据行本身：
    同一指标名在库里的口径可能不同——世界银行来源是「亿美元」，国家统计局来源是「亿元」，
    早先写死「(亿元)」会把美元数值标成人民币量级。
    """
    if not dimension:
        return ""
    rows = query_indicators(year=year, category=category,
                            indicator=indicator, dimension=dimension)
    return str(rows[0]["unit"]) if rows else ""


def _keyed(indicator: str, unit: str) -> str:
    """按实际单位拼接结果键；无单位时退化为纯指标名。"""
    return f"{indicator}({unit})" if unit else indicator


def _get(year: int, category: str, indicator: str,
         dimension: str | None = None) -> float | None:
    return _find(year, category, indicator, dimension)[0]


def value_of(year: int, category: str, indicator: str,
             dimension: str | None = None) -> float | None:
    """公开取数接口（供公报 / 报表等模块调用）。"""
    return _find(year, category, indicator, dimension)[0]


def _prev(year: int, category: str, indicator: str,
          dimension: str | None = None) -> float | None:
    """同维度、同指标的上一年值（口径一致，供同比计算）。"""
    return _get(year - 1, category, indicator, dimension)


# ---------------------------------------------------------------------------
# 维度 / 卡片（看板首页）
# ---------------------------------------------------------------------------
def available_dimensions() -> list[str]:
    """当前库中出现过的全部维度，按偏好顺序排在前，其余按名称排序。"""
    dims = {r["dimension"] for r in query_indicators()}
    head = [d for d in DIMENSION_PREFERENCE if d in dims]
    return head + sorted(dims - set(head))


def available_years() -> list[int]:
    """当前库中出现过的全部年份（倒序）。"""
    return sorted({int(r["year"]) for r in query_indicators()}, reverse=True)


def dimension_cards(year: int, dimension: str) -> list[dict[str, object]]:
    """按维度生成看板卡片（真实数据，附同比与出处）。

    先取 `CARD_INDICATORS` 里为该维度预设的指标，不足则按专业优先级补齐。
    """
    rows = query_indicators(year=year, dimension=dimension)
    picked: list[dict[str, object]] = []
    used: set[tuple[str, str]] = set()

    def _emit(category: str, indicator: str) -> None:
        r = next((x for x in rows
                  if x["category"] == category and x["indicator"] == indicator), None)
        if r is None or (category, indicator) in used:
            return
        used.add((category, indicator))
        prev = _get(year - 1, category, indicator, dimension)
        picked.append({
            "label": indicator,
            "value": r["value"],
            "unit": r["unit"],
            "dimension": dimension,
            "note": r["note"],
            "yoy": fmt_pct(yoy(r["value"], prev)) if prev is not None else "",
        })

    for category, indicator in CARD_INDICATORS.get(dimension, []):
        _emit(category, indicator)

    if len(picked) < CARD_COUNT:
        ordered = sorted(
            rows,
            key=lambda r: (CATEGORY_PRIORITY.index(r["category"])
                           if r["category"] in CATEGORY_PRIORITY else 99,
                           r["indicator"]),
        )
        for r in ordered:
            if len(picked) >= CARD_COUNT:
                break
            _emit(r["category"], r["indicator"])
    return picked[:CARD_COUNT]


def economy_ranking(year: int, category: str, indicator: str,
                    exclude: tuple[str, ...] = ("亚太", "亚太(发展中)")) -> list[dict[str, object]]:
    """按某指标给各经济体排名（真实数据，用于替代原先的「分街镇排名」）。"""
    rows = [
        (r["dimension"], r["value"]) for r in query_indicators(
            year=year, category=category, indicator=indicator)
        if r["dimension"] not in exclude
    ]
    if not rows:
        return []
    return [{"经济体": n, "数值": v, "排名": rk} for n, v, rk in rank_items(rows)]


def all_categories() -> list[str]:
    """库中实际存在的专业分类（供前端筛选下拉动态生成）。"""
    cats = {r["category"] for r in query_indicators()}
    head = [c for c in CATEGORY_PRIORITY if c in cats]
    return head + sorted(cats - set(head))


# ---------------------------------------------------------------------------
# 各专业统计
# ---------------------------------------------------------------------------
def gdp_overview(year: int, prev_year: int | None = None,
                 dimension: str | None = None) -> dict[str, object]:
    dim, cat, iname = _pick(
        year, [("综合", "地区生产总值"), ("综合", "国内生产总值(GDP)")], dimension)
    if dim is None or cat is None or iname is None:
        return {"指标": "地区生产总值", "年份": year, "维度": "—",
                "数值": None, "同比": "—"}
    cur = _in(year, cat, iname, dim)
    prev = _in(year - 1, cat, iname, dim)
    return {
        # 标签用命中的真实指标名：世界银行口径是「国内生产总值(GDP)」，
        # 国家统计局口径是「地区生产总值」。早先把前者统一改写成后者，
        # 会让亚太等世界银行维度被标成 NBS 口径（并且注释文案互相矛盾）。
        "指标": iname,
        "年份": year,
        "维度": dim,
        _keyed("数值", _unit(year, cat, iname, dim)): cur,
        "同比": fmt_pct(yoy(cur, prev)) if prev is not None else "—",
    }


def industry_stats(year: int, dimension: str | None = None) -> dict[str, object]:
    dim, _, _ = _pick(year, [("工业", "工业增加值"),
                             ("工业", "规模以上工业增加值"),
                             ("工业", "规模以上工业总产值")], dimension)
    ranking = economy_ranking(year, "工业", "工业增加值")
    return {
        "维度": dim or "—",
        _keyed("工业增加值", _unit(year, "工业", "工业增加值", dim)):
            _in(year, "工业", "工业增加值", dim),
        _keyed("规上工业增加值", _unit(year, "工业", "规模以上工业增加值", dim)):
            _in(year, "工业", "规模以上工业增加值", dim),
        "分经济体排名": ranking[:10],
    }


def trade_stats(year: int, dimension: str | None = None) -> dict[str, object]:
    dim, _, _ = _pick(year, [("贸易", "货物服务出口总额"),
                             ("贸易", "货物进出口总额"),
                             ("贸易", "社会消费品零售总额")], dimension)
    out: dict[str, object] = {"维度": dim or "—"}
    for indicator in ("货物服务出口总额", "货物服务进口总额",
                      "货物进出口总额", "社会消费品零售总额",
                      "限额以上商品销售额"):
        v = _in(year, "贸易", indicator, dim)
        if v is not None:
            out[_keyed(indicator, _unit(year, "贸易", indicator, dim))] = v
    return out


def investment_stats(year: int, dimension: str | None = None) -> dict[str, object]:
    dim, _, _ = _pick(year, [("投资", "固定资产投资总额")], dimension)
    total = _in(year, "投资", "固定资产投资总额", dim)
    secondary = _in(year, "投资", "第二产业投资", dim)
    tertiary = _in(year, "投资", "第三产业投资", dim)
    out: dict[str, object] = {
        "维度": dim or "—",
        _keyed("固定资产投资总额", _unit(year, "投资", "固定资产投资总额", dim)): total,
    }
    if secondary is not None:
        out[_keyed("第二产业投资", _unit(year, "投资", "第二产业投资", dim))] = secondary
        out["二产投资占比(%)"] = share(secondary, total)
    if tertiary is not None:
        out[_keyed("第三产业投资", _unit(year, "投资", "第三产业投资", dim))] = tertiary
    return out


def population_stats(year: int, dimension: str | None = None) -> dict[str, object]:
    dim, _, _ = _pick(year, [("人口", "总人口"), ("人口", "常住人口")], dimension)
    out: dict[str, object] = {"维度": dim or "—"}
    for indicator, unit in (("总人口", "亿人"), ("常住人口", "万人"),
                            ("居民人均可支配收入", "元"),
                            ("预期寿命", "岁"), ("失业率", "%")):
        v = _in(year, "人口", indicator, dim)
        if v is not None:
            out[f"{indicator}({unit})"] = v
    return out


def service_stats(year: int, dimension: str | None = None) -> dict[str, object]:
    dim, _, _ = _pick(year, [("服务业", "规模以上服务业营业收入"),
                             ("综合", "第三产业增加值")], dimension)
    rev = _in(year, "服务业", "规模以上服务业营业收入", dim)
    added = _in(year, "综合", "第三产业增加值", dim)
    out: dict[str, object] = {"维度": dim or "—"}
    if rev is not None:
        prev = _in(year - 1, "服务业", "规模以上服务业营业收入", dim)
        out[_keyed("规模以上服务业营业收入",
                   _unit(year, "服务业", "规模以上服务业营业收入", dim))] = rev
        out["同比"] = fmt_pct(yoy(rev, prev)) if prev is not None else "—"
    if added is not None:
        out[_keyed("第三产业增加值", _unit(year, "综合", "第三产业增加值", dim))] = added
    return out


def agriculture_stats(year: int, dimension: str | None = None) -> dict[str, object]:
    dim, _, _ = _pick(year, [("农业", "农业总产值"), ("综合", "第一产业增加值")],
                      dimension)
    out: dict[str, object] = {"维度": dim or "—"}
    out_val = _in(year, "农业", "农业总产值", dim)
    if out_val is not None:
        out[_keyed("农业总产值", _unit(year, "农业", "农业总产值", dim))] = out_val
    added = _in(year, "综合", "第一产业增加值", dim)
    if added is not None:
        out[_keyed("第一产业增加值", _unit(year, "综合", "第一产业增加值", dim))] = added
    return out


def inflation_stats(year: int, dimension: str | None = None) -> dict[str, object]:
    dim, _, _ = _pick(year, [("综合", "通货膨胀率(CPI)")], dimension)
    return {"维度": dim or "—", "通货膨胀率(CPI)": _in(year, "综合", "通货膨胀率(CPI)", dim)}
