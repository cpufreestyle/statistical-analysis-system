"""将 public/ 下的前端静态文件嵌入为 src/pages.py（Vercel serverless 函数无法访问 public/ 目录）。

用法: python scripts/embed_pages.py
生成: src/pages.py（含 PAGE_INDEX / PAGE_APP / STYLE_CSS / APP_JS 四个字符串常量）
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
OUT = ROOT / "src" / "pages.py"

FILES = {
    "PAGE_INDEX": "index.html",
    "PAGE_APP": "app.html",
    "STYLE_CSS": "style.css",
    "APP_JS": "app.js",
}


def main() -> None:
    lines: list[str] = [
        '"""由 scripts/embed_pages.py 自动生成 —— 前端页面资源内嵌（Vercel 兼容）。"""',
        "from __future__ import annotations",
        "",
    ]
    for name, fname in FILES.items():
        path = PUBLIC / fname
        if not path.exists():
            raise SystemExit(f"缺失文件: {path}")
        content = path.read_text(encoding="utf-8")
        lines.append(f"{name} = {content!r}")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
