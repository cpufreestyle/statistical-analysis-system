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
import logging
import math
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from src.db import IndicatorRow, upsert_indicators

logger = logging.getLogger(__name__)

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


def _opt_str(raw: Mapping[str, object], key: str) -> str:
    """取可选字符串列；空值与 pandas 的 NaN 一律归一成空串。

    pandas 读缺失单元格得到的是 ``float('nan')``，直接 ``str()`` 会写成字面量
    "nan"——那是把缺失数据存成了字符串，比存空串更难排查。
    """
    value = raw.get(key)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def _coerce_row(raw: Mapping[str, object]) -> IndicatorRow | None:
    """把一行原始映射转成 IndicatorRow；不可用时返回 None。

    种子 CSV 与用户 CSV/Excel **共用**这一套规则（原先各写一份，容易漂移）。
    判定「不可用」的条件：必需列缺失、年份/数值不可解析、数值非有限。
    """
    try:
        year = int(str(raw["year"]).strip())
        value = float(str(raw["value"]).strip())
        if not math.isfinite(value):
            return None
        return IndicatorRow(
            year=year,
            category=str(raw["category"]).strip(),
            indicator=str(raw["indicator"]).strip(),
            dimension=str(raw["dimension"]).strip(),
            value=value,
            unit=_opt_str(raw, "unit"),
            note=_opt_str(raw, "note"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _parse_rows(text: str) -> list[IndicatorRow]:
    rows: list[IndicatorRow] = []
    for raw in csv.DictReader(io.StringIO(text.lstrip("\ufeff"))):
        row = _coerce_row(raw)
        if row is not None:
            rows.append(row)
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
    """导入用户 CSV/Excel，要求列为 year,category,indicator,dimension,value,unit,note。

    逐行校验，规则与种子数据完全一致（``_coerce_row``）：必需列缺失、
    年份/数值不可解析、数值非有限的行会被跳过并在日志里报数。
    **整份文件都不可用时抛 ValueError** 而不是返回 0——用户传错文件时必须
    立刻看到失败，而不是收到一句「已导入 0 条」还以为成功了。
    """
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

    records = cast("list[dict[str, object]]", df.to_dict("records"))
    rows: list[IndicatorRow] = []
    for record in records:
        row = _coerce_row(record)
        if row is not None:
            rows.append(row)

    if not rows:
        raise ValueError(
            f"{path}：{len(records)} 行全部不可用。需要 year / category / indicator / "
            "dimension / value 五列（unit 与 note 可选），且年份与数值必须可解析。"
        )
    skipped = len(records) - len(rows)
    if skipped:
        logger.warning("%s：跳过 %d / %d 行（必需列缺失、数值不可解析或非有限）",
                       Path(path).name, skipped, len(records))
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
