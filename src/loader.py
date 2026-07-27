"""数据导入：CSV/Excel 导入 + 示例数据生成。

参考 agent_infini 的 `db` / `task file` 思路：把外部数据载入统一指标宽表。
"""
from __future__ import annotations

from typing import cast

from src.db import IndicatorRow, upsert_indicators


def load_file(path: str) -> int:
    """导入 CSV/Excel，要求列为 year,category,indicator,dimension,value,unit,note。"""
    import pandas as pd

    if path.endswith(".csv"):
        df: pd.DataFrame = pd.read_csv(path)
    else:
        # pandas-stubs 的 read_excel 签名含 Unknown 参数，触发 reportUnknownMemberType；
        # 此为库本身类型缺陷，针对性忽略。
        df = pd.read_excel(path)  # type: ignore[reportUnknownMemberType]
    rows: list[IndicatorRow] = cast("list[IndicatorRow]", df.to_dict("records"))
    return upsert_indicators(rows)


def generate_sample_data(year: int = 2024) -> int:
    """生成宝山区示例统计指标（贴近公开公报量级）。"""
    rows: list[IndicatorRow] = [
        # 综合
        IndicatorRow(year=year, category="综合", indicator="地区生产总值", dimension="全区",
                     value=2110.57, unit="亿元", note="示例值，贴近2024公报量级"),
        IndicatorRow(year=year - 1, category="综合", indicator="地区生产总值", dimension="全区",
                     value=2010.0, unit="亿元", note="上年基数"),
        # 工业
        IndicatorRow(year=year, category="工业", indicator="规模以上工业总产值", dimension="全区",
                     value=2600.0, unit="亿元", note="示例"),
        IndicatorRow(year=year, category="工业", indicator="规模以上工业增加值", dimension="全区",
                     value=620.0, unit="亿元", note="示例"),
        # 贸易
        IndicatorRow(year=year, category="贸易", indicator="社会消费品零售总额", dimension="全区",
                     value=944.14, unit="亿元", note="示例"),
        IndicatorRow(year=year, category="贸易", indicator="限额以上商品销售额", dimension="全区",
                     value=9906.85, unit="亿元", note="示例"),
        # 投资
        IndicatorRow(year=year, category="投资", indicator="固定资产投资总额", dimension="全区",
                     value=578.33, unit="亿元", note="示例"),
        IndicatorRow(year=year, category="投资", indicator="第二产业投资", dimension="全区",
                     value=122.83, unit="亿元", note="示例"),
        IndicatorRow(year=year, category="投资", indicator="第三产业投资", dimension="全区",
                     value=455.46, unit="亿元", note="示例"),
        # 人口
        IndicatorRow(year=year, category="人口", indicator="常住人口", dimension="全区",
                     value=223.5, unit="万人", note="示例"),
        IndicatorRow(year=year, category="人口", indicator="居民人均可支配收入", dimension="全区",
                     value=82000, unit="元", note="示例"),
    ]
    # 分街镇工业产值示例
    towns = ["大场镇", "杨行镇", "顾村镇", "月浦镇", "罗店镇"]
    for i, t in enumerate(towns):
        rows.append(IndicatorRow(
            year=year, category="工业", indicator="规上工业总产值", dimension=t,
            value=round(2600.0 / len(towns) * (1 + i * 0.1), 2),
            unit="亿元", note="示例"))
    return upsert_indicators(rows)
