"""Web 层路由测试（Flask 测试客户端，不起真实 socket）。

覆盖出海相关的关键路由：
- ``/`` 与 ``/app`` 的 ``__HTML_LANG__`` 占位符按 ``?lang=`` 替换（SEO / 分享卡片语言）；
- ``/api/export.csv`` 的 BOM（Excel 直接打开）、7 列定宽、Content-Disposition 文件名、
  以及 lang=en/zh 的本地化方向；
- ``/robots.txt`` ``/sitemap.xml`` ``/og-image.png`` 三大 SEO 资源存在且 Content-Type 正确。
"""
from __future__ import annotations

import csv
import io

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
    for path in ("/style.css", "/app.js", "/i18n.js"):
        cc = client.get(path).headers.get("Cache-Control", "")
        assert "max-age=31536000" in cc and "immutable" in cc, path


def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert "default-src 'self'" in resp.headers.get("Content-Security-Policy", "")
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_asset_version_placeholder_replaced(client):
    """页面里的 ?v=__ASSET_VER__ 必须被替换，且不再残留占位符。"""
    for path in ("/", "/app"):
        data = client.get(path).data
        assert b"__ASSET_VER__" not in data, path
        assert b"?v=" in data, path


def test_asset_version_is_content_hash(client):
    """页面上出现的版本号应等于内容哈希 _ASSET_VER。"""
    import re

    from src import web

    html = client.get("/app").get_data(as_text=True)
    versions = set(re.findall(r"\?v=([0-9a-f]{6,})", html))
    assert versions == {web._ASSET_VER}


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
# /docs —— API 参考页（服务端渲染、双语、与路由表保持一致）
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
