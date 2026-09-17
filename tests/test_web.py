"""Web 层路由测试（Flask 测试客户端，不起真实 socket）。

覆盖出海相关的关键路由：
- ``/`` 与 ``/app`` 的 ``__HTML_LANG__`` 占位符按 ``?lang=`` 替换（SEO / 分享卡片语言）；
- ``/api/export.csv`` 的 BOM（Excel 直接打开）、7 列定宽、Content-Disposition 文件名、
  以及 lang=en/zh 的本地化方向；
- ``/robots.txt`` ``/sitemap.xml`` ``/og-image.svg`` 三大 SEO 资源存在且 Content-Type 正确。
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


def test_og_image_svg(client):
    resp = client.get("/og-image.svg")
    assert resp.status_code == 200
    assert resp.content_type.startswith("image/svg+xml")
    assert "<svg" in resp.text
