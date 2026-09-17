"""embed_pages.py 单遍合并回归测试。

历史坑：``main()`` 曾两次调用 ``_write_assets``（先页面、后 SEO），而该函数是
**整文件覆写**——后一次把前一次冲掉，导致 pages.py 只剩 SEO 资源或只剩页面资源。
修复后改为一次合并写入。本测试固化这一不变量：

- ``_write_assets`` 一次写入 ``{**FILES, **SEO_FILES}`` 时，产物同时含页面资源与
  SEO 资源（任一方都不缺）；
- 实装 ``src.pages`` 含全部页面 + SEO 常量；
- ``src.seed_data.LABELS_CSV`` 非空且含 ``kind`` 表头（标签包兜底路径依赖它）；
- 所有待嵌入的源文件都存在（否则构建会 SystemExit）。
"""
from __future__ import annotations

from pathlib import Path

import scripts.embed_pages as embed


def test_write_assets_single_pass_keeps_both_pages_and_seo(tmp_path):
    out = tmp_path / "pages_test.py"
    embed._write_assets(out, embed.PUBLIC,
                        {**embed.FILES, **embed.SEO_FILES},
                        "test doc")
    content = out.read_text(encoding="utf-8")
    # 页面资源与 SEO 资源必须共存（防止分两次调用互相冲掉）
    assert "PAGE_INDEX = " in content
    assert "PAGE_APP = " in content
    assert "ROBOTS_TXT = " in content
    assert "SITEMAP_XML = " in content
    assert "OG_IMAGE_SVG = " in content


def test_all_source_files_exist():
    for name, fname in {**embed.FILES, **embed.SEO_FILES}.items():
        assert (embed.PUBLIC / fname).exists(), f"缺失页面资源: {name} -> {fname}"
    for name, fname in embed.DATA_FILES.items():
        assert (embed.DATA / fname).exists(), f"缺失数据资源: {name} -> {fname}"


def test_pages_module_has_all_assets():
    import src.pages as pages

    for name in ("PAGE_INDEX", "PAGE_APP", "STYLE_CSS", "APP_JS", "I18N_JS",
                 "ROBOTS_TXT", "SITEMAP_XML", "OG_IMAGE_SVG"):
        assert hasattr(pages, name), f"src.pages 缺少 {name}"
    # SEO 内容真实可用
    assert "Sitemap:" in pages.ROBOTS_TXT
    assert "<urlset" in pages.SITEMAP_XML
    assert "<svg" in pages.OG_IMAGE_SVG


def test_seed_data_labels_csv_valid():
    import src.seed_data as seed

    assert hasattr(seed, "LABELS_CSV")
    csv_text = str(seed.LABELS_CSV)
    assert "kind" in csv_text, "LABELS_CSV 应含表头行 kind,key,slug,en"
    assert len(csv_text.strip()) > 0
