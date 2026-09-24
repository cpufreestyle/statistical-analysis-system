"""Web 层路由测试（Flask 测试客户端，不起真实 socket）。

覆盖出海相关的关键路由：
- ``/`` 与 ``/app`` 的 ``__HTML_LANG__`` 占位符按 ``?lang=`` 替换（SEO / 分享卡片语言）；
- ``/api/export.csv`` 的 BOM（Excel 直接打开）、7 列定宽、Content-Disposition 文件名、
  以及 lang=en/zh 的本地化方向；
- ``/robots.txt`` ``/sitemap.xml`` ``/og-image.png`` 三大 SEO 资源存在且 Content-Type 正确；
- 冷启动自愈整条链路 ``_ensure_data``：旧快照被清表重播种、好数据不被误清、
  各失败分支留下可区分的告警（文件末尾一段）。
"""
from __future__ import annotations

import csv
import io
import logging

import pytest

EXPORT_FIELDS = ["year", "category", "indicator", "dimension", "value", "unit", "note"]


# ---------------------------------------------------------------------------
# __HTML_LANG__ 占位符
# ---------------------------------------------------------------------------
def test_index_html_lang_zh(client):
    resp = client.get("/?lang=zh")
    assert resp.status_code == 200
    assert b'lang="zh-CN"' in resp.data


def test_index_html_lang_en(client):
    resp = client.get("/?lang=en")
    assert resp.status_code == 200
    assert b'lang="en"' in resp.data


def test_app_html_lang_en(client):
    resp = client.get("/app?lang=en")
    assert resp.status_code == 200
    assert b'lang="en"' in resp.data


# ---------------------------------------------------------------------------
# /api/export.csv
# ---------------------------------------------------------------------------
def test_export_csv_default_has_bom_and_columns(seeded_client):
    resp = seeded_client.get("/api/export.csv")
    assert resp.status_code == 200
    # Flask 自动加单 charset，避免重复
    assert resp.content_type.startswith("text/csv")
    # BOM：Excel 直接打开中文不乱码
    assert resp.data.startswith(b"\xef\xbb\xbf")
    # 文件名：默认 year=all, dimension=all, lang=en
    assert 'filename="indicators_all_all_en.csv"' in resp.headers.get("Content-Disposition", "")
    # 7 列定宽表头
    text = resp.data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    assert header == EXPORT_FIELDS


def test_export_csv_china_en_localized(seeded_client):
    resp = seeded_client.get("/api/export.csv?year=2024&dimension=中国&lang=en")
    assert resp.status_code == 200
    assert 'filename="indicators_2024_china_en.csv"' in resp.headers.get("Content-Disposition", "")
    text = resp.data.decode("utf-8-sig")
    # 英文界面：维度被本地化为 China（而非中文规范键原样透传）
    assert "China" in text


def test_export_csv_zh_keeps_canonical(seeded_client):
    resp = seeded_client.get("/api/export.csv?dimension=中国&lang=zh")
    assert resp.status_code == 200
    assert 'filename="indicators_all_china_zh.csv"' in resp.headers.get("Content-Disposition", "")
    text = resp.data.decode("utf-8-sig")
    # 中文界面：维度保留规范键「中国」
    assert "中国" in text


def test_export_csv_rows_parse(seeded_client):
    resp = seeded_client.get("/api/export.csv?dimension=中国&lang=en")
    text = resp.data.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows, "应至少有一行数据"
    # 每行都有完整的 7 个字段
    for r in rows:
        assert set(EXPORT_FIELDS).issubset(r.keys())


# ---------------------------------------------------------------------------
# SEO 三件套
# ---------------------------------------------------------------------------
def test_robots_txt(client):
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/plain")
    assert "Sitemap:" in resp.text


def test_sitemap_xml(client):
    resp = client.get("/sitemap.xml")
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/xml")
    assert "<urlset" in resp.text


def test_og_image_png(client):
    resp = client.get("/og-image.png")
    assert resp.status_code == 200
    assert resp.content_type.startswith("image/png")
    # PNG 魔数
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# 生产加固：缓存策略 + 安全响应头 + 静态资源内容哈希版本号
# ---------------------------------------------------------------------------
def test_html_is_no_store(client):
    resp = client.get("/")
    assert "no-store" in resp.headers.get("Cache-Control", "")


def test_static_asset_long_cache(client):
    """每一份静态资源都必须带一年 immutable 长缓存（URL 里有内容哈希，换内容即换 URL）。"""
    from src import web

    for path in web._ASSET_FILES:
        resp = client.get(path)
        assert resp.status_code == 200, path
        cc = resp.headers.get("Cache-Control", "")
        assert "max-age=31536000" in cc and "immutable" in cc, path


def test_metric_unit_nowrap_in_css():
    """指标卡单位不得折行——'100 million USD' 折成两行会让数值与单位视觉脱节。"""
    import re
    from pathlib import Path

    css_path = Path(__file__).resolve().parent.parent / "public" / "style.css"
    css = css_path.read_text(encoding="utf-8")
    block = re.search(r"\.metric-unit\s*\{([^}]*)\}", css)
    assert block, ".metric-unit 规则缺失，请检查 public/style.css"
    assert "white-space" in block.group(1) and "nowrap" in block.group(1), (
        ".metric-unit 缺少 white-space:nowrap，单位可能折行"
    )


def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "default-src 'self'" in resp.headers.get("Content-Security-Policy", "")
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_asset_version_placeholder_replaced(client):
    """页面里的 ?v=__<资产名>_VER__ 必须全部被替换，任何残留都算故障。"""
    import re

    for path in ("/", "/app", "/docs", "/privacy"):
        data = client.get(path).data
        assert b"?v=" in data, path
        leftover = re.findall(rb"__[A-Z0-9_]+_VER__", data)
        assert not leftover, f"{path} 残留未替换的版本号占位符：{leftover}"


def test_asset_version_is_content_hash(client):
    """每个静态资源的 ?v= 必须等于**它自己**内容的哈希，且各资产互不相同。

    后半句是关键：早期实现把四份资源合起来算一个全局哈希，「只改落地页」也会把看板
    全部资产的 URL 换掉、害用户白下载一遍。改成按资产算后，改哪个才换哪个。
    """
    import hashlib
    import re

    from src import pages, web

    def ver_of(asset: str) -> str:
        name = web._ASSET_FILES[asset]
        return hashlib.sha256(getattr(pages, name).encode("utf-8")).hexdigest()[:12]

    html = client.get("/app").get_data(as_text=True)
    used = dict(re.findall(r"/([A-Za-z0-9._-]+)\?v=([0-9a-f]{6,})", html))
    for asset in web._ASSET_FILES:
        if asset in ("landing.css", "i18n-dict-landing.js"):
            continue  # 落地页专属资产，不该出现在看板里（另有一条测试专门盯这个）
        assert asset in used, f"/app 未引用 {asset}"
        assert used[asset] == ver_of(asset), asset
    assert len(set(used.values())) == len(used), f"版本号退化成了全局同一个：{used}"


def test_landing_only_assets_are_not_loaded_by_the_dashboard(client):
    """落地页专属资产不能被看板引用——否则按资产缓存的收益直接作废。"""
    app = client.get("/app").get_data(as_text=True)
    assert "/landing.css?v=" not in app, "看板引用了落地页专属的 landing.css"
    assert "/i18n-dict-landing.js?v=" not in app, "看板引用了落地页专属的字典子集"


def test_dashboard_only_assets_are_not_loaded_by_the_landing_page(client):
    index = client.get("/").get_data(as_text=True)
    for asset in ("/style.css?v=", "/app.js?v=", "/i18n-dict.js?v="):
        assert asset not in index, f"落地页引用了看板专属资产 {asset}"


def _token_names(block: str) -> set[str]:
    """取出一段 CSS 里定义过的自定义属性名（value 不重要，只比集合）。"""
    import re

    return set(re.findall(r"(--[a-z0-9-]+)\s*:", block))


def test_theme_css_is_the_single_source_of_tokens(client):
    """主题令牌唯一来源：深浅两个入口都在 theme.css，页面样式不得再自建色阶。

    历史上 public/style.css 与 public/index.html 各有一套灰阶/蓝色，取值还不一样
    （#F9FAFB/#E5E7EB vs #F8FAFC/#E2E8F0），同一站点两个页面灰度不一致。
    """
    theme = client.get("/theme.css").get_data(as_text=True)
    assert ':root[data-theme="dark"]' in theme, "theme.css 缺少手动深色入口"
    assert "@media (prefers-color-scheme: dark)" in theme, "theme.css 缺少跟随系统的深色入口"
    # 每个灰阶/底色令牌 = 浅色 1 次 + 两个深色入口各 1 次
    assert theme.count("--gray-500:") == 3, "灰阶令牌未在三个入口各定义一次"
    assert theme.count("--surface:") == 3, "底色令牌未在三个入口各定义一次"
    # 蓝色不随主题反相，只应定义一次
    assert theme.count("--blue-600:") == 1, "主色不应被深色入口重复定义"
    # 语义令牌：落地页深色带与半透明导航靠它们随主题翻转
    assert "--band-bg:" in theme and "--nav-bg:" in theme, "缺少语义令牌"
    # 两个深色入口必须定义完全相同的令牌集合，否则「手动切深色」与「跟随系统」会走到两套外观
    manual = theme.split(':root[data-theme="dark"] {')[1].split("}")[0]
    system = theme.split(':root:not([data-theme="light"]) {')[1].split("}")[0]
    assert _token_names(manual) == _token_names(system), (
        "两个深色入口的令牌集合不一致：",
        sorted(_token_names(manual) ^ _token_names(system)))

    for page in ("/", "/app"):
        html = client.get(page).get_data(as_text=True)
        assert "--gray-500:" not in html, f"{page} 仍在自建灰阶令牌（应只保留在 theme.css）"
        assert "--blue-600:" not in html, f"{page} 仍在自建蓝色令牌"
        head = html.split("<style>")[0]
        assert "prefers-color-scheme: dark) {" not in head, f"{page} 在 <style> 前又挂了深色覆写"


def test_theme_css_loads_before_page_styles(client):
    """令牌必须先立、组件后取：theme.css 必须排在页面自己的样式之前。"""
    app = client.get("/app").get_data(as_text=True)
    assert app.index("/theme.css?v=") < app.index("/style.css?v="), "看板里 theme.css 排在 style.css 之后"
    index = client.get("/").get_data(as_text=True)
    assert index.index("/theme.css?v=") < index.index("/landing.css?v="), "落地页里 theme.css 排在 landing.css 之后"


def test_landing_page_shares_the_workbench_theme_contract(client):
    """落地页必须与看板同一套主题约定：同一个 storage 键、防闪白脚本、三态按钮。

    此前落地页只跟随系统偏好、读不到用户手动选的主题——在看板切到深色后回到首页，
    首页仍是一片白。
    """
    html = client.get("/").get_data(as_text=True)
    assert "qu_theme_v1" in html, "落地页没有沿用 qu_theme_v1 这个主题存储键"
    assert 'id="themeToggle"' in html, "落地页缺少主题切换按钮"
    assert 'onclick="cycleTheme()"' in html, "落地页主题按钮未接三态循环"
    assert "document.documentElement.setAttribute('data-theme'" in html, "落地页缺少防闪白预置脚本"
    # 防闪白脚本必须出现在样式表之前，否则深色偏好用户仍会闪一下白
    assert html.index("qu_theme_v1") < html.index("/theme.css?v="), "防闪白脚本排在 theme.css 之后"


def test_landing_theme_dark_band_uses_tokens(client):
    """落地页两块「深色带」必须走语义令牌，不能再写死灰阶——否则深色下反相成白底白字。

    落地页样式已从 index.html 的内联 <style> 抽成 /landing.css，故直接取那份响应。
    """
    import re

    css = client.get("/landing.css").get_data(as_text=True)
    for sel in (".tech-stack", ".footer"):
        found = re.search(re.escape(sel) + r"\s*\{([^}]*)\}", css)
        assert found, f"{sel} 规则缺失"
        assert "var(--band-bg)" in found.group(1), f"{sel} 未改用 --band-bg 语义令牌"
    nav = re.search(r"\.nav\s*\{([^}]*)\}", css)
    assert nav and "var(--nav-bg)" in nav.group(1), ".nav 未改用 --nav-bg 语义令牌"




# ---------------------------------------------------------------------------
# 管理端点鉴权（清库 / 抓数 / 读环境变量）
# ---------------------------------------------------------------------------
def test_admin_endpoint_allows_local(monkeypatch, client):
    """本地（非 Vercel、未配 token）放行管理端点。"""
    from src import web

    monkeypatch.setattr(web, "_IS_SERVERLESS", False)
    monkeypatch.setattr(web, "_ADMIN_TOKEN", "")
    assert client.get("/api/db").status_code == 200


def test_admin_disabled_in_production(monkeypatch, client):
    """部署到 Vercel 且未配 token 时，管理端点一律 403（无副作用）。"""
    from src import web

    monkeypatch.setattr(web, "_IS_SERVERLESS", True)
    monkeypatch.setattr(web, "_ADMIN_TOKEN", "")
    assert client.get("/api/db").status_code == 403
    assert client.post("/api/reseed").status_code == 403
    assert client.get("/api/kv-status").status_code == 403
    assert client.post("/api/collect").status_code == 403


def test_admin_token_required_when_configured(monkeypatch, client):
    from src import web

    monkeypatch.setattr(web, "_IS_SERVERLESS", True)
    monkeypatch.setattr(web, "_ADMIN_TOKEN", "s3cret")
    assert client.get("/api/db").status_code == 403
    assert client.get("/api/db", headers={"X-Admin-Token": "s3cret"}).status_code == 200


# ---------------------------------------------------------------------------
# /api/stats —— 公开的数据规模统计（与受保护的管理端点严格区分）
# ---------------------------------------------------------------------------
def test_public_stats_endpoint(seeded_client):
    resp = seeded_client.get("/api/stats")
    assert resp.status_code == 200
    d = resp.get_json()
    assert {"indicator_rows", "knowledge_rows", "dimension_count",
            "year_count", "years", "dimensions"} <= set(d)
    assert d["indicator_rows"] > 0
    assert d["dimension_count"] == len(d["dimensions"])


def test_public_stats_hides_environment_details(seeded_client):
    """公开端点不得泄露库路径 / 引擎等环境信息——那些属于受保护的管理端点。"""
    import json

    d = seeded_client.get("/api/stats").get_json()
    blob = json.dumps(d).lower()
    assert "sqlite" not in blob
    assert "/tmp" not in blob
    assert "url" not in d and "path" not in d and "engine" not in d


def test_public_stats_stays_open_in_production(monkeypatch, seeded_client):
    """回归防线：落地页 / 侧栏依赖的统计数字在线上必须拿得到。

    此前它们读的是受保护的 ``/api/db``，部署到 Vercel 后一律 403，
    页面上一整块统计会静默显示「—」而不报错。
    """
    from src import web

    monkeypatch.setattr(web, "_IS_SERVERLESS", True)
    monkeypatch.setattr(web, "_ADMIN_TOKEN", "")
    assert seeded_client.get("/api/stats").status_code == 200
    assert seeded_client.get("/api/db").status_code == 403


# ---------------------------------------------------------------------------
# /api/insights —— 可复算的数据洞察（同比榜单 + 名次变动 + 覆盖规模）
# ---------------------------------------------------------------------------
def test_insights_endpoint_shape(seeded_client):
    resp = seeded_client.get("/api/insights?year=2024&dimension=亚太")
    assert resp.status_code == 200
    d = resp.get_json()
    assert d["year"] == 2024 and d["prev_year"] == 2023
    assert d["dimension_key"] == "亚太"
    assert {"movers", "rank_shifts", "rank_indicator", "rank_indicator_key",
            "coverage"} <= set(d)
    assert d["movers"], "有可比数据时榜单不应为空"
    for m in d["movers"]:
        assert {"indicator", "indicator_key", "indicator_slug", "unit",
                "value", "prev_value", "change_pct"} <= set(m)
    # 榜单按变化幅度降序
    amps = [abs(m["change_pct"]) for m in d["movers"]]
    assert amps == sorted(amps, reverse=True)


def test_insights_numbers_are_recomputable(seeded_client):
    """洞察数字必须能被 /api/indicators 复算——「绝不编数」的机器防线。"""
    d = seeded_client.get("/api/insights?year=2024&dimension=亚太").get_json()
    top = d["movers"][0]
    key = top["indicator_key"]
    cur_rows = seeded_client.get(
        f"/api/indicators?year=2024&indicator={key}&dimension=亚太").get_json()
    prev_rows = seeded_client.get(
        f"/api/indicators?year=2023&indicator={key}&dimension=亚太").get_json()
    cur, prev = float(cur_rows[0]["value"]), float(prev_rows[0]["value"])
    assert abs(cur - float(top["value"])) < 1e-9
    assert top["change_pct"] == round((cur - prev) / abs(prev) * 100, 1)


def test_insights_is_localized(seeded_client):
    zh = seeded_client.get("/api/insights?lang=zh&year=2024&dimension=中国").get_json()
    en = seeded_client.get("/api/insights?lang=en&year=2024&dimension=china").get_json()
    assert zh["dimension"] == "中国"
    assert en["dimension"] == "China"
    # 规范键跨语言稳定，英文消费方才能把两种语言的同一条洞察对上
    assert en["dimension_key"] == "中国"
    assert en["movers"][0]["indicator_slug"]
    assert en["movers"][0]["indicator"] != en["movers"][0]["indicator_key"]


def test_insights_rank_delta_direction(seeded_client):
    """delta = 上年名次 − 今年名次：正数代表名次上升。"""
    d = seeded_client.get("/api/insights?year=2024").get_json()
    shifts = d["rank_shifts"]
    assert shifts
    for s in shifts:
        assert s["delta"] == s["rank_prev"] - s["rank_now"]
        assert 1 <= s["rank_now"] <= 20
    amps = [abs(s["delta"]) for s in shifts]
    assert amps == sorted(amps, reverse=True)


# ---------------------------------------------------------------------------
# /docs —— API 参考页（服务端渲染、双语、与路由表保持一致）
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
def test_docs_page_renders_without_placeholders(client):
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/html")
    assert b"__ASSET_VER__" not in resp.data
    assert b"__HTML_LANG__" not in resp.data


def test_docs_page_is_bilingual_by_lang(client):
    zh = client.get("/docs?lang=zh").get_data(as_text=True)
    en = client.get("/docs?lang=en").get_data(as_text=True)
    assert 'lang="zh-CN"' in zh and "接口一览" in zh
    assert 'lang="en"' in en and "Endpoints" in en
    # 两种语言互不串味
    assert "Endpoints" not in zh
    assert "接口一览" not in en


def test_docs_language_toggle_link_points_to_other_lang(client):
    assert 'href="/docs?lang=zh"' in client.get("/docs?lang=en").get_data(as_text=True)
    assert 'href="/docs?lang=en"' in client.get("/docs?lang=zh").get_data(as_text=True)


def test_docs_covers_exactly_the_real_routes(client):
    """文档与实现的一致性契约：路由表里的每条路径都必须出现在 /docs，反之亦然。

    新增路由却忘了登记文档时，这条测试会失败——避免文档静默过期。
    """
    import re

    from src import api_docs, web

    text = " ".join(str(e["path"]) for e in api_docs.ENDPOINTS)
    documented = set(re.findall(r"/[A-Za-z0-9_./\-]+", text))
    documented.add("/")  # 站点根路径不带尾部字符，正则匹配不到
    rules = {r.rule for r in web.app.url_map.iter_rules()
             if not r.rule.startswith("/static")}

    missing = sorted(rules - documented)
    stale = sorted(documented - rules)
    assert not missing, f"路由存在但未登记到 /docs：{missing}"
    assert not stale, f"/docs 里登记了不存在的路由：{stale}"


def test_docs_declares_admin_endpoints_as_protected(client):
    """管理端点必须在文档里标出需要令牌，否则第三方会误以为可匿名调用。"""
    en = client.get("/docs?lang=en").get_data(as_text=True)
    admin_block = en[en.index("Admin endpoints"):]
    assert admin_block.count("Admin token") >= 4


def test_docs_english_page_has_no_chinese_comments(client):
    """英文 /docs 的代码块注释必须也是英文。

    只审注释行（``#`` / ``//``）：示例载荷里的中文是数据本身
    （如 ``["国民经济", "GDP", "中国"]``、``"category": "通用"``），
    调用方必须原样使用，不在翻译范围内；注释则是写给人看的说明，必须跟随语言。
    """
    import html as html_mod
    import re

    en = client.get("/docs?lang=en").get_data(as_text=True)
    blocks = re.findall(r'<pre class="doc-pre">(.*?)</pre>', en, re.S)
    assert blocks, "未找到任何 doc-pre 代码块"

    leaked = []
    for index, block in enumerate(blocks):
        text = html_mod.unescape(block).replace("&quot;", '"')
        for line in text.splitlines():
            stripped = line.strip()
            is_comment = stripped.startswith("#") or "//" in stripped
            if is_comment and re.search(r"[\u4e00-\u9fff]", stripped):
                leaked.append((index, stripped[:40]))
    assert not leaked, f"英文页代码块里出现中文注释：{leaked}"


# ---------------------------------------------------------------------------
# 自定义错误页（品牌一致，且接口路径仍回 JSON）
# ---------------------------------------------------------------------------
def test_404_page_is_branded_html(client):
    resp = client.get("/no-such-page-here")
    assert resp.status_code == 404
    body = resp.get_data(as_text=True)
    assert "404" in body
    assert "/docs" in body and "/app" in body
    assert "__HTML_LANG__" not in body


def test_404_for_api_path_returns_json(client):
    resp = client.get("/api/no-such-endpoint")
    assert resp.status_code == 404
    assert resp.is_json
    assert resp.get_json()["ok"] is False


def test_405_page_for_wrong_method(client):
    resp = client.post("/api/stats")  # 只允许 GET
    assert resp.status_code == 405
    assert resp.is_json
    assert resp.get_json()["ok"] is False


def test_error_page_language_follows_lang(client):
    zh = client.get("/nope?lang=zh").get_data(as_text=True)
    en = client.get("/nope?lang=en").get_data(as_text=True)
    assert "页面不存在" in zh
    assert "Page not found" in en


# ---------------------------------------------------------------------------
# hreflang / sitemap 一致性
# ---------------------------------------------------------------------------
def test_hreflang_alternates_present(client):
    for path in ("/", "/app"):
        html = client.get(path).get_data(as_text=True)
        for lang in ('hreflang="en"', 'hreflang="zh-CN"', 'hreflang="x-default"'):
            assert lang in html, f"{path} 缺少 {lang}"


def test_hreflang_per_page_urls(client):
    """alternate 必须指向自身页面（/ 与 /app 不能互相串）。"""
    app_html = client.get("/app").get_data(as_text=True)
    assert 'hreflang="en" href="https://qu-stat-system.vercel.app/app?lang=en"' in app_html
    doc_html = client.get("/docs").get_data(as_text=True)
    assert 'hreflang="zh-CN" href="https://qu-stat-system.vercel.app/docs?lang=zh"' in doc_html


def test_sitemap_lists_docs(client):
    assert "/docs" in client.get("/sitemap.xml").get_data(as_text=True)


# ---------------------------------------------------------------------------
# /privacy —— 隐私与数据声明页（对外分发的合规入口）
# ---------------------------------------------------------------------------
def test_privacy_page_renders_without_placeholders(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/html")
    assert b"__ASSET_VER__" not in resp.data
    assert b"__HTML_LANG__" not in resp.data


def test_privacy_page_is_bilingual(client):
    zh = client.get("/privacy?lang=zh").get_data(as_text=True)
    en = client.get("/privacy?lang=en").get_data(as_text=True)
    assert 'lang="zh-CN"' in zh and "我们不设账号" in zh
    assert 'lang="en"' in en and "No accounts, no login" in en
    assert "No accounts, no login" not in zh


def test_privacy_page_answers_the_faq(client):
    """对外三问必须都有答案：收集什么 / 数据从哪来 / AI 是否外发。"""
    en = client.get("/privacy?lang=en").get_data(as_text=True)
    assert "qu_lang_v2" in en          # 浏览器里存了什么
    assert "CC BY 4.0" in en           # 数据许可
    assert "off by default" in en      # 云端 AI 默认关闭
    assert "/tmp" in en                # 托管与存储


def test_privacy_page_reachable_from_docs_and_landing(client):
    """入口不能只存在于路由表里：落地页页脚与 /docs 导航都要能看到。"""
    assert "/privacy" in client.get("/").get_data(as_text=True)
    assert "/privacy" in client.get("/docs?lang=en").get_data(as_text=True)
    assert "/privacy" in client.get("/no-such-page").get_data(as_text=True)


def test_sitemap_lists_privacy(client):
    assert "/privacy" in client.get("/sitemap.xml").get_data(as_text=True)


# ---------------------------------------------------------------------------
# 区级旧快照判别（线上冷启动防线：旧数据混入会让英文首页变空看板并漏出「全区」）
# ---------------------------------------------------------------------------
def test_legacy_snapshot_detected_without_apac_aggregate():
    from src.web import _is_legacy_dataset

    assert _is_legacy_dataset({"全区", "中国", "全国"})
    assert _is_legacy_dataset(set())


def test_real_apac_dataset_is_not_legacy():
    from src.web import _is_legacy_dataset

    assert not _is_legacy_dataset({"亚太", "亚太(发展中)", "中国"})


# ---------------------------------------------------------------------------
# 冷启动自愈整条链路（_ensure_data：KV 恢复 → 特征判别 → 清表 → 重播种 → 清 KV）
# 上面的谓词测试只证明「认得出旧快照」，这里证明认出来之后确实恢复了。
# ---------------------------------------------------------------------------
# 区级快照的标志性维度：真实亚太种子集里一律不存在，才能证明「清表」真的生效
LEGACY_DIMS = ("全区", "高新区")


@pytest.fixture()
def clean_indicators():
    """把 indicators 表清成已知空态，起始数据由各测试自行铺设。"""
    from src.db import INDICATORS, engine, init_db

    init_db()
    with engine.begin() as conn:
        conn.execute(INDICATORS.delete())
    yield
    with engine.begin() as conn:
        conn.execute(INDICATORS.delete())


@pytest.fixture()
def fake_kv(monkeypatch):
    """KV 层换成可记录 / 可注入的假实现（本地无 Redis，测试一律不触网）。

    ``_ensure_data`` 与两处同步钩子都是在函数内 ``from src.kv_store import ...``，
    因此按模块属性打补丁即可在调用时生效。
    """
    import src.kv_store as kv

    trace: dict[str, list] = {"events": [], "deleted_keys": []}

    def _delete(key: str) -> bool:
        trace["events"].append("kv_delete")
        trace["deleted_keys"].append(key)
        return True

    monkeypatch.setattr(kv, "kv_available", lambda: True)
    monkeypatch.setattr(kv, "kv_set_json", lambda key, value: True)
    monkeypatch.setattr(kv, "kv_delete", _delete)
    return trace


def _store_legacy_snapshot() -> int:
    """直接在库里铺一份区级旧快照（缺「亚太」聚合维度）。"""
    from src.db import INDICATORS, engine, init_db

    init_db()
    rows = [
        {"year": 2024, "category": "综合", "indicator": "地区生产总值",
         "dimension": dim, "value": 1.0, "unit": "亿元", "note": ""}
        for dim in LEGACY_DIMS
    ]
    with engine.begin() as conn:
        conn.execute(INDICATORS.delete())
        conn.execute(INDICATORS.insert(), rows)
    return len(rows)


def _dimensions() -> set[str]:
    from src.db import query_indicators

    return {str(r["dimension"]) for r in query_indicators()}


def test_coldstart_purges_legacy_kv_snapshot_in_order(
        clean_indicators, fake_kv, monkeypatch, caplog):
    """旧快照 → 清表 → 重播种 → 清 KV，三个副作用按序发生，且 web 层全程无告警。"""
    import src.kv_sync as kv_sync
    import src.loader as loader
    from src.web import _ensure_data

    real_load = loader.load_seed_data

    def restore_legacy() -> bool:
        fake_kv["events"].append("restore")
        assert _store_legacy_snapshot() == len(LEGACY_DIMS)
        return True

    def spy_load(years=None):
        from src.db import query_indicators

        # 重播种前表必须已被清空，否则旧维度会以「覆盖不删」的方式残留
        assert query_indicators() == [], "重播种前未清表"
        fake_kv["events"].append("reseed")
        return real_load(years)

    monkeypatch.setattr(kv_sync, "restore_from_kv", restore_legacy)
    monkeypatch.setattr(loader, "load_seed_data", spy_load)

    with caplog.at_level(logging.WARNING, logger="src.web"):
        _ensure_data()

    # 只算 src.web 自己的告警：别处（例如 src.db 的慢查询告警）的噪音不该记在这条
    # 契约的账上——本测试要钉住的是「启动流程不降级」，不是「全世界都别打日志」。
    web_warnings = [r.getMessage() for r in caplog.records
                    if r.levelno >= logging.WARNING and r.name == "src.web"]
    assert web_warnings == []
    assert fake_kv["events"] == ["restore", "reseed", "kv_delete"]
    assert fake_kv["deleted_keys"] == ["qu_stat_ap:indicators"]
    dims = _dimensions()
    assert "亚太" in dims
    assert not set(LEGACY_DIMS) & dims, "区级旧维度未被清掉"


def test_coldstart_keeps_good_kv_snapshot_without_purging(clean_indicators, fake_kv, monkeypatch):
    """KV 里是真实亚太数据时不得清库——否则每次冷启动都白灌一遍。"""
    import src.kv_sync as kv_sync
    from src.loader import load_seed_data
    from src.web import _ensure_data

    def restore_good() -> bool:
        fake_kv["events"].append("restore")
        load_seed_data()
        return True

    monkeypatch.setattr(kv_sync, "restore_from_kv", restore_good)

    _ensure_data()

    assert fake_kv["events"] == ["restore"]
    assert fake_kv["deleted_keys"] == []
    assert "亚太" in _dimensions()


def test_kv_purge_failure_is_logged_apart_from_restore_failure(
        clean_indicators, fake_kv, monkeypatch, caplog):
    """清 KV 失败要与「恢复失败」可区分（不同日志），且不影响已完成的恢复结果。"""
    import src.kv_store as kv
    import src.kv_sync as kv_sync
    from src.web import _ensure_data

    def boom(key: str) -> bool:
        raise RuntimeError("upstash unreachable")

    def restore_legacy() -> bool:
        _store_legacy_snapshot()
        return True

    fake_kv["deleted_keys"] = []          # 本测试不记录成功路径
    monkeypatch.setattr(kv, "kv_delete", boom)
    monkeypatch.setattr(kv_sync, "restore_from_kv", restore_legacy)

    with caplog.at_level(logging.WARNING, logger="src.web"):
        _ensure_data()

    messages = [r.getMessage() for r in caplog.records]
    assert any("kv purge after reseed failed" in m for m in messages), messages
    assert not any("kv restore skipped" in m for m in messages), messages
    dims = _dimensions()
    assert "亚太" in dims and not set(LEGACY_DIMS) & dims


def test_kv_restore_failure_falls_back_to_offline_seed(
        clean_indicators, fake_kv, monkeypatch, caplog):
    """KV 恢复抛错不得阻断看板启动，并留下可归因的告警 + 完成离线播种。"""
    import src.kv_sync as kv_sync
    from src.web import _ensure_data

    def boom() -> bool:
        raise RuntimeError("kv read timeout")

    monkeypatch.setattr(kv_sync, "restore_from_kv", boom)

    with caplog.at_level(logging.WARNING, logger="src.web"):
        _ensure_data()

    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("kv restore skipped") for m in messages), messages
    assert "亚太" in _dimensions()
