"""应用内「隐私与数据声明」页 ``/privacy``（服务端渲染，中英双语）。

为什么需要它
------------
对外开源分发后，访问者会反复问三件事：这个站点收集什么？数据从哪来？
AI 解读会把我的问题发到哪里？本页把答案固定下来，避免每个 issue 重新解释一遍。

做法与 :mod:`src.api_docs` 一致：服务端按请求语言渲染、**零 JavaScript**，
复用 ``/style.css`` 的设计令牌（深色模式自动生效）。
"""
from __future__ import annotations

from src.api_docs import SHARED_CSS

_EXTRA_CSS = """
.priv-meta { font-size: 12px; color: var(--gray-400); margin: 0 0 24px; }
.priv-p { margin: 0 0 10px; font-size: 13.5px; color: var(--gray-600); line-height: 1.78; max-width: 74ch; }
.docs-conv p.priv-p { margin: 0 0 10px; }
"""

#: 中文章节（标题, 正文）。``code`` 与 **加粗** 会被渲染成对应标签。
_ZH = {
    "doc.title": "隐私与数据声明 · 亚太统计分析系统",
    "doc.h1": "隐私与数据声明",
    "doc.lead": ("本站点只使用公开统计数据的开放看板。下面说明它收集什么、不收集什么，"
                 "以及开启云端 AI 解读时会发生什么。"),
    "updated": "最近更新：2026-09-18",
    "nav.home": "返回落地页",
    "nav.app": "进入数据看板",
    "nav.docs": "API 参考",
    "skip": "跳到主内容",
    "sections": [
        ("我们不设账号",
         "本站没有注册、登录与个人资料。你在查询框输入的问题只在**当次请求**中用于生成回答，"
         "服务端不建立用户档案，也不做跨会话的画像。"),
        ("浏览器里存了什么",
         "只有一个键 ``qu_lang_v2``（localStorage），用来记住你选择的语言；删掉它即恢复默认英文。"
         "**没有 Cookie，没有第三方统计或广告脚本。**"),
        ("数据从哪来",
         "全部为公开数据：世界银行 Open Data（CC BY 4.0）、中国国家统计局与海关总署的公开发布物。"
         "仓库与数据库中**不含任何内部、涉密或个人数据**；每一行的来源都写在 ``note`` 字段里，"
         "看板上可直接看到。"),
        ("AI 解读会发出什么",
         "云端解读**默认关闭**。开启后，你的问题与本地检索到的统计结果会一起发送给所选 provider"
         "（``infinisynapse``，或任意 OpenAI 兼容端点）；提示词明确要求「只依据给定数字、不得编造」。"
         "密钥只从环境变量读取，从不写进仓库。未开启时，全部处理都在本地完成。"),
        ("托管与存储",
         "线上部署在 Vercel（无状态函数）。SQLite 落在 ``/tmp``，冷启动时重建；可选的 KV 快照"
         "**只保存指标数据本身**，用于加速恢复。系统没有用户表，也不长期留存你上传的文件。"),
        ("第三方依赖",
         "页面不加载任何外部 CDN 资源：字体使用系统字体栈，图表是内联 SVG（无图表库），"
         "样式与脚本同源提供；所有响应带收敛到 ``'self'`` 的 CSP。"),
        ("你的选择",
         "清除站点数据即可移除语言偏好；若不希望问题离开本机，不要勾选「AI 云端解读」即可"
         "（本地统计照常工作）。对数据口径有疑问请提交 issue，安全问题请看 ``SECURITY.md``。"),
        ("本页的变更",
         "本页随代码一同更新，变更记录见 ``CHANGELOG.md``。"),
    ],
    "footer": "亚太统计分析系统 · 仅使用官方公开数据",
}

_EN = {
    "doc.title": "Privacy & data statement · Asia-Pacific Statistical Analysis System",
    "doc.h1": "Privacy & data statement",
    "doc.lead": ("An open dashboard built on public statistics. This page explains what it "
                 "collects, what it does not, and what happens when you turn on the optional "
                 "cloud AI interpretation."),
    "updated": "Last updated: 2026-09-18",
    "nav.home": "Back to landing page",
    "nav.app": "Open the dashboard",
    "nav.docs": "API reference",
    "skip": "Skip to content",
    "sections": [
        ("No accounts, no login",
         "There is no sign-up, login or profile. The question you type is used only to produce "
         "**that one answer**; the server keeps no user profile and builds no cross-session "
         "history."),
        ("What is stored in your browser",
         "A single key, ``qu_lang_v2``, in ``localStorage``, which remembers your language choice — "
         "delete it and the default (English) returns. **No cookies, no third-party analytics or "
         "ad scripts.**"),
        ("Where the data comes from",
         "Everything is public: World Bank Open Data (CC BY 4.0) plus public releases from China "
         "NBS and China Customs. Neither the repository nor the database holds **any internal, "
         "restricted or personal data**; every row carries its source in the ``note`` field, "
         "visible on the dashboard."),
        ("What the AI layer sends out",
         "Cloud interpretation is **off by default**. When enabled, your question and the locally "
         "retrieved statistics are sent to the selected provider (``infinisynapse``, or any "
         "OpenAI-compatible endpoint); the prompt requires it to use only the given figures and "
         "never invent any. Keys are read from environment variables only and are never "
         "committed. With it off, everything stays local."),
        ("Hosting and storage",
         "The hosted build runs on Vercel (stateless functions). SQLite lives in ``/tmp`` and is "
         "rebuilt on cold start; the optional KV snapshot stores **only the indicator rows**, to "
         "speed up restores. There is no user table and no long-term retention of files you "
         "upload."),
        ("Third-party dependencies",
         "No external CDN resources are loaded: fonts use the system stack, charts are inline SVG "
         "(no chart library), styles and scripts are same-origin, and every response carries a "
         "CSP limited to ``'self'``."),
        ("Your choices",
         "Clear site data to remove the language preference. If you would rather a question never "
         "left your machine, leave “AI cloud interpretation” unchecked — local statistics keep "
         "working. Questions about data caliber belong in an issue; security reports go through "
         "``SECURITY.md``."),
        ("Changes to this page",
         "This page ships with the code; see ``CHANGELOG.md`` for the history."),
    ],
    "footer": "Asia-Pacific Statistical Analysis System · official public data only",
}


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _md(text: str) -> str:
    """极简行内标记：``code`` → ``<code>``、**bold** → ``<b>``（先转义，避免注入）。"""
    out = _esc(text)
    parts = out.split("``")
    if len(parts) > 1:
        out = "".join(p if i % 2 == 0 else f"<code>{p}</code>"
                      for i, p in enumerate(parts))
    while "**" in out:
        out = out.replace("**", "<b>", 1)
        if "**" in out:
            out = out.replace("**", "</b>", 1)
        else:
            break
    return out


def render(lang: str, base_url: str) -> str:
    """渲染整页 ``/privacy`` HTML（占位符由 :func:`src.web._render_page` 替换）。"""
    s = _EN if lang == "en" else _ZH
    other = "zh" if lang == "en" else "en"
    other_label = "中文" if lang == "en" else "EN"

    body = "".join(
        f'<h3 class="docs-h3">{_md(head)}</h3><p class="priv-p">{_md(text)}</p>'
        for head, text in s["sections"]  # type: ignore[union-attr]
    )

    return f"""<!DOCTYPE html>
<html lang="__HTML_LANG__">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(s["doc.title"])}</title>
<meta name="description" content="{_esc(s["doc.lead"])}">
<meta name="robots" content="index, follow">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="canonical" href="{_esc(base_url)}/privacy">
<link rel="alternate" hreflang="en" href="{_esc(base_url)}/privacy?lang=en">
<link rel="alternate" hreflang="zh-CN" href="{_esc(base_url)}/privacy?lang=zh">
<link rel="alternate" hreflang="x-default" href="{_esc(base_url)}/privacy">
<meta property="og:type" content="website">
<meta property="og:title" content="{_esc(s["doc.title"])}">
<meta property="og:description" content="{_esc(s["doc.lead"])}">
<meta property="og:image" content="{_esc(base_url)}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/style.css?v=__STYLE_CSS_VER__">
<style>{SHARED_CSS}{_EXTRA_CSS}</style>
</head>
<body>
<a class="skip-link" href="#main">{_esc(s["skip"])}</a>
<nav class="docs-nav">
  <div class="docs-brand"><div class="docs-logo">AP</div>
    <span>{_esc("亚太统计分析系统" if lang != "en" else "Asia-Pacific Statistics")}</span></div>
  <div class="docs-nav-links">
    <a href="/">{_esc(s["nav.home"])}</a>
    <a href="/app">{_esc(s["nav.app"])}</a>
    <a href="/docs">{_esc(s["nav.docs"])}</a>
    <a id="privacyLangToggle" class="lang-toggle" href="/privacy?lang={other}">{_esc(other_label)}</a>
  </div>
</nav>
<main class="docs-wrap" id="main">
  <div class="docs-hero">
    <h1>{_esc(s["doc.h1"])}</h1>
    <p>{_esc(s["doc.lead"])}</p>
    <p class="priv-meta">{_esc(s["updated"])}</p>
  </div>
  <h2 class="docs-h2" id="statement">{_esc(s["doc.h1"])}</h2>
  <div class="docs-conv">
    {body}
  </div>
  <div class="docs-foot">
    <span>{_esc(s["footer"])}</span>
    <span>{_esc("本页随代码更新 · CHANGELOG.md" if lang != "en"
                else "Shipped with the code · CHANGELOG.md")}</span>
  </div>
</main>
</body>
</html>"""
