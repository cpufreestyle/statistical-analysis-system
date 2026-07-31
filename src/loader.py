"""数据导入：CSV/Excel 导入 + 示例数据生成。

参考 agent_infini 的 `db` / `task file` 思路：把外部数据载入统一指标宽表。
"""
from __future__ import annotations

from typing import cast

from src.db import IndicatorRow, upsert_indicators


def load_file(path: str) -> int:
    """导入 CSV/Excel，要求列为 year,category,indicator,dimension,value,unit,note。"""
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError(
            "导入文件需要 pandas / openpyxl，请先安装：pip install '.[files]'"
        )

    if path.endswith(".csv"):
        df: pd.DataFrame = pd.read_csv(path)
    else:
        # pandas-stubs 的 read_excel 签名含 Unknown 参数，触发 reportUnknownMemberType；
        # 此为库本身类型缺陷，针对性忽略。
        df = pd.read_excel(path)  # type: ignore[reportUnknownMemberType]
    rows: list[IndicatorRow] = cast("list[IndicatorRow]", df.to_dict("records"))
    return upsert_indicators(rows)


def generate_sample_data(year: int = 2024) -> int:
    """生成亚太口径的示例统计指标（量级贴近东亚太平洋地区合计，仅作离线演示）。

    维度统一为「亚太」；如需分经济体数据，请用 `collect` 从网络采集。
    """
    rows: list[IndicatorRow] = [
        # 综合
        IndicatorRow(year=year, category="综合", indicator="地区生产总值", dimension="亚太",
                     value=2376000.0, unit="亿元", note="示例值，贴近亚太(EAP)合计量级"),
        IndicatorRow(year=year - 1, category="综合", indicator="地区生产总值", dimension="亚太",
                     value=2230000.0, unit="亿元", note="上年基数（示例）"),
        # 工业
        IndicatorRow(year=year, category="工业", indicator="规模以上工业总产值", dimension="亚太",
                     value=3000000.0, unit="亿元", note="示例"),
        IndicatorRow(year=year, category="工业", indicator="规模以上工业增加值", dimension="亚太",
                     value=800000.0, unit="亿元", note="示例"),
        # 贸易
        IndicatorRow(year=year, category="贸易", indicator="社会消费品零售总额", dimension="亚太",
                     value=1500000.0, unit="亿元", note="示例"),
        IndicatorRow(year=year, category="贸易", indicator="限额以上商品销售额", dimension="亚太",
                     value=1600000.0, unit="亿元", note="示例"),
        # 投资
        IndicatorRow(year=year, category="投资", indicator="固定资产投资总额", dimension="亚太",
                     value=1700000.0, unit="亿元", note="示例"),
        IndicatorRow(year=year, category="投资", indicator="第二产业投资", dimension="亚太",
                     value=560000.0, unit="亿元", note="示例"),
        IndicatorRow(year=year, category="投资", indicator="第三产业投资", dimension="亚太",
                     value=1090000.0, unit="亿元", note="示例"),
        # 人口
        IndicatorRow(year=year, category="人口", indicator="常住人口", dimension="亚太",
                     value=21.0, unit="亿人", note="示例"),
        IndicatorRow(year=year, category="人口", indicator="居民人均可支配收入", dimension="亚太",
                     value=38000, unit="元", note="示例"),
    ]
    # 分经济体工业产值示例（少量，演示分维度；采集可扩展到全部经济体）
    economies = ["中国", "日本", "韩国", "印度", "印度尼西亚"]
    for i, p in enumerate(economies):
        rows.append(IndicatorRow(
            year=year, category="工业", indicator="规模以上工业总产值", dimension=p,
            value=round(3000000.0 / len(economies) * (1 + i * 0.15), 2),
            unit="亿元", note="示例"))
    return upsert_indicators(rows)


# 全国口径多年度示例数据：year -> {indicator: (value, unit, note)}
_NATIONAL_YEARS: dict[int, dict[str, tuple[float, str, str]]] = {
    2024: {
        "地区生产总值": (2110.57, "亿元", "示例值，贴近2024公报量级"),
        "规模以上工业总产值": (2600.0, "亿元", "示例"),
        "规模以上工业增加值": (620.0, "亿元", "示例"),
        "社会消费品零售总额": (944.14, "亿元", "示例"),
        "限额以上商品销售额": (9906.85, "亿元", "示例"),
        "固定资产投资总额": (578.33, "亿元", "示例"),
        "第二产业投资": (122.83, "亿元", "示例"),
        "第三产业投资": (455.46, "亿元", "示例"),
        "常住人口": (223.5, "万人", "示例"),
        "居民人均可支配收入": (82000.0, "元", "示例"),
        "规模以上服务业营业收入": (1500.0, "亿元", "示例"),
        "农业总产值": (12.5, "亿元", "示例"),
    },
    2025: {
        "地区生产总值": (2280.0, "亿元", "示例值，贴近2025公报量级"),
        "规模以上工业总产值": (2860.0, "亿元", "示例"),
        "规模以上工业增加值": (680.0, "亿元", "示例"),
        "社会消费品零售总额": (1030.0, "亿元", "示例"),
        "限额以上商品销售额": (10600.0, "亿元", "示例"),
        "固定资产投资总额": (615.0, "亿元", "示例"),
        "第二产业投资": (131.0, "亿元", "示例"),
        "第三产业投资": (484.0, "亿元", "示例"),
        "常住人口": (225.0, "万人", "示例"),
        "居民人均可支配收入": (87000.0, "元", "示例"),
        "规模以上服务业营业收入": (1680.0, "亿元", "示例"),
        "农业总产值": (13.1, "亿元", "示例"),
    },
    2026: {
        "地区生产总值": (2460.0, "亿元", "示例值，贴近2026公报量级"),
        "规模以上工业总产值": (3120.0, "亿元", "示例"),
        "规模以上工业增加值": (740.0, "亿元", "示例"),
        "社会消费品零售总额": (1120.0, "亿元", "示例"),
        "限额以上商品销售额": (11400.0, "亿元", "示例"),
        "固定资产投资总额": (655.0, "亿元", "示例"),
        "第二产业投资": (140.0, "亿元", "示例"),
        "第三产业投资": (515.0, "亿元", "示例"),
        "常住人口": (226.5, "万人", "示例"),
        "居民人均可支配收入": (92000.0, "元", "示例"),
        "规模以上服务业营业收入": (1870.0, "亿元", "示例"),
        "农业总产值": (13.8, "亿元", "示例"),
    },
}

# 指标 -> 专业分类
_INDICATOR_CATEGORY = {
    "地区生产总值": "综合",
    "规模以上工业总产值": "工业",
    "规模以上工业增加值": "工业",
    "社会消费品零售总额": "贸易",
    "限额以上商品销售额": "贸易",
    "固定资产投资总额": "投资",
    "第二产业投资": "投资",
    "第三产业投资": "投资",
    "常住人口": "人口",
    "居民人均可支配收入": "人口",
    "规模以上服务业营业收入": "服务业",
    "农业总产值": "农业",
}

# 各年度乡镇分维度规上工业总产值（示例）
_TOWN_VALUES: dict[int, dict[str, float]] = {
    2024: {"大场镇": 520.0, "杨行镇": 572.0, "顾村镇": 624.0,
           "月浦镇": 676.0, "罗店镇": 728.0},
    2025: {"大场镇": 560.0, "杨行镇": 615.0, "顾村镇": 670.0,
           "月浦镇": 725.0, "罗店镇": 780.0},
    2026: {"大场镇": 600.0, "杨行镇": 660.0, "顾村镇": 720.0,
           "月浦镇": 780.0, "罗店镇": 840.0},
}


def generate_national_sample_data(years: list[int] | None = None) -> int:
    """生成全国口径的多年度示例数据（2024-2026），维度统一为「全区」。

    线上 Vercel 冷启动 /tmp 空库时会调用，保证各年份均有数据。
    """
    years = years or [2024, 2025, 2026]
    rows: list[IndicatorRow] = []
    for y in years:
        for indicator, (value, unit, note) in _NATIONAL_YEARS.get(y, {}).items():
            rows.append(IndicatorRow(
                year=y,
                category=_INDICATOR_CATEGORY.get(indicator, "综合"),
                indicator=indicator,
                dimension="全区",
                value=value,
                unit=unit,
                note=note,
            ))
        # 乡镇分维度
        for town, tv in _TOWN_VALUES.get(y, {}).items():
            rows.append(IndicatorRow(
                year=y, category="工业", indicator="规上工业总产值",
                dimension=town, value=tv, unit="亿元", note="示例",
            ))
    return upsert_indicators(rows)
