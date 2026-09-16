"""自然语言式查询：把中/英文问句解析为统计口径（本地规则，无需云端）。

参考 agent_infini 的 `task ask` 多轮分析思路，但用本地关键词路由实现。
支持类似：
  "2024年GDP多少" / "2024 GDP"
  "工业增加值" / "industrial value added"
  "货物出口" / "exports of goods and services"
  "各经济体人口排名" / "population by economy"
"""
from __future__ import annotations

import re
from typing import Callable

from src.stats import indicators as ind
from src.stats import custom as cust
from src import knowledge

DEFAULT_YEAR = 2024

# 每个关键词 -> (输出键, 统计函数)。gdp 需要两年对比，用 lambda 包一层。
# 中英文键混排，英文键一律小写，匹配前会把问句转小写。
CATEGORY_MAP: dict[str, tuple[str, Callable[[int, str | None], dict[str, object]]]] = {
    "gdp": ("GDP", lambda y, d: ind.gdp_overview(y, y - 1, d)),
    "gross domestic product": ("GDP", lambda y, d: ind.gdp_overview(y, y - 1, d)),
    "工业": ("工业", ind.industry_stats),
    "规上工业": ("工业", ind.industry_stats),
    "industry": ("工业", ind.industry_stats),
    "industrial": ("工业", ind.industry_stats),
    "贸易": ("贸易", ind.trade_stats),
    "社零": ("贸易", ind.trade_stats),
    "消费": ("贸易", ind.trade_stats),
    "进出口": ("贸易", ind.trade_stats),
    "trade": ("贸易", ind.trade_stats),
    "retail": ("贸易", ind.trade_stats),
    "export": ("贸易", ind.trade_stats),
    "import": ("贸易", ind.trade_stats),
    "投资": ("投资", ind.investment_stats),
    "固定资产": ("投资", ind.investment_stats),
    "investment": ("投资", ind.investment_stats),
    "人口": ("人口", ind.population_stats),
    "居民": ("人口", ind.population_stats),
    "population": ("人口", ind.population_stats),
    "demograph": ("人口", ind.population_stats),
    "unemployment": ("人口", ind.population_stats),
    "life expectancy": ("人口", ind.population_stats),
    "失业率": ("人口", ind.population_stats),
    "预期寿命": ("人口", ind.population_stats),
    "服务业": ("服务业", ind.service_stats),
    "规上服务业": ("服务业", ind.service_stats),
    "service": ("服务业", ind.service_stats),
    "农业": ("农业", ind.agriculture_stats),
    "agriculture": ("农业", ind.agriculture_stats),
    "agricultural": ("农业", ind.agriculture_stats),
    "通货膨胀": ("综合", ind.inflation_stats),
    "inflation": ("综合", ind.inflation_stats),
    "cpi": ("综合", ind.inflation_stats),
}

# 英文口语表达 -> 中文指标名。命中后会把这些中文词附到问句末尾，
# 从而复用同一套「指标名直命中」逻辑。
EN_TERMS: list[tuple[str, str]] = [
    ("gross domestic product", "国内生产总值(GDP)"),
    ("gdp per capita", "人均GDP"),
    ("per capita gdp", "人均GDP"),
    ("per-capita gdp", "人均GDP"),
    ("retail sales", "社会消费品零售总额"),
    ("consumer goods", "社会消费品零售总额"),
    ("fixed asset investment", "固定资产投资总额"),
    ("fixed-asset investment", "固定资产投资总额"),
    ("resident population", "常住人口"),
    ("total population", "总人口"),
    ("disposable income", "居民人均可支配收入"),
    ("life expectancy", "预期寿命"),
    ("old-age", "预期寿命"),
    ("unemployment rate", "失业率"),
    ("inflation rate", "通货膨胀率(CPI)"),
    ("consumer price", "通货膨胀率(CPI)"),
    ("exports of goods", "货物服务出口总额"),
    ("imports of goods", "货物服务进口总额"),
    ("industry value added", "工业增加值"),
    ("industrial value added", "工业增加值"),
    ("manufacturing value added", "工业增加值"),
    ("merchandise trade", "货物进出口总额"),
    ("primary industry", "第一产业增加值"),
    ("secondary industry", "第二产业增加值"),
    ("tertiary industry", "第三产业增加值"),
]

# 指标名直命中时，最多返回多少条（跨维度去重后）
_MAX_INDICATOR_HITS = 12


def parse_year(text: str, default: int = DEFAULT_YEAR) -> int:
    m = re.search(r"(20\d{2})", text)
    return int(m.group(1)) if m else default


def _normalize(text: str) -> str:
    """把英文表达补成中文口径词，使中英文问句走同一套匹配逻辑。"""
    lower = text.lower()
    extra = [zh for en, zh in EN_TERMS if en in lower]
    return text + (" " + " ".join(extra) if extra else "")


def _match_indicators(text: str, year: int, dimension: str | None,
                      lang: str = "en") -> list[dict[str, object]]:
    """在指标库中查找名称被问句直接提及的指标，返回该年数值。

    指标在库里存的是中文规范名，所以英文问句（``GDP growth``）走不通——
    这里同时拿 ``labels`` 的英文标签比对，让中英文问句命中同一批指标。
    输出的 ``指标`` 仍是中文规范名，由标签层统一本地化。
    """
    from src import labels
    from src.db import query_indicators

    rows = query_indicators(year=year, dimension=dimension) if dimension \
        else query_indicators(year=year)
    if not dimension:
        # 未指定维度时优先看默认口径，避免把十几个经济体全列出来
        order = {d: i for i, d in enumerate(ind.DIMENSION_PREFERENCE)}
        rows = sorted(rows, key=lambda r: order.get(r["dimension"], 99))
    probe = text.lower()
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, object]] = []
    for r in rows:
        name = r["indicator"]
        if not name:
            continue
        english = labels.label("indicator", name, lang)
        # 英文标签至少 3 字符才参与匹配，避免短标签（如 "%"）造成误命中
        hit_en = len(english) >= 3 and english.lower() in probe
        if name not in text and not hit_en:
            continue
        key = (name, r["dimension"])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "指标": name,
            "维度": r["dimension"],
            "数值": r["value"],
            "单位": r["unit"],
            "说明": r["note"],
        })
        if len(out) >= _MAX_INDICATOR_HITS:
            break
    return out


def ask(text: str, default_year: int = DEFAULT_YEAR, with_knowledge: bool = True,
        dimension: str | None = None, lang: str = "en") -> dict[str, object]:
    year = parse_year(text, default_year)
    result = _ask_core(text, year, dimension, lang)
    if with_knowledge:
        ctx = knowledge.retrieve_context(text, lang=lang)
        if ctx:
            result["知识库参考"] = ctx
    return result


def _ask_core(text: str, year: int, dimension: str | None,
              lang: str = "en") -> dict[str, object]:
    probe = _normalize(text)
    t = probe.lower()
    # 1) 自定义分析优先：命中名称即按用户定义公式求值（中文名 / 英文名都认）
    for a in cust.load_custom():
        for candidate in (a.get("name", ""), a.get("name_en", "")):
            if candidate and candidate.lower() in t:
                return {"年份": year,
                        cust.display_name(a, lang): cust.run_custom(a, year, lang)}
    # 2) 具体指标名直命中：问到「社会消费品零售总额」/「retail sales」这类要答到点，
    #    优先级高于宽泛的专业关键词（否则「retail sales」会被"贸易"整块吞掉）
    hits = _match_indicators(probe, year, dimension, lang)
    if hits:
        return {"年份": year, "匹配指标": hits}
    # 3) 专业关键词路由
    for kw, (key, fn) in CATEGORY_MAP.items():
        if kw in t:
            return {"年份": year, key: fn(year, dimension)}
    # 4) 兜底：返回该维度的概览卡片
    dim = dimension or ind.DIMENSION_PREFERENCE[0]
    return {
        "年份": year,
        "维度": dim,
        "指标概览": [
            {"指标": c["label"], "数值": c["value"],
             "单位": c["unit"], "维度": c["dimension"]}
            for c in ind.dimension_cards(year, dim)
        ],
    }
