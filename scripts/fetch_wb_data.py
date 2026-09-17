"""抓取世界银行 Open Data，生成「亚太宏观（真实官方数据）」种子数据集。

为什么要落盘成 CSV：Vercel Serverless / 离线环境不能保证联网，演示时必须
**每个数字都可溯源**，因此把真实官方数据一次性抓回仓库内固化，冷启动直接读文件。

数据来源：World Bank Open Data API v2（公开、无需鉴权）
  https://api.worldbank.org/v2/country/<ISO>/indicator/<CODE>?format=json&date=YYYY:YYYY

用法：
  .venv/Scripts/python.exe scripts/fetch_wb_data.py                 # 默认 2019-2024
  .venv/Scripts/python.exe scripts/fetch_wb_data.py --from 2015 --to 2024
  .venv/Scripts/python.exe scripts/fetch_wb_data.py --economies EAP,CHN,JPN

输出：
  data/ap_macro.csv  （列：year,category,indicator,dimension,value,unit,note）

说明：CSV 文件名刻意不带 `indicators_` 前缀，避免被 .gitignore 的
`data/indicators_*.csv` 规则忽略——这份数据是**要提交进仓库**的种子数据。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ap_macro.csv"

WB_BASE = "https://api.worldbank.org/v2"
USER_AGENT = "qu-stat-system/0.1 (+public open data only)"

# 世界银行指标 code -> (中文指标名, 专业, 单位, 缩放)
# 缩放把原始值换算为常用单位：美元总量 ÷1e8 -> 亿美元；人口头数 ÷1e8 -> 亿人
WB_INDICATORS: dict[str, tuple[str, str, str, float]] = {
    "NY.GDP.MKTP.CD": ("国内生产总值(GDP)", "综合", "亿美元", 1e8),
    "NY.GDP.MKTP.KD.ZG": ("GDP增长率", "综合", "%", 1.0),
    "NY.GDP.PCAP.CD": ("人均GDP", "综合", "美元", 1.0),
    "FP.CPI.TOTL.ZG": ("通货膨胀率(CPI)", "综合", "%", 1.0),
    "NV.IND.TOTL.CD": ("工业增加值", "工业", "亿美元", 1e8),
    "NE.EXP.GNFS.CD": ("货物服务出口总额", "贸易", "亿美元", 1e8),
    "NE.IMP.GNFS.CD": ("货物服务进口总额", "贸易", "亿美元", 1e8),
    "SP.POP.TOTL": ("总人口", "人口", "亿人", 1e8),
    "SP.DYN.LE00.IN": ("预期寿命", "人口", "岁", 1.0),
    "SL.UEM.TOTL.ZS": ("失业率", "人口", "%", 1.0),
}

# ISO / 世界银行地区码 -> 维度名（中英并列，便于前端 i18n 直接命中）
# EAS = East Asia & Pacific（全部收入水平，与日本/韩国/新加坡/澳大利亚同级可比）
# EAP = East Asia & Pacific (excluding high income)，仅作对照
ECONOMIES: dict[str, str] = {
    "EAS": "亚太",
    "EAP": "亚太(发展中)",
    "CHN": "中国",
    "JPN": "日本",
    "KOR": "韩国",
    "IND": "印度",
    "IDN": "印度尼西亚",
    "THA": "泰国",
    "VNM": "越南",
    "MYS": "马来西亚",
    "PHL": "菲律宾",
    "SGP": "新加坡",
}

DEFAULT_FROM, DEFAULT_TO = 2019, 2024


def _get_json(url: str, timeout: int = 30) -> Any:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    # 绕过系统代理直连：api.worldbank.org 本机可直连，走 127.0.0.1:7897 反而失败
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch(iso: str, code: str, y_from: int, y_to: int) -> list[dict[str, Any]]:
    """抓取某经济体某指标在 [y_from, y_to] 区间的全部年度记录。"""
    params = urllib.parse.urlencode({
        "format": "json", "date": f"{y_from}:{y_to}", "per_page": "100"})
    url = f"{WB_BASE}/country/{iso}/indicator/{code}?{params}"
    try:
        data = _get_json(url)
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        print(f"  [跳过] {iso}/{code}: {exc}")
        return []
    if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
        return [r for r in data[1] if isinstance(r, dict)]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description="抓取世界银行开放数据（亚太宏观）")
    ap.add_argument("--from", dest="y_from", type=int, default=DEFAULT_FROM)
    ap.add_argument("--to", dest="y_to", type=int, default=DEFAULT_TO)
    ap.add_argument("--economies", default=",".join(ECONOMIES),
                    help="逗号分隔的 ISO/地区码，默认全部")
    ap.add_argument("--sleep", type=float, default=0.25, help="请求间隔(秒)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    isos = [s.strip().upper() for s in args.economies.split(",") if s.strip()]
    rows: list[dict[str, Any]] = []
    total = len(isos) * len(WB_INDICATORS)
    done = 0

    for iso in isos:
        dim = ECONOMIES.get(iso, iso)
        for code, (name, cat, unit, scale) in WB_INDICATORS.items():
            done += 1
            recs = fetch(iso, code, args.y_from, args.y_to)
            hit = 0
            for r in recs:
                val = r.get("value")
                date = str(r.get("date") or "")
                if val is None or not date.isdigit():
                    continue
                rows.append({
                    "year": int(date),
                    "category": cat,
                    "indicator": name,
                    "dimension": dim,
                    "value": round(float(val) / scale, 4),
                    "unit": unit,
                    "note": f"来源：世界银行OpenData({code}, {iso})",
                })
                hit += 1
            print(f"[{done}/{total}] {iso} {code} {name}: {hit} 年")
            time.sleep(args.sleep)

    rows.sort(key=lambda r: (r["dimension"], r["indicator"], r["year"]))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["year", "category", "indicator",
                           "dimension", "value", "unit", "note"])
        w.writeheader()
        w.writerows(rows)

    years = sorted({r["year"] for r in rows})
    dims = sorted({r["dimension"] for r in rows})
    print(f"\nOK -> {out}")
    print(f"   {len(rows)} 行 / {len(dims)} 个维度 / 年份 {years}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
