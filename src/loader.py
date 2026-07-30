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
