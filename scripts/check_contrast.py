# -*- coding: utf-8 -*-
"""从前端样式表里抽取真实的「前景色 / 背景色」配对，按 WCAG 2.1 计算对比度。

为什么值得抽检而不是靠肉眼：本项目有三套主题入口（浅色 / 手动深色 / 跟随系统），
同一个类在三套下的前景背景配对完全不同，而「#8B97AA 这种中灰在深色底上够不够亮」
这类问题肉眼极难判断、跨主题还可能一边达标一边不达标。WCAG 对比度是纯数学，
写一次就能在每次改动后自动回归。

配对不是手写清单，而是**从样式表里扫出来的**：凡同一条规则里同时出现
``color: var(--x)`` 与 ``background(-color): var(--y)``，就构成一对候选。
这样新增组件时自动纳入检查，不需要维护第二份清单。

阈值按 WCAG 2.1 AA：
  · 普通文本（< 18.66px，或 < 24px 的非粗体）  4.5:1
  · 大文本（>= 18.66px 粗体，或 >= 24px）      3:1
  · 非文本 UI 组件边界 / 图标                  3:1
同一条规则没写 font-size 时按普通文本（从严）处理。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC = BASE_DIR / "public"
THEME_CSS = PUBLIC / "theme.css"
SHEETS = [PUBLIC / "style.css", PUBLIC / "landing.css"]

#: 三个主题入口的选择器（浅色 + 两个深色）。顺序即报告顺序。
THEME_BLOCKS = [
    ("浅色", ":root {"),
    ("深色(手动)", ':root[data-theme="dark"] {'),
    ("深色(跟随系统)", ':root:not([data-theme="light"]) {'),
]

LARGE_TEXT_PX = 24.0
LARGE_BOLD_PX = 18.66


def _block(source: str, opener: str) -> str:
    """取出 opener 之后到配对右花括号之间的内容（支持嵌套，媒体查询里那一块要用）。"""
    start = source.find(opener)
    if start < 0:
        return ""
    i = source.find("{", start)
    if i < 0:
        return ""
    depth = 0
    for j in range(i, len(source)):
        ch = source[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[i + 1:j]
    return ""


def parse_tokens(text: str) -> dict[str, str]:
    """把一段 CSS 里的 ``--name: value;`` 收成字典（忽略注释）。"""
    tokens: dict[str, str] = {}
    for name, value in re.findall(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;]+);", text):
        tokens[name] = value.strip()
    return tokens


def resolve(var: str, tokens: dict[str, str], depth: int = 0) -> str | None:
    """把 ``var(--x)`` / ``var(--x, fallback)`` 解成字面值；解析不了返回 None。"""
    if depth > 5:
        return None
    m = re.fullmatch(r"var\(\s*(--[A-Za-z0-9_-]+)\s*(?:,\s*([^)]+))?\)", var.strip())
    if not m:
        return var.strip()
    name, fallback = m.group(1), m.group(2)
    if name in tokens:
        return resolve(tokens[name], tokens, depth + 1)
    if fallback is not None:
        return resolve(fallback, tokens, depth + 1)
    return None


def parse_color(value: str) -> tuple[float, float, float, float] | None:
    """解析 #RGB / #RRGGBB / rgb() / rgba()，返回 0-255 的 RGB 与 0-1 的 alpha。"""
    text = value.strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3})", text)
    if m:
        h = m.group(1)
        return tuple(int(c * 2, 16) for c in h) + (1.0,)  # type: ignore[return-value]
    m = re.fullmatch(r"#([0-9a-f]{6})", text)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"rgba?\(([^)]+)\)", text)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        if len(parts) < 3:
            return None
        try:
            rgb = tuple(float(re.sub(r"[a-z%]+$", "", p)) for p in parts[:3])
            alpha = float(parts[3]) if len(parts) > 3 else 1.0
        except ValueError:
            return None
        if len(rgb) != 3:
            return None
        return (rgb[0], rgb[1], rgb[2], alpha)  # type: ignore[return-value]
    return None


def _lin(channel: float) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    l1, l2 = luminance(fg), luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def composite(fg, bg):
    """半透明前景按 alpha 与背景合成（alpha<1 时）。"""
    r, g, b, a = fg
    return (r * a + bg[0] * (1 - a), g * a + bg[1] * (1 - a), b * a + bg[2] * (1 - a))


def collect_pairs() -> list[tuple[str, str, str, int, int]]:
    """扫样式表，返回 (前景 var, 背景 var, 出处, 字号 px, 字重) 五元组。"""
    pairs: list[tuple[str, str, str, int, int]] = []
    seen: set[tuple[str, str, str]] = set()
    for sheet in SHEETS:
        if not sheet.exists():
            continue
        text = re.sub(r"/\*.*?\*/", "", sheet.read_text(encoding="utf-8"), flags=re.S)
        for rule in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
            selector, body = rule[0].strip(), rule[1]
            fg = re.search(r"(?<!-)\bcolor\s*:\s*([^;]+);", body)
            bg = re.search(r"background(?:-color)?\s*:\s*([^;]+);", body)
            if not fg or not bg:
                continue
            fg_var, bg_var = fg.group(1).strip(), bg.group(1).strip()
            if not (fg_var.startswith("var(") and bg_var.startswith("var(")):
                continue
            if "currentColor" in fg_var or "transparent" in bg_var:
                continue
            size = re.search(r"font-size\s*:\s*([\d.]+)px", body)
            weight = re.search(r"font-weight\s*:\s*(\d+)", body)
            key = (fg_var, bg_var, selector)
            if key in seen:
                continue
            seen.add(key)
            pairs.append((fg_var, bg_var, selector,
                          int(float(size.group(1))) if size else 0,
                          int(weight.group(1)) if weight else 400))
    return pairs


def main() -> int:
    theme = THEME_CSS.read_text(encoding="utf-8")
    entries = [(label, parse_tokens(_block(theme, opener))) for label, opener in THEME_BLOCKS]
    missing_block = [label for label, tokens in entries if not tokens]
    if missing_block:
        print(f"[ERR ] theme.css 找不到主题入口：{missing_block}")
        return 2

    pairs = collect_pairs()
    if not pairs:
        print("[ERR ] 没有扫到任何前景/背景配对，脚本本身可能坏了")
        return 2

    failures = 0
    checked = 0
    print("WCAG 2.1 AA 对比度抽检（前景/背景配对从样式表自动提取）\n")
    for label, tokens in entries:
        rows = []
        for fg_var, bg_var, selector, size, weight in pairs:
            fg = resolve(fg_var, tokens)
            bg = resolve(bg_var, tokens)
            if fg is None or bg is None:
                continue
            fg_rgb, bg_rgb = parse_color(fg), parse_color(bg)
            if not fg_rgb or not bg_rgb:
                continue
            if fg_rgb[3] < 1:
                fg_rgb = (*composite(fg_rgb, bg_rgb[:3]), 1.0)  # type: ignore[assignment]
            if bg_rgb[3] < 1:
                continue
            large = size >= LARGE_TEXT_PX or (size >= LARGE_BOLD_PX and weight >= 700)
            need = 3.0 if large else 4.5
            ratio = contrast(fg_rgb[:3], bg_rgb[:3])  # type: ignore[index]
            checked += 1
            if ratio < need:
                failures += 1
            rows.append((ratio, need, fg_var, bg_var, selector, size))
        rows.sort()
        for ratio, need, fg_var, bg_var, selector, size in rows:
            mark = "ok  " if ratio >= need else "FAIL"
            print(f"[{mark}] {label:12s} {ratio:5.2f}:1 (需 {need}) "
                  f"{fg_var} on {bg_var}  {selector} {size}px")
        print()
    print(f"共检查 {checked} 个配对，{failures} 个不达标")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
