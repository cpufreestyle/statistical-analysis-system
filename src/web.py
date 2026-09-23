"""Web 看板（Flask，纯离线、无外部 CDN 依赖）。

启动：python -m src.cli web   访问 http://127.0.0.1:5000
页面数据全部来自本地 SQLite / 统计函数；图表用内联 SVG 绘制。
数据源为公开开放数据（世界银行 Open Data + 国家统计局 / 海关总署公开发布）。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os as _os
import gzip as _gzip

# 本地看板跑在 127.0.0.1，必须排除出系统 HTTP 代理（如 127.0.0.1:7897），
# 否则代理会拦截本地请求导致预览/接口连接被拒。
_os.environ.setdefault("no_proxy", "127.0.0.1,localhost")
_os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
if "127.0.0.1" not in _os.environ.get("no_proxy", ""):
    _os.environ["no_proxy"] = (_os.environ.get("no_proxy", "") + ",127.0.0.1,localhost").strip(",")
if "127.0.0.1" not in _os.environ.get("NO_PROXY", ""):
    _os.environ["NO_PROXY"] = (_os.environ.get("NO_PROXY", "") + ",127.0.0.1,localhost").strip(",")

from functools import wraps

from flask import Flask, request, jsonify, Response

from src import report
from src.db import query_indicators, db_info, init_db
from src import knowledge as kb
from src import collect as collector
from src import labels
from src import api_docs
from src import error_pages
from src import privacy_page
from src.stats import indicators as ind
from src.stats import query as nlq
from src.stats import custom as cust
from src import pages

app = Flask(__name__)

DEFAULT_DIMENSION = "亚太"
DEFAULT_YEAR = 2024

#: 对外公开站点基址（canonical / hreflang / 文档示例用）。自定义域名时用环境变量覆盖，
#: 避免把 vercel.app 写死在索引与分享元数据里。
_BASE_URL = _os.environ.get("QU_STAT_BASE_URL", "https://qu-stat-system.vercel.app").rstrip("/")

#: 静态资源版本号 = 三份前端资源的内容哈希（前 12 位）。改了任一资源，哈希自动变，
#: 页面里的 ``?v=`` 随之变，浏览器必然拉新文件——这样才能给静态资源上「一年 immutable」
#: 的长缓存，同时 HTML / 接口保持 no-store（见 :func:`_apply_headers` 的说明）。
_ASSET_VER = hashlib.sha256(
    (pages.STYLE_CSS + pages.APP_JS + pages.I18N_JS).encode("utf-8")
).hexdigest()[:12]

#: 静态资源缓存（URL 已带内容哈希版本号，可安全长缓存）。
_STATIC_CACHE = "public, max-age=31536000, immutable"

#: C3 · 触发 gzip 的最小响应体（更小则压缩不划算）。
_GZIP_MIN_BYTES = 500
#: C3 · 可压缩的 MIME 前缀（文本类）。
_GZIP_MIMES = ("text/", "application/json", "application/javascript",
               "application/xml", "image/svg+xml")


def _client_accepts_gzip() -> bool:
    """客户端是否声明支持 gzip（Accept-Encoding）。"""
    return "gzip" in (request.headers.get("Accept-Encoding") or "").lower()

#: 安全响应头。本项目无外部 CDN 依赖（字体已走系统字体栈），故 CSP 收敛到 'self'。
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self'"
    ),
}

#: 管理端点令牌：配置后，请求头 ``X-Admin-Token`` 或查询参数 ``?token=`` 必须匹配。
#: 未配置时——本地开发放行；一旦部署到 Vercel（``VERCEL`` 环境变量存在）则一律 403。
_ADMIN_TOKEN = _os.environ.get("QU_STAT_ADMIN_TOKEN", "").strip()
_IS_SERVERLESS = bool(_os.environ.get("VERCEL"))


def _render_page(html: str) -> str:
    """替换页面模板占位符：语言（``__HTML_LANG__``）+ 静态资源版本号（``__ASSET_VER__``）。"""
    return (html.replace("__HTML_LANG__", _html_lang())
                .replace("__ASSET_VER__", _ASSET_VER))


def _admin_denied():
    """管理端点鉴权：返回 ``(响应, 403)`` 表示拒绝，返回 ``None`` 表示放行。"""
    if _ADMIN_TOKEN:
        supplied = request.headers.get("X-Admin-Token") or request.args.get("token") or ""
        if hmac.compare_digest(supplied, _ADMIN_TOKEN):
            return None
        return jsonify({"ok": False, "error": "admin token required"}), 403
    if _IS_SERVERLESS:
        return jsonify({"ok": False,
                        "error": "admin endpoints are disabled in production"}), 403
    return None


def admin_required(fn):
    """装饰器：给「清库 / 抓数 / 读环境变量」这类管理端点加鉴权。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        denied = _admin_denied()
        if denied is not None:
            return denied
        return fn(*args, **kwargs)
    return wrapper


@app.after_request
def _apply_headers(resp):
    """统一响应头：缓存策略 + 安全头。

    缓存：静态资源在各自路由里显式给了「一年 immutable」（URL 带内容哈希版本号，改资源即换
    URL，故不会读到旧文件）；其余响应（HTML / JSON / CSV）保持 ``no-store``。
    —— 取代原先「所有响应一律 no-store」的粗放做法：那会让 style.css / app.js / i18n.js
    永远无法被浏览器与 CDN 缓存，每次访问都重下（也是当年为绕开旧 i18n.js 缓存 bug 的权宜之计）。

    安全：nosniff / 防点击劫持 / Referrer 策略 / 权限策略 / CSP；HTTPS 下再加 HSTS。
    """
    if "Cache-Control" not in resp.headers:
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
    for key, value in _SECURITY_HEADERS.items():
        resp.headers.setdefault(key, value)
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        resp.headers.setdefault("Strict-Transport-Security",
                                "max-age=31536000; includeSubDomains")
    # C2 · ETag + 条件请求：内容未变则 304，省带宽。
    # 仅对 JSON 接口启用——HTML 页面必须保持 ``no-store``（见
    # tests/test_web.py::test_html_is_no_store），否则会破坏「页面永不缓存」的既定契约。
    if (resp.status_code == 200 and request.method in ("GET", "HEAD")
            and not resp.direct_passthrough and "ETag" not in resp.headers
            and resp.mimetype == "application/json"):
        resp.add_etag()
        # no-store 会让浏览器不再发条件请求；接口改为 no-cache（可存但每次校验）。
        if "no-store" in resp.headers.get("Cache-Control", ""):
            resp.headers["Cache-Control"] = "no-cache"
        resp = resp.make_conditional(request)

    # C3 · gzip 压缩：文本类、体积达标、客户端支持、尚未编码。
    if (resp.status_code == 200 and request.method in ("GET", "HEAD")
            and not resp.direct_passthrough
            and "Content-Encoding" not in resp.headers
            and _client_accepts_gzip()
            and resp.mimetype and resp.mimetype.startswith(_GZIP_MIMES)):
        _data = resp.get_data()
        if len(_data) >= _GZIP_MIN_BYTES:
            _compressed = _gzip.compress(_data, compresslevel=6)
            if len(_compressed) < len(_data):
                resp.set_data(_compressed)
                resp.headers["Content-Encoding"] = "gzip"
                resp.headers["Content-Length"] = str(len(_compressed))
                resp.vary.add("Accept-Encoding")
    return resp


def _lang() -> str:
    """请求语言：``?lang=`` 优先，其次 ``Accept-Language`` 头，最后默认 en（与前端默认一致）。

    数据标识符（专业 / 指标 / 维度 / 单位）由 :mod:`src.labels` 按此语言在服务端本地化，
    不再依赖浏览器端的词条替换——因此直接调接口的第三方也能拿到正确语言。
    """
    explicit = request.args.get("lang")
    if explicit:
        return labels.normalize_lang(explicit)
    return (labels.lang_from_accept_language(request.headers.get("Accept-Language"))
            or labels.DEFAULT_LANG)


def _html_lang() -> str:
    """页面 ``<html lang>``：按请求语言输出，供爬虫与分享链接使用。

    页面模板里写的是占位符 ``__HTML_LANG__``（见 ``public/index.html`` / ``app.html``），
    这里按 ``?lang=`` / ``Accept-Language`` 替换。原先两页都写死 ``zh-CN``，
    与「产品默认英文」矛盾——爬虫与分享卡片会误判语言。
    """
    return "zh-CN" if labels.normalize_lang(_lang()) == "zh" else "en"


def _dimension_arg() -> str:
    """维度入参：规范键（``中国``）与英文标签 / slug（``China`` / ``china``）等价。"""
    raw = (request.args.get("dimension") or "").strip()
    return labels.key_of("dimension", raw) if raw else DEFAULT_DIMENSION


def _category_arg() -> str | None:
    """专业入参：同样接受英文标签 / slug。"""
    raw = (request.args.get("category") or "").strip()
    return labels.key_of("category", raw) if raw else None


def _fmt(v: object) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}" if abs(v) < 1e6 else f"{v:,.0f}"
    return str(v)


def _overview(year: int, dimension: str, lang: str) -> dict[str, object]:
    """汇总首页需要的卡片（真实数据，按维度动态生成，附同比与出处）。

    每个字段给三层：本地化展示值 + ``*_key``（中文规范键）+ ``*_slug``（ASCII 稳定键）。
    ``dimensions`` / ``categories`` 保持规范键列表（可作为请求参数原样回传），
    另给 ``*_options`` 供前端下拉框用「键做 value、本地化文案做 label」。
    """
    raw = ind.dimension_cards(year, dimension)
    cards = [{
        "label": labels.label("indicator", str(c["label"]), lang),
        "label_key": str(c["label"]),
        "label_slug": labels.slug("indicator", str(c["label"])),
        "value": _fmt(c["value"]),
        "unit": labels.label("unit", str(c.get("unit", "")), lang),
        "unit_key": str(c.get("unit", "")),
        "unit_slug": labels.slug("unit", str(c.get("unit", ""))),
        "yoy": c.get("yoy", ""),
        "note": labels.localize_note(str(c.get("note", "")), lang),
        "note_key": str(c.get("note", "")),
        "dimension": labels.label("dimension", str(c.get("dimension", dimension)), lang),
        "dimension_key": str(c.get("dimension", dimension)),
        "dimension_slug": labels.slug("dimension", str(c.get("dimension", dimension))),
    } for c in raw]
    dims = ind.available_dimensions()
    cats = ind.all_categories()
    return {
        "year": year,
        "lang": lang,
        "dimension": labels.label("dimension", dimension, lang),
        "dimension_key": dimension,
        "dimension_slug": labels.slug("dimension", dimension),
        "cards": cards,
        "dimensions": dims,
        "years": ind.available_years(),
        "categories": cats,
        "dimension_options": labels.localize_terms("dimension", dims, lang),
        "category_options": labels.localize_terms("category", cats, lang),
    }


@app.route("/")
def index():
    return _render_page(pages.PAGE_INDEX)


@app.route("/app")
def app_page():
    return _render_page(pages.PAGE_APP)


@app.route("/docs")
def docs_page():
    """API 参考页（服务端按请求语言渲染，不依赖前端 JS）。

    端点清单与实现的一致性由 ``tests/test_web.py`` 对照 ``app.url_map`` 校验，
    防止新增路由后文档静默过期。
    """
    return _render_page(api_docs.render(_lang(), _BASE_URL))


@app.route("/privacy")
def privacy():
    """隐私与数据声明页（服务端按请求语言渲染，零 JS）。

    对外分发后被问得最多的就是「收集什么 / 数据从哪来 / AI 会不会把问题发出去」，
    答案固定在这一页，见 :mod:`src.privacy_page`。
    """
    return _render_page(privacy_page.render(_lang(), _BASE_URL))


@app.errorhandler(404)
def handle_404(err):
    """品牌一致的 404 页（而非 Flask 默认的英文白页）。JSON 请求仍回 JSON。"""
    if _wants_json():
        return jsonify({"ok": False, "error": "not found"}), 404
    return _render_page(error_pages.render(404, _lang(), _BASE_URL)), 404


@app.errorhandler(500)
def handle_500(err):  # pragma: no cover - 需要人为触发内部错误
    if _wants_json():
        return jsonify({"ok": False, "error": "internal server error"}), 500
    return _render_page(error_pages.render(500, _lang(), _BASE_URL)), 500


@app.errorhandler(405)
def handle_405(err):
    if _wants_json():
        return jsonify({"ok": False, "error": "method not allowed"}), 405
    return _render_page(error_pages.render(405, _lang(), _BASE_URL)), 405


def _wants_json() -> bool:
    """接口路径或显式 Accept: application/json 时回 JSON，否则回 HTML 错误页。"""
    if request.path.startswith("/api/"):
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept


@app.route("/robots.txt")
def serve_robots():
    return pages.ROBOTS_TXT, 200, {"Content-Type": "text/plain; charset=utf-8",
                                  "Cache-Control": "public, max-age=3600"}


@app.route("/sitemap.xml")
def serve_sitemap():
    return pages.SITEMAP_XML, 200, {"Content-Type": "application/xml; charset=utf-8",
                                    "Cache-Control": "public, max-age=3600"}


#: 分享卡片 PNG（内嵌为 base64），启动时解码一次。
_OG_IMAGE_PNG = base64.b64decode(pages.OG_IMAGE_PNG_B64)


@app.route("/og-image.png")
def serve_og_image():
    """社交分享卡片（og:image）——1200×630 PNG，由 scripts/make_og_image.py 生成。

    Facebook / X / LinkedIn 对 SVG 的 og:image 支持不稳定，故改用 PNG。
    """
    return Response(_OG_IMAGE_PNG, mimetype="image/png",
                    headers={"Cache-Control": _STATIC_CACHE})


@app.route("/style.css")
def serve_css():
    return pages.STYLE_CSS, 200, {"Content-Type": "text/css; charset=utf-8",
                                  "Cache-Control": _STATIC_CACHE}


@app.route("/app.js")
def serve_js():
    return pages.APP_JS, 200, {"Content-Type": "application/javascript; charset=utf-8",
                               "Cache-Control": _STATIC_CACHE}


@app.route("/i18n.js")
def serve_i18n():
    return pages.I18N_JS, 200, {"Content-Type": "application/javascript; charset=utf-8",
                                "Cache-Control": _STATIC_CACHE}


@app.route("/favicon.svg")
def serve_favicon():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="14" fill="#2B6BDB"/>'
        '<path d="M14 44V28h7v16zM28 44V20h7v24zM42 44V32h7v12z" fill="#fff"/>'
        "</svg>"
    )
    return svg, 200, {"Content-Type": "image/svg+xml; charset=utf-8",
                      "Cache-Control": _STATIC_CACHE}


@app.route("/api/overview")
def api_overview():
    year = request.args.get("year", type=int) or DEFAULT_YEAR
    return jsonify(_overview(year, _dimension_arg(), _lang()))


@app.route("/api/stats")
def api_stats():
    """公开只读的「数据规模」统计——落地页首屏与看板侧栏用它填数字。

    与 ``/api/db`` 的分工：后者是**管理端点**，含库文件路径、引擎等环境细节，
    部署到 Vercel 后一律 403（见 :func:`_admin_denied`）；本端点只暴露可对外公开的
    聚合计数与覆盖范围，故保持公开。

    —— 前端若误用被鉴权端点，线上页面会整片显示「—」且不报错（静默功能缺失），
    这正是本端点存在的理由。
    """
    info = db_info()          # 内部已 init_db()
    dims = ind.available_dimensions()
    years = ind.available_years()
    return jsonify({
        "indicator_rows": int(info["indicator_rows"]),
        "knowledge_rows": int(info["knowledge_rows"]),
        "dimension_count": len(dims),
        "year_count": len(years),
        "years": years,
        "dimensions": dims,
    })


@app.route("/api/db")
@admin_required
def api_db():
    init_db()
    return jsonify(db_info())


@app.route("/api/reseed", methods=["POST"])
@admin_required
def api_reseed():
    """一次性全量重播种：清空 indicators 表后重新载入真实公开数据种子集。

    先删除 KV 旧 key，写入后 KV 自动同步，下次冷启动不再回退到旧数据。
    """
    from src.db import init_db, INDICATORS, engine, count_indicators
    from src.loader import load_seed_data
    from src.kv_store import kv_available, kv_delete as _kv_del
    init_db()
    if kv_available():
        try:
            _kv_del("qu_stat_ap:indicators")
        except Exception:
            pass
    with engine.begin() as conn:
        conn.execute(INDICATORS.delete())
    n = load_seed_data()
    return jsonify({"ok": True, "count": n, "total_in_db": count_indicators()})


@app.route("/api/kv-status")
@admin_required
def api_kv_status():
    """调试端点：检查 Redis 持久化连接状态。"""
    import os as _os2
    from src.kv_store import kv_available, kv_set_json, kv_get_json, kv_delete

    keys = ["KV_REST_API_URL", "KV_REST_API_TOKEN", "KV_URL", "KV_REST_API_READ_ONLY_TOKEN",
            "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN",
            "QU_STAT_REDIS_URL", "QU_STAT_REDIS_TOKEN",
            "REDIS_URL", "REDIS_HOST"]
    env_status: dict[str, object] = {}
    for k in keys:
        v = _os2.environ.get(k)
        env_status[k] = (v[:10] + "…" if len(v) > 10 else "***") if v else None

    status: dict[str, object] = {
        "available": kv_available(),
        "env_vars": env_status,
    }
    if kv_available():
        test_key = "qu_stat_ap:__ping__"
        ok = kv_set_json(test_key, {"ts": "ok"})
        result = kv_get_json(test_key)
        kv_delete(test_key)
        status["write_ok"] = ok
        status["read_ok"] = result is not None
    return jsonify(status)


@app.route("/api/knowledge", methods=["GET", "POST", "DELETE"])
def api_knowledge():
    init_db()
    if request.method == "POST":
        d = request.get_json(force=True) or {}
        title = str(d.get("title", "")).strip()
        content = str(d.get("content", "")).strip()
        if not title or not content:
            return jsonify({"ok": False, "error": "title 与 content 必填"}), 400
        kid = kb.add_knowledge(
            title, str(d.get("category", "通用")) or "通用",
            str(d.get("tags", "")), content, str(d.get("source", "")),
        )
        return jsonify({"ok": True, "id": kid})
    if request.method == "DELETE":
        kid = request.args.get("id", type=int)
        if kid is None:
            return jsonify({"ok": False, "error": "缺少 id"}), 400
        return jsonify({"ok": kb.delete_knowledge(kid)})
    q = (request.args.get("q") or "").strip()
    cat = request.args.get("category")
    rows = kb.search_knowledge(q) if q else kb.list_knowledge(cat)
    return jsonify(rows)


@app.route("/api/collect", methods=["POST"])
@admin_required
def api_collect():
    init_db()
    d = request.get_json(force=True) or {}
    source = str(d.get("source", "worldbank"))
    year = d.get("year")
    country = d.get("country")
    indicators = d.get("indicators")
    countries = d.get("countries")
    inds = (
        indicators.split(",") if isinstance(indicators, str) and indicators
        else (indicators if isinstance(indicators, list) else None)
    )
    ctry = (
        countries.split(",") if isinstance(countries, str) and countries
        else (countries if isinstance(countries, list) else None)
    )
    try:
        if source == "global":
            n = collector.collect_global(year=year, indicators=inds,
                                         countries=ctry)
        else:
            n = collector.collect_worldbank(year=year, country=country,
                                            indicators=inds)
        return jsonify({"ok": True, "count": n})
    except collector.CollectError as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@app.route("/api/indicators")
def api_indicators():
    """指标宽表查询。

    这是给程序消费的主要数据接口：每行的 ``category`` / ``indicator`` /
    ``dimension`` / ``unit`` 按 ``lang`` 本地化，并并列给出 ``*_key``（中文规范键）
    与 ``*_slug``（ASCII 稳定键），英文消费方无需任何中文词表即可使用。
    """
    lang = _lang()
    year = request.args.get("year", type=int)
    dimension_raw = (request.args.get("dimension") or "").strip()
    dimension = labels.key_of("dimension", dimension_raw) if dimension_raw else None
    indicator_raw = (request.args.get("indicator") or "").strip()
    indicator = labels.key_of("indicator", indicator_raw) if indicator_raw else None
    q = (request.args.get("q") or "").strip().lower()
    rows = query_indicators(year=year, category=_category_arg(),
                            dimension=dimension, indicator=indicator)
    localized = labels.localize_indicators(rows, lang)
    if q:
        # 同时匹配「原始行 + 本地化行」的全部字段：中文词、英文词、
        # 规范键与 slug 都能命中（例如 q=retail 命中 Retail Sales of Consumer Goods）
            localized = [
            loc for raw, loc in zip(rows, localized)
            if q in " ".join(
                str(v) for v in list(raw.values()) + list(loc.values())
            ).lower()
        ]
    return jsonify(localized)


@app.route("/api/export.csv")
def api_export_csv():
    """导出当前筛选条件下的指标宽表为 CSV（按 lang 本地化）。

    复用 ``query_indicators`` + ``labels.localize_indicators``；列定义与 CLI 的
    ``report.export_csv`` 保持一致（year/category/indicator/dimension/value/unit/note），
    便于第三方直接消费。

    - ``year`` / ``dimension`` 缺省表示「全部」：年份不传 → 跨年全量；维度不传 → 全经济体。
      图表面板的「导出当前指标」即利用此特性导出一个指标的完整跨年 × 全经济体序列。
    - 文件名含年份（或 all）、维度 slug 与语言，内容带 BOM（utf-8-sig）以便 Excel 直接打开。
    """
    import csv as _csv
    import io as _io

    lang = _lang()
    year = request.args.get("year", type=int)
    dimension_raw = (request.args.get("dimension") or "").strip()
    dimension = labels.key_of("dimension", dimension_raw) if dimension_raw else None
    indicator_raw = (request.args.get("indicator") or "").strip()
    indicator = labels.key_of("indicator", indicator_raw) if indicator_raw else None
    q = (request.args.get("q") or "").strip().lower()

    rows = query_indicators(year=year, category=_category_arg(),
                            dimension=dimension, indicator=indicator)
    localized = labels.localize_indicators(rows, lang)
    if q:
        localized = [
            loc for raw, loc in zip(rows, localized)
            if q in " ".join(str(v) for v in list(raw.values()) + list(loc.values())).lower()
        ]

    fieldnames = ["year", "category", "indicator", "dimension", "value", "unit", "note"]
    buf = _io.StringIO()
    w = _csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for loc in localized:
        w.writerow({k: loc.get(k, "") for k in fieldnames})
    data = buf.getvalue().encode("utf-8-sig")

    year_part = "all" if year is None else str(year)
    dim_part = labels.slug("dimension", dimension) if dimension else "all"
    fname = f"indicators_{year_part}_{dim_part}_{lang}.csv"
    return Response(
        data,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


def _cloud_prompt(text: str, local: dict[str, object], lang: str) -> str:
    """把本地统计结果作为事实上下文交给云端 AI，避免模型编数字。"""
    facts = json.dumps(
        {k: v for k, v in local.items() if k not in ("知识库参考",)},
        ensure_ascii=False, indent=2, default=str)
    if lang == "zh":
        return (
            "你是资深统计分析师。下面是本系统从公开数据源（世界银行 Open Data、"
            "国家统计局、海关总署）取到的真实统计结果，请**只依据这些数字**回答用户问题，"
            "输出 3-5 条要点（可用 Markdown 列表），指出关键变化与 1-2 个需关注的风险。"
            "不要编造未给出的数据。\n\n"
            f"【用户问题】\n{text}\n\n【系统取到的真实数据】\n{facts}"
        )
    return (
        "You are a senior statistical analyst. Below are the real figures this system "
        "retrieved from public sources (World Bank Open Data, China NBS, China Customs). "
        "Answer the user's question using ONLY these numbers. Reply in English with 3-5 "
        "concise bullet points (Markdown), highlighting key movements and 1-2 risks to watch. "
        "Do not invent any figures that are not given.\n\n"
        f"[User question]\n{text}\n\n[Retrieved real data]\n{facts}"
    )


@app.route("/api/ask")
def api_ask():
    text = request.args.get("text", "")
    use_cloud = request.args.get("cloud", "0") == "1"
    dimension_raw = (request.args.get("dimension") or "").strip()
    dimension = labels.key_of("dimension", dimension_raw) if dimension_raw else None
    lang = _lang()
    local = nlq.ask(text, dimension=dimension, lang=lang)

    if not use_cloud:
        return jsonify(labels.localize_payload(local, lang))

    from src.analyzer import get_analyzer, AgentInfiniError
    try:
        az = get_analyzer(lang=lang)
        if az is None:
            local["注"] = ("Cloud AI is not enabled — showing local statistics only."
                           if lang == "en" else "云端未启用，仅本地统计")
            return jsonify(labels.localize_payload(local, lang))
        # 云端提示词喂原始（中文规范键）事实，避免本地化后再回溯口径
        from src.analyzer import build_facts_files
        facts = build_facts_files(local, lang)
        out = az.analyze(_cloud_prompt(text, local, lang), files=facts)
        answer = str(out.get("result") or "").strip()
        if answer:
            local["AI 解读"] = answer
        if out.get("task_id"):
            local["task_id"] = out["task_id"]
        if out.get("console_url"):
            local["console_url"] = out["console_url"]
        return jsonify(labels.localize_payload(local, lang))
    except AgentInfiniError as e:
        local["注"] = (f"Cloud analysis failed: {e}" if lang == "en"
                       else f"云端分析失败：{e}")
        return jsonify(labels.localize_payload(local, lang))


@app.route("/api/report")
def api_report():
    year = request.args.get("year", type=int) or DEFAULT_YEAR
    use_cloud = request.args.get("cloud", "0") == "1"
    lang = _lang()
    dimension = _dimension_arg()
    # format=json：返回结构化公报，标识符由服务端按 lang 本地化后交给前端渲染
    if request.args.get("format") == "json":
        built = report.build_report(year, use_cloud=use_cloud,
                                    dimension=dimension, lang=lang)
        return jsonify(labels.localize_payload(built, lang))
    return report.generate_report(year, use_cloud=use_cloud,
                                  dimension=dimension, lang=lang)


@app.route("/api/indicator_keys")
def api_indicator_keys():
    """返回全部可绑定指标键，供「新增自定义分析」下拉选择。

    每项给本地化的 ``category`` / ``indicator`` / ``dimension`` 用于展示，
    同时给 ``*_key``（写回 YAML 用的规范键）与 ``*_slug``（ASCII 稳定键）。
    """
    init_db()
    lang = _lang()
    rows = query_indicators()
    keys: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for r in rows:
        k = (r.get("category", ""), r.get("indicator", ""), r.get("dimension", ""))
        if k in seen:
            continue
        seen.add(k)
        entry: dict[str, str] = {}
        for field, value in zip(("category", "indicator", "dimension"), k):
            entry[field] = labels.label(field, value, lang)
            entry[f"{field}_key"] = value
            entry[f"{field}_slug"] = labels.slug(field, value)
        keys.append(entry)
    return jsonify(keys)


@app.route("/api/custom", methods=["GET", "POST"])
def api_custom():
    lang = _lang()
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        ok, err = cust.add_custom(data, lang=lang)
        if not ok:
            return jsonify({"ok": False, "error": err}), 400
        return jsonify({"ok": True})
    name = request.args.get("name")
    year = request.args.get("year", type=int) or DEFAULT_YEAR
    if not name:
        return jsonify(cust.list_custom(lang))
    a = cust.find_custom(name)
    if a is None:
        msg = (f"Custom analysis not found: {name}" if lang == "en"
               else f"未找到自定义分析：{name}")
        return jsonify({"error": msg}), 404
    # 自定义分析的「名称」是用户自己写的配置（name / name_en），已由 run_custom 按语言取用；
    # 这里只把结构键与单位等数据词条本地化。
    from src.stats import sql_engine
    engine_name = (request.args.get("engine") or "").strip().lower() or None
    result = sql_engine.run_custom(a, year, lang, engine_name)
    return jsonify(labels.localize_payload(result, lang))


@app.route("/api/infini_skill")
def api_infini_skill():
    """按 agent_infini Skill 规范暴露集成自检：推荐工作流 + 资源预检。

    只读端点，不触发任何云端调用；CLI 不可用时自动降级为「声明式」结果。
    """
    from src import infini_skill
    db_ids = [x for x in (request.args.get("db") or "").split(",") if x.strip()]
    rag_ids = [x for x in (request.args.get("rag") or "").split(",") if x.strip()]
    creds = infini_skill.skill_credentials()
    return jsonify({
        "skill": infini_skill.SKILL_NAME,
        "config_found": bool(creds.get("server") or creds.get("api_key")),
        "cli": infini_skill.resolve_cli_path(),
        "workflow": infini_skill.recommended_workflow(),
        "preflight": infini_skill.preflight(db_ids, rag_ids),
    })


def _is_legacy_dataset(dims: set[str]) -> bool:
    """判别区级旧快照：真实亚太种子必含「亚太」聚合维度，旧数据必缺。

    早先按行数判别（<30 行视为旧合成数据）拦不住 51 行的区级 demo 快照——
    它混进线上后，英文首页维度下拉直漏中文「全区」且默认视图为空看板。
    """
    return "亚太" not in dims


def _ensure_data() -> None:
    """首次启动保证有内容（真实公开数据）。优先从 KV 恢复，避免重复写入（加速冷启动）。"""
    from src.db import init_db, count_indicators
    from src import knowledge as kb
    from src.loader import load_seed_data

    init_db()

    # 优先从 KV 恢复（Redis 持久化）：有数据则直接用，省去种子数据写入
    from src.kv_store import kv_available, kv_delete as _kv_del
    if kv_available():
        from src.kv_sync import restore_from_kv
        try:
            if restore_from_kv():
                if _is_legacy_dataset({str(r["dimension"]) for r in query_indicators()}):
                    # 旧版 KV 里是已废弃的区级/合成快照 → 清掉重灌真实亚太数据
                    from src.db import INDICATORS, engine
                    with engine.begin() as conn:
                        conn.execute(INDICATORS.delete())
                    load_seed_data()
                    try:
                        _kv_del("qu_stat_ap:indicators")
                    except Exception as exc:
                        # 清表+重播种已完成，此处只影响 KV 是否留着脏快照；
                        # 单独成一条日志，运维才能把它和「恢复失败」区分开。
                        app.logger.warning("kv purge after reseed failed: %s", exc)
                else:
                    # 恢复成功：补齐缺失年份
                    try:
                        existing = {r["year"] for r in query_indicators()}
                        missing = [y for y in ind.available_years() if y not in existing]
                        if missing:
                            load_seed_data(missing)
                    except Exception as exc:
                        app.logger.warning("year seeding skipped: %s", exc)
                # 知识库按标题幂等补齐（含中英文两组种子）
                try:
                    kb.seed_default_knowledge()
                except Exception as exc:
                    app.logger.warning("knowledge seeding skipped: %s", exc)
                return
        except Exception as exc:  # KV 恢复失败不应阻断看板启动
            app.logger.warning("kv restore skipped: %s", exc)

    # KV 不可用或为空：载入真实公开数据 + 知识库
    if count_indicators() == 0:
        try:
            load_seed_data()
        except Exception as exc:  # 播种失败不应阻断看板启动
            app.logger.warning("seed data loading skipped: %s", exc)
    try:
        kb.seed_default_knowledge()
    except Exception as exc:
        app.logger.warning("knowledge seeding skipped: %s", exc)


# 本地直接运行时执行数据初始化；Vercel 入口 api/index.py 会自行调用
if __name__ == "__main__":
    _ensure_data()
    # debug=True 会注入 Werkzeug 调试工具栏（依赖 getBoundingClientRect），
    # 在嵌入式 WebView 中会触发 null 引用报错，故用 debug=False。
    app.run(host="127.0.0.1", port=5000, debug=False)
