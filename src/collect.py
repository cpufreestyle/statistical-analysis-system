"""全网数据采集：从公开、无需鉴权的开放数据源抓取宏观统计数据，写入本地 indicators 表。

设计原则：
- 只抓取**公开开放数据**（如世界银行 Open Data API），不抓取任何需登录 / 付费 /
  违反站点服务条款的内容；尊重速率限制与 robots。
- 通过系统 HTTP(S)_PROXY 联网（与云端 AI 一致），结果带 source 标注便于溯源。
- 可插拔数据源：每个源实现 fetch -> list[IndicatorRow]；registry 按名称调度。
- 默认数据源为世界银行（覆盖全国与全球主要经济体），可扩展接入更多开放数据源。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, TypedDict, cast

from src.db import CONFIG, IndicatorRow, upsert_indicators


class CollectError(Exception):
    """数据采集相关错误。"""


DEFAULT_TIMEOUT = 30
USER_AGENT = "qu-stat-system/0.1 (+local analysis; public open data only)"


def _http_get_json(url: str, params: dict[str, str] | None = None,
                  timeout: int = DEFAULT_TIMEOUT) -> Any:
    """发起 GET 请求并解析 JSON；失败时抛 CollectError。"""
    if params:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise CollectError(f"请求失败 {url}: {e}") from e
    except json.JSONDecodeError as e:
        raise CollectError(f"非 JSON 响应 {url}: {e}") from e


# ---------------------------------------------------------------------------
# 世界银行开放数据（无需鉴权，按国家/指标/年份查询）
# ---------------------------------------------------------------------------
WB_BASE = "https://api.worldbank.org/v2"


class WBIndicator(TypedDict):
    name: str
    category: str
    unit: str
    scale: float


# code -> (中文名, 专业, 单位, 缩放)。scale 把原始值换算为常用单位
# （美元计总量 ÷1e8 得「亿美元」，人口头数 ÷1e8 得「亿人」；比率不变）。
WB_INDICATORS: dict[str, WBIndicator] = {
    "NY.GDP.MKTP.CD": {"name": "国内生产总值(GDP)", "category": "综合", "unit": "亿美元", "scale": 1e8},
    "NY.GDP.MKTP.KD.ZG": {"name": "GDP增长率", "category": "综合", "unit": "%", "scale": 1.0},
    "NY.GDP.PCAP.CD": {"name": "人均GDP", "category": "综合", "unit": "美元", "scale": 1.0},
    "SP.POP.TOTL": {"name": "总人口", "category": "人口", "unit": "亿人", "scale": 1e8},
    "SP.DYN.LE00.IN": {"name": "预期寿命", "category": "人口", "unit": "岁", "scale": 1.0},
    "SL.UEM.TOTL.ZS": {"name": "失业率", "category": "人口", "unit": "%", "scale": 1.0},
    "FP.CPI.TOTL.ZG": {"name": "通货膨胀率(CPI)", "category": "综合", "unit": "%", "scale": 1.0},
    "NE.EXP.GNFS.CD": {"name": "货物服务出口总额", "category": "贸易", "unit": "亿美元", "scale": 1e8},
    "NE.IMP.GNFS.CD": {"name": "货物服务进口总额", "category": "贸易", "unit": "亿美元", "scale": 1e8},
    "NV.IND.TOTL.CD": {"name": "工业增加值", "category": "工业", "unit": "亿美元", "scale": 1e8},
}

# CLI 友好别名
WB_ALIASES: dict[str, str] = {
    "gdp": "NY.GDP.MKTP.CD", "gdpgrowth": "NY.GDP.MKTP.KD.ZG",
    "gdppc": "NY.GDP.PCAP.CD", "population": "SP.POP.TOTL",
    "life": "SP.DYN.LE00.IN", "unemployment": "SL.UEM.TOTL.ZS",
    "cpi": "FP.CPI.TOTL.ZG", "export": "NE.EXP.GNFS.CD",
    "import": "NE.IMP.GNFS.CD", "industry": "NV.IND.TOTL.CD",
}

# ISO 国家码 -> 中文维度名（用于全球对比时的 dimension）
COUNTRY_CN: dict[str, str] = {
    "CHN": "全国", "USA": "美国", "JPN": "日本", "DEU": "德国",
    "IND": "印度", "GBR": "英国", "FRA": "法国", "BRA": "巴西",
    "RUS": "俄罗斯", "KOR": "韩国", "CAN": "加拿大", "AUS": "澳大利亚",
    "IDN": "印度尼西亚", "MEX": "墨西哥",
}


def _collection_cfg() -> dict[str, Any]:
    cfg = CONFIG.get("collection")
    if not isinstance(cfg, dict):
        return {}
    return cast("dict[str, Any]", cfg)


def _resolve_codes(specs: list[str] | None) -> list[str]:
    """把用户传入的指标（worldbank code 或别名）解析为 worldbank code 列表。"""
    if not specs:
        src = _collection_cfg().get("sources", {})
        wb = src.get("worldbank", {}) if isinstance(src, dict) else {}
        ind = wb.get("indicators", {}) if isinstance(wb, dict) else {}
        if isinstance(ind, dict) and ind:
            return list(ind.keys())
        return list(WB_INDICATORS.keys())
    out: list[str] = []
    for s in specs:
        s = s.strip()
        out.append(WB_ALIASES.get(s, s))
    return out


def _fetch_wb(indicator: str, iso: str, date: str) -> list[dict[str, Any]]:
    url = f"{WB_BASE}/country/{iso}/indicator/{indicator}"
    data = _http_get_json(url, {"format": "json", "date": date, "per_page": "100"})
    if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
        return [cast("dict[str, Any]", r) for r in data[1]]
    return []


def collect_worldbank(year: int | None = None, country: str | None = None,
                      indicators: list[str] | None = None,
                      dimension: str | None = None,
                      sleep: float | None = None) -> int:
    """抓取单个国家的世界银行指标，写入 indicators 表。返回写入条数。"""
    cfg = _collection_cfg()
    year = year or int(cfg.get("year", 2024))
    country = (country or str(cfg.get("country", "CHN")) or "CHN").upper()
    sleep = sleep if sleep is not None else float(cfg.get("rate_limit_sleep", 0.5))
    dim = dimension or COUNTRY_CN.get(country, country)
    codes = _resolve_codes(indicators)

    rows: list[IndicatorRow] = []
    date = str(year)
    for code in codes:
        spec = WB_INDICATORS.get(code)
        if spec is None:
            print(f"[采集跳过] 未知指标 {code}（可选别名：{list(WB_ALIASES)}）")
            continue
        try:
            recs = _fetch_wb(code, country, date)
        except CollectError as e:
            print(f"[采集跳过] {code}: {e}")
            continue
        if not recs:
            continue
        val = recs[0].get("value")
        if val is None:
            continue
        rows.append(IndicatorRow(
            year=year, category=spec["category"], indicator=spec["name"],
            dimension=dim, value=round(float(val) / spec["scale"], 4),
            unit=spec["unit"], note=f"来源：世界银行OpenData({code})",
        ))
        time.sleep(sleep)
    if rows:
        upsert_indicators(rows)
    return len(rows)


def collect_global(year: int | None = None, indicators: list[str] | None = None,
                   countries: list[str] | None = None,
                   sleep: float | None = None) -> int:
    """抓取多个经济体（全球对比），每国一个 dimension。返回写入条数。"""
    countries = countries or ["CHN", "USA", "JPN", "DEU", "IND",
                              "GBR", "FRA", "BRA", "RUS", "KOR"]
    total = 0
    for iso in countries:
        total += collect_worldbank(year=year, country=iso,
                                   indicators=indicators, sleep=sleep)
    return total


SOURCES: dict[str, Any] = {
    "worldbank": collect_worldbank,
    "global": collect_global,
}


def collect(source: str, **kwargs: Any) -> int:
    """按数据源名称调度采集。source ∈ {worldbank, global}。"""
    fn = SOURCES.get(source)
    if fn is None:
        raise CollectError(f"未知数据源：{source}（可选：{list(SOURCES)}）")
    return fn(**kwargs)
