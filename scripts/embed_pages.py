"""把静态资源内嵌为 Python 模块（Vercel serverless 读不到仓库里的 public/ 与 data/ 文件）。

用法: python scripts/embed_pages.py

生成:
  src/pages.py      —— 前端页面资源（PAGE_INDEX / PAGE_STYLE / ... 见 FILES）
  src/seed_data.py  —— 种子数据集（真实公开数据 CSV 原文，见 DATA_FILES）

改完 public/ 下任何文件、或 scripts/fetch_wb_data.py 重新抓了数据，都要重跑本脚本，
并重启服务（pages.py / seed_data.py 在启动时 import）。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
DATA = ROOT / "data"
OUT = ROOT / "src" / "pages.py"
OUT_DATA = ROOT / "src" / "seed_data.py"

FILES = {
    "PAGE_INDEX": "index.html",
    "PAGE_APP": "app.html",
    "STYLE_CSS": "style.css",
    "APP_JS": "app.js",
    "I18N_JS": "i18n.js",
}

# 真实公开数据种子集（由 scripts/fetch_wb_data.py / 官方公报整理而来）
DATA_FILES = {
    "AP_MACRO_CSV": "ap_macro.csv",
    "NBS_CN_CSV": "nbs_cn.csv",
}


def _write_assets(out: Path, base: Path, mapping: dict[str, str], doc: str) -> None:
    lines: list[str] = [
        f'"""{doc}"""',
        "from __future__ import annotations",
        "",
    ]
    for name, fname in mapping.items():
        path = base / fname
        if not path.exists():
            raise SystemExit(f"缺失文件: {path}")
        content = path.read_text(encoding="utf-8")
        lines.append(f"{name} = {content!r}")
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK -> {out} ({out.stat().st_size} bytes)")


def main() -> None:
    _write_assets(OUT, PUBLIC, FILES,
                  "由 scripts/embed_pages.py 自动生成 —— 前端页面资源内嵌（Vercel 兼容）。")
    _write_assets(OUT_DATA, DATA, DATA_FILES,
                  "由 scripts/embed_pages.py 自动生成 —— 真实公开数据种子集（Vercel 兼容）。")


if __name__ == "__main__":
    main()
