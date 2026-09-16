"""数据导入：真实公开数据种子集 + 用户 CSV/Excel 导入。

数据口径（对外展示统一为**真实官方数据，每个数字可溯源**）：
- `data/ap_macro.csv`  世界银行 Open Data 的亚太地区与主要经济体宏观指标（2019-2024），
                       由 `scripts/fetch_wb_data.py` 抓取，note 字段带 WB 指标 code。
- `data/nbs_cn.csv`    中国国家统计局 / 海关总署 2024 年公开发布的主要指标，note 带出处。

这两份 CSV 会由 `scripts/embed_pages.py` 内嵌进 `src/seed_data.py`：
Vercel serverless 函数读不到仓库里的 data/ 目录，必须内嵌才能冷启动即有真实数据。
"""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import cast

from src.db import IndicatorRow, upsert_indicators

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 内嵌常量名 -> 仓库文件（本地开发优先用文件，改完数据无需重新内嵌即可生效）
_SEED_FILES: dict[str, str] = {
    "AP_MACRO_CSV": "ap_macro.csv",
    "NBS_CN_CSV": "nbs_cn.csv",
}


def _seed_text(const_name: str) -> str:
    """取种子 CSV 原文：优先仓库文件，其次内嵌常量（Vercel 环境）。"""
    path = DATA_DIR / _SEED_FILES[const_name]
    if path.exists():
        return path.read_text(encoding="utf-8")
    from src import seed_data

    return cast("str", getattr(seed_data, const_name))


def _parse_rows(text: str) -> list[IndicatorRow]:
    rows: list[IndicatorRow] = []
    for raw in csv.DictReader(io.StringIO(text.lstrip("\ufeff"))):
        try:
            rows.append(IndicatorRow(
                year=int(str(raw["year"]).strip()),
                category=str(raw["category"]).strip(),
                indicator=str(raw["indicator"]).strip(),
                dimension=str(raw["dimension"]).strip(),
                value=float(str(raw["value"]).strip()),
                unit=str(raw.get("unit") or "").strip(),
                note=str(raw.get("note") or "").strip(),
            ))
        except (KeyError, TypeError, ValueError):
            continue  # 跳过格式异常行，不阻断整批导入
    return rows


def load_seed_data(years: list[int] | None = None) -> int:
    """把真实公开数据种子集写入 indicators 表。`years` 非空时仅写入这些年份。"""
    rows: list[IndicatorRow] = []
    for const in _SEED_FILES:
        rows.extend(_parse_rows(_seed_text(const)))
    if years:
        keep = {int(y) for y in years}
        rows = [r for r in rows if r["year"] in keep]
    return upsert_indicators(rows) if rows else 0


def load_file(path: str) -> int:
    """导入用户 CSV/Excel，要求列为 year,category,indicator,dimension,value,unit,note。"""
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


# ---------------------------------------------------------------------------
# 兼容旧调用点（CLI init / Web 冷启动 / /api/reseed）：
# 过去是「生成合成示例数据」，现在统一改为「载入真实公开数据」。
# ---------------------------------------------------------------------------
def generate_sample_data(year: int | None = None) -> int:
    """载入真实公开数据种子集（`year` 仅保留签名兼容，不再使用）。"""
    return load_seed_data()


def generate_national_sample_data(years: list[int] | None = None) -> int:
    """载入真实公开数据种子集；`years` 非空时仅写入这些年份。"""
    return load_seed_data(years)
