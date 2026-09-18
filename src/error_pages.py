"""品牌一致的自定义错误页（404 / 405 / 500）。

Flask 默认错误页是英文白底纯文本，与站点观感割裂；且本项目对外默认英文，
中文用户也需要可读的说明。故统一由本模块渲染：复用 ``/style.css`` 的设计令牌
（含深色模式），页内零 JS，语言按请求 ``?lang=`` / ``Accept-Language``。
"""
from __future__ import annotations

_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--surface); color: var(--gray-700);
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.err-card {
  max-width: 520px; width: 100%; text-align: center;
  border: 1px solid var(--gray-150); border-radius: var(--radius-xl);
  background: var(--surface-2); padding: 40px 32px;
}
.err-logo {
  width: 46px; height: 46px; margin: 0 auto 16px; border-radius: 12px;
  background: linear-gradient(135deg, var(--blue-500), var(--blue-700));
  color: #fff; font-size: 16px; font-weight: 700; letter-spacing: .02em;
  display: flex; align-items: center; justify-content: center;
}
.err-code { font-size: 44px; font-weight: 700; color: var(--gray-900); letter-spacing: -.02em; line-height: 1; margin: 0 0 6px; }
.err-title { font-size: 16px; font-weight: 600; color: var(--gray-800); margin: 0 0 8px; }
.err-desc { font-size: 13px; color: var(--gray-500); margin: 0 0 22px; line-height: 1.7; }
.err-actions { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
.err-btn {
  display: inline-block; padding: 9px 18px; border-radius: var(--radius-md);
  font-size: 13px; text-decoration: none; border: 1px solid var(--gray-200);
  color: var(--gray-600); background: var(--surface);
}
.err-btn.primary { background: var(--blue-600); border-color: var(--blue-600); color: #fff; }
.err-links { margin-top: 22px; font-size: 12px; color: var(--gray-400); }
.err-links a { color: var(--blue-600); text-decoration: none; }
"""

#: 每种状态码的双语文案：(标题, 说明) —— zh, en
_TEXT: dict[int, dict[str, tuple[str, str]]] = {
    404: {
        "zh": ("页面不存在",
               "这个地址没有对应的内容。可能是链接已过期，或者地址拼写有误。"
               "你可以回到落地页，或直接查阅 API 参考。"),
        "en": ("Page not found",
               "There is nothing at this address. The link may be outdated, or the URL may "
               "be mistyped. Head back to the landing page, or browse the API reference."),
    },
    405: {
        "zh": ("请求方法不被允许",
               "该地址存在，但不支持当前 HTTP 方法（例如对只读接口发起了 POST）。"),
        "en": ("Method not allowed",
               "The address exists, but this HTTP method is not supported for it (for "
               "example a POST against a read-only endpoint)."),
    },
    500: {
        "zh": ("服务暂时出错",
               "处理请求时发生了内部错误，请稍后重试。若持续出现，请查看服务端日志。"),
        "en": ("Something went wrong",
               "An internal error occurred while handling the request. Please try again in a "
               "moment; if it persists, check the server logs."),
    },
}


def render(code: int, lang: str, base_url: str) -> str:
    """渲染错误页。``lang`` 为 ``en`` / ``zh``；未知状态码退回 500 的文案。"""
    entry = _TEXT.get(code) or _TEXT[500]
    title, desc = entry["en"] if lang == "en" else entry["zh"]
    zh = lang != "en"
    other = "zh" if lang == "en" else "en"
    other_label = "中文" if lang == "en" else "EN"
    doc_label = "API 参考" if zh else "API reference"
    home_label = "返回落地页" if zh else "Back to landing page"
    app_label = "进入数据看板" if zh else "Open the dashboard"
    skip = "跳到主内容" if zh else "Skip to content"
    return f"""<!DOCTYPE html>
<html lang="__HTML_LANG__">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{code} · {title}</title>
<meta name="robots" content="noindex">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="canonical" href="{base_url}/">
<link rel="stylesheet" href="/style.css?v=__ASSET_VER__">
<style>{_CSS}</style>
</head>
<body>
<a class="skip-link" href="#main">{skip}</a>
<main class="err-card" id="main">
  <div class="err-logo">AP</div>
  <p class="err-code">{code}</p>
  <p class="err-title">{title}</p>
  <p class="err-desc">{desc}</p>
  <div class="err-actions">
    <a class="err-btn primary" href="/">{home_label}</a>
    <a class="err-btn" href="/app">{app_label}</a>
  </div>
  <p class="err-links">
    <a href="/docs">{doc_label}</a> ·
    <a href="/docs?lang={other}">{other_label}</a>
  </p>
</main>
</body>
</html>"""
