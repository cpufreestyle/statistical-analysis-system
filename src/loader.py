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
    """生成全国口径的示例统计指标（量级贴近公开公报，仅作离线演示）。

    维度统一为「全国」；如需分省份/分国家数据，请用 `collect` 从网络采集。
    """
    rows: list[IndicatorRow] = [
        # 综合
        IndicatorRow(year=year, category="综合", indicator="地区生产总值", dimension="全国",
                     value=1349080.0, unit="亿元", note="示例值，贴近2024全国公报量级"),
        IndicatorRow(year=year - 1, category="综合", indicator="地区生产总值", dimension="全国",
                     value=1294272.0, unit="亿元", note="上年基数（示例）"),
        # 工业
        IndicatorRow(year=year, category="工业", indicator="规模以上工业总产值", dimension="全国",
                     value=1400000.0, unit="亿元", note="示例"),
        IndicatorRow(year=year, category="工业", indicator="规模以上工业增加值", dimension="全国",
                     value=400000.0, unit="亿元", note="示例"),
        # 贸易
        IndicatorRow(year=year, category="贸易", indicator="社会消费品零售总额", dimension="全国",
                     value=487000.0, unit="亿元", note="示例"),
        IndicatorRow(year=year, category="贸易", indicator="限额以上商品销售额", dimension="全国",
                     value=500000.0, unit="亿元", note="示例"),
        # 投资
        IndicatorRow(year=year, category="投资", indicator="固定资产投资总额", dimension="全国",
                     value=514000.0, unit="亿元", note="示例"),
        IndicatorRow(year=year, category="投资", indicator="第二产业投资", dimension="全国",
                     value=170000.0, unit="亿元", note="示例"),
        IndicatorRow(year=year, category="投资", indicator="第三产业投资", dimension="全国",
                     value=330000.0, unit="亿元", note="示例"),
        # 人口
        IndicatorRow(year=year, category="人口", indicator="常住人口", dimension="全国",
                     value=14.08, unit="亿人", note="示例"),
        IndicatorRow(year=year, category="人口", indicator="居民人均可支配收入", dimension="全国",
                     value=41300, unit="元", note="示例"),
    ]
    # 分省份工业产值示例（少量，演示分维度；采集可扩展到全部省份）
    provinces = ["广东省", "江苏省", "山东省", "浙江省", "河南省"]
    for i, p in enumerate(provinces):
        rows.append(IndicatorRow(
            year=year, category="工业", indicator="规模以上工业总产值", dimension=p,
            value=round(1400000.0 / len(provinces) * (1 + i * 0.15), 2),
            unit="亿元", note="示例"))
    return upsert_indicators(rows)
