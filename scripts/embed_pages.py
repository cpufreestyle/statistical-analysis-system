"""把静态资源内嵌为 Python 模块（Vercel serverless 读不到仓库里的 public/ 与 data/ 文件）。

用法: python scripts/embed_pages.py

生成:
  src/pages.py      —— 前端页面资源（PAGE_INDEX / PAGE_STYLE / ... 见 FILES）
  src/seed_data.py  —— 种子数据集（真实公开数据 CSV 原文，见 DATA_FILES）

改完 public/ 下任何文件、或 scripts/fetch_wb_data.py 重新抓了数据，都要重跑本脚本，
并重启服务（pages.py / seed_data.py 在启动时 import）。
"""
from __future__ import annotations

import base64
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
    "THEME_CSS": "theme.css",
    "APP_JS": "app.js",
    "I18N_JS": "i18n.js",
}

# SEO 静态资源（robots / sitemap / 分享卡片），同样内嵌进 pages.py 以保证
# Vercel serverless 环境也能直接以 /robots.txt /sitemap.xml /og-image.png 提供。
SEO_FILES = {
    "ROBOTS_TXT": "robots.txt",
    "SITEMAP_XML": "sitemap.xml",
    # 分享卡片是二进制 PNG，无法按 UTF-8 文本内嵌 → 以 base64 存储（键名带 _B64 提示）。
    "OG_IMAGE_PNG_B64": "og-image.png",
}

#: 需要按二进制读取并按 base64 内嵌的文件（其余一律按 UTF-8 文本内嵌）
BINARY_FILES = {"og-image.png"}

# 真实公开数据种子集（由 scripts/fetch_wb_data.py / 官方公报整理而来）
DATA_FILES = {
    "AP_MACRO_CSV": "ap_macro.csv",
    "NBS_CN_CSV": "nbs_cn.csv",
    # 数据标识符的多语言标签包：服务端本地化的唯一事实来源，见 src/labels.py
    "LABELS_CSV": "labels.csv",
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
        if fname in BINARY_FILES:
            # 二进制（如 og-image.png）：以 base64 字符串内嵌，运行期再 decode 回 bytes。
            b64 = base64.b64encode(path.read_bytes()).decode("ascii")
            lines.append(f"{name} = {b64!r}")
        else:
            # utf-8-sig：带 BOM 的 UTF-8 会被剥掉 BOM，避免内嵌常量里带上 \ufeff
            # （BOM 会污染 CSV 首行，让标签包静默失效——见 src/labels.py 的说明）。
            content = path.read_text(encoding="utf-8-sig").lstrip("\ufeff")
            lines.append(f"{name} = {content!r}")
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK -> {out} ({out.stat().st_size} bytes)")


def main() -> None:
    # 页面资源与 SEO 资源合并写入同一个 pages.py —— _write_assets 是整文件覆写，
    # 分两次调用会让后一次冲掉前一次。
    _write_assets(OUT, PUBLIC, {**FILES, **SEO_FILES},
                  "由 scripts/embed_pages.py 自动生成 —— 前端页面与 SEO 资源内嵌（Vercel 兼容）。")
    _write_assets(OUT_DATA, DATA, DATA_FILES,
                  "由 scripts/embed_pages.py 自动生成 —— 真实公开数据种子集（Vercel 兼容）。")


if __name__ == "__main__":
    main()
