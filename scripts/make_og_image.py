"""生成社交分享卡片 og-image.png（1200×630）——纯 Pillow 绘制，零外部依赖。

用法: .venv/Scripts/python.exe scripts/make_og_image.py

背景：Facebook / X / LinkedIn 对 og:image 用 SVG 支持不稳定，故改为 PNG。
设计沿用 public/og-image.svg（深蓝渐变 + AP 徽标 + 标题 + 两行副标题），
字体用系统 Arial（无需下载 Web 字体，与本项目「无外部 CDN」定位一致）。
改完本脚本后重跑，并把产物 public/og-image.png 提交即可。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "og-image.png"

W, H = 1200, 630
TOP = (0x0F, 0x17, 0x2A)   # 渐变起点（深蓝黑）
BOT = (0x1B, 0x56, 0xC4)   # 渐变终点（品牌蓝）
BRAND = (0x2B, 0x6B, 0xDB)
SUB = (0x94, 0xA3, 0xB8)

# Windows 自带字体；非 Windows 环境退回 DejaVu（Pillow 自带）
_candidates_bold = ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf"]
_candidates_reg = ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"]


def _font(size: int, bold: bool) -> ImageFont.FreeTypeFont:
    for path in (_candidates_bold if bold else _candidates_reg):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)


def main() -> None:
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)

    # 纵向线性渐变
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)],
               fill=tuple(int(TOP[i] + (BOT[i] - TOP[i]) * t) for i in range(3)))

    # 徽标：圆角蓝底 + 居中白字 AP
    d.rounded_rectangle([64, 64, 64 + 96, 64 + 96], radius=20, fill=BRAND)
    f_logo = _font(46, bold=True)
    d.text((112, 112), "AP", font=f_logo, fill="white", anchor="mm")

    # 标题（两行）
    f_title = _font(58, bold=True)
    d.text((64, 288), "Asia-Pacific Statistical", font=f_title, fill="white", anchor="ls")
    d.text((64, 358), "Analysis System", font=f_title, fill="white", anchor="ls")

    # 副标题（两行）
    f_sub = _font(30, bold=False)
    d.text((64, 430),
           "Official public data · World Bank Open Data · China NBS · China Customs",
           font=f_sub, fill=SUB, anchor="ls")
    d.text((64, 476),
           "AI-grounded interpretation · Charts · Export & share",
           font=f_sub, fill=SUB, anchor="ls")

    img.save(OUT, "PNG", optimize=True)
    print(f"OK -> {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
