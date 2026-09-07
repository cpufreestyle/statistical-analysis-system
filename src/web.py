"""Web 看板（Flask，纯离线、无外部 CDN 依赖）。

启动：python -m src.cli web   访问 http://127.0.0.1:5000
页面数据全部来自本地 SQLite / 统计函数；图表用内联 SVG 绘制。
"""
from __future__ import annotations

import os as _os

# 本地看板跑在 127.0.0.1，必须排除出系统 HTTP 代理（如 127.0.0.1:7897），
# 否则代理会拦截本地请求导致预览/接口连接被拒。
_os.environ.setdefault("no_proxy", "127.0.0.1,localhost")
_os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
if "127.0.0.1" not in _os.environ.get("no_proxy", ""):
    _os.environ["no_proxy"] = (_os.environ.get("no_proxy", "") + ",127.0.0.1,localhost").strip(",")
if "127.0.0.1" not in _os.environ.get("NO_PROXY", ""):
    _os.environ["NO_PROXY"] = (_os.environ.get("NO_PROXY", "") + ",127.0.0.1,localhost").strip(",")

from flask import Flask, request, jsonify

from src import report
from src.db import query_indicators, db_info, init_db
from src import knowledge as kb
from src import collect as collector
from src.stats import indicators as ind
from src.stats import query as nlq
from src.stats import custom as cust
from src import pages

app = Flask(__name__)


@app.after_request
def _no_cache(resp):
    """页面与静态资源一律不缓存。

    曾出过问题：改完前端后浏览器仍用启发式缓存的旧 /i18n.js
    （那版脚本抛 ReferenceError，导致 toggleLang 未定义、语言切换按钮失效）。
    """
    resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp


def _fmt(v: object) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v)


def _overview(year: int) -> dict[str, object]:
    """汇总首页需要的卡片、街镇排名、专业列表。"""
    gdp = ind.gdp_overview(year, year - 1)
    indu = ind.industry_stats(year)
    trade = ind.trade_stats(year)
    inv = ind.investment_stats(year)
    pop = ind.population_stats(year)

    cards = [
        {"label": "地区生产总值 (GDP)", "value": _fmt(gdp.get("数值(亿元)")),
         "sub": f"同比 {gdp.get('同比')}"},
        {"label": "规上工业总产值", "value": _fmt(indu.get("规上工业总产值(亿元)")),
         "sub": f"增加值 {_fmt(indu.get('规上工业增加值(亿元)'))} 亿元"},
        {"label": "社会消费品零售总额", "value": _fmt(trade.get("社会消费品零售总额(亿元)")),
         "sub": f"限上销售额 {_fmt(trade.get('限额以上商品销售额(亿元)'))} 亿元"},
        {"label": "固定资产投资总额", "value": _fmt(inv.get("固定资产投资总额(亿元)")),
         "sub": f"工业投资占比 {_fmt(inv.get('工业投资占比(%)'))}%"},
        {"label": "常住人口", "value": _fmt(pop.get("常住人口(万人)")),
         "sub": f"人均可支配收入 {_fmt(pop.get('居民人均可支配收入(元)'))} 元"},
    ]
    return {
        "year": year,
        "cards": cards,
        "towns": indu.get("分街镇排名"),
        "categories": ind.all_categories(),
    }


@app.route("/")
def index():
    return pages.PAGE_INDEX


@app.route("/app")
def app_page():
    return pages.PAGE_APP


@app.route("/style.css")
def serve_css():
    return pages.STYLE_CSS, 200, {"Content-Type": "text/css; charset=utf-8"}


@app.route("/app.js")
def serve_js():
    return pages.APP_JS, 200, {"Content-Type": "application/javascript; charset=utf-8"}


@app.route("/i18n.js")
def serve_i18n():
    return pages.I18N_JS, 200, {"Content-Type": "application/javascript; charset=utf-8"}


@app.route("/api/overview")
def api_overview():
    year = int(request.args.get("year", 2024))
    return jsonify(_overview(year))


@app.route("/api/db")
def api_db():
    from src.db import init_db
    init_db()
    return jsonify(db_info())


@app.route("/api/reseed", methods=["POST"])
def api_reseed():
    """一次性全量重播种：清空 indicators 表后重新生成 2024-2026 全国口径数据（51 条）。
    先删除 KV 旧 key，写入后 KV 自动同步，下次冷启动不再回退到旧数据。"""
    from src.db import init_db, INDICATORS, engine
    from src.loader import generate_national_sample_data
    from src.kv_store import kv_available, kv_delete as _kv_del
    init_db()
    # 先删 KV 旧数据
    if kv_available():
        try:
            _kv_del("qu_stat_ap:indicators")
        except Exception:
            pass
    with engine.begin() as conn:
        conn.execute(INDICATORS.delete())
    n = generate_national_sample_data()
    from src.db import count_indicators
    return jsonify({"ok": True, "count": n, "total_in_db": count_indicators()})


@app.route("/api/kv-status")
def api_kv_status():
    """调试端点：检查 Redis 持久化连接状态。"""
    import os as _os
    from src.kv_store import kv_available, kv_set_json, kv_get_json, kv_delete

    # 列出所有 KV 相关环境变量（脱敏展示）
    keys = ["KV_REST_API_URL", "KV_REST_API_TOKEN", "KV_URL", "KV_REST_API_READ_ONLY_TOKEN",
            "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN",
            "QU_STAT_REDIS_URL", "QU_STAT_REDIS_TOKEN",
            "REDIS_URL", "REDIS_HOST"]
    env_status: dict[str, object] = {}
    for k in keys:
        v = _os.environ.get(k)
        if v:
            env_status[k] = v[:10] + "…" if len(v) > 10 else "***"
        else:
            env_status[k] = None

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
    year = request.args.get("year", type=int)
    category = request.args.get("category")
    q = (request.args.get("q") or "").strip().lower()
    rows = query_indicators(year=year, category=category or None)
    if q:
        rows = [
            r for r in rows
            if q in r["indicator"].lower() or q in (r["note"] or "").lower()
            or q in r["dimension"].lower() or q in r["category"].lower()
        ]
    return jsonify(rows)


@app.route("/api/ask")
def api_ask():
    text = request.args.get("text", "")
    use_cloud = request.args.get("cloud", "0") == "1"
    if use_cloud:
        from src.analyzer import get_analyzer, AgentInfiniError
        try:
            az = get_analyzer()
            if az is None:
                return jsonify({"注": "云端未启用，仅本地统计", **nlq.ask(text)})
            return jsonify(az.analyze(text))
        except AgentInfiniError as e:
            return jsonify({"注": f"云端分析失败：{e}", **nlq.ask(text)})
    return jsonify(nlq.ask(text))


@app.route("/api/report")
def api_report():
    year = int(request.args.get("year", 2024))
    use_cloud = request.args.get("cloud", "0") == "1"
    return report.generate_report(year, use_cloud=use_cloud)


@app.route("/api/indicator_keys")
def api_indicator_keys():
    """返回全部可绑定指标键 (category, indicator, dimension)，供新增分析时下拉选择。"""
    init_db()
    rows = query_indicators()
    keys: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for r in rows:
        k = (r.get("category", ""), r.get("indicator", ""), r.get("dimension", ""))
        if k in seen:
            continue
        seen.add(k)
        keys.append({"category": k[0], "indicator": k[1], "dimension": k[2]})
    return jsonify(keys)


@app.route("/api/custom", methods=["GET", "POST"])
def api_custom():
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        ok, err = cust.add_custom(data)
        if not ok:
            return jsonify({"ok": False, "error": err}), 400
        return jsonify({"ok": True})
    name = request.args.get("name")
    year = int(request.args.get("year", 2024))
    if not name:
        return jsonify([
            {"name": a.get("name", ""), "description": a.get("description", ""),
             "unit": a.get("unit", "")}
            for a in cust.load_custom()
        ])
    a = next((x for x in cust.load_custom() if x.get("name") == name), None)
    if a is None:
        return jsonify({"error": f"未找到自定义分析：{name}"}), 404
    return jsonify(cust.run_custom(a, year))


def _ensure_data() -> None:
    """首次启动保证有内容。优先从 KV 恢复持久化数据，避免重复播种示例（加速冷启动）。"""
    from src.db import init_db, count_indicators
    from src import knowledge as kb

    init_db()

    # 优先从 KV 恢复（Redis 持久化）：有数据则直接用，省去示例数据写入
    from src.kv_store import kv_available, kv_delete as _kv_del
    if kv_available():
        from src.kv_sync import restore_from_kv
        try:
            if restore_from_kv():
                total = count_indicators()
                # 旧版 KV 中只有 2024 年亚太口径 16 条示例数据 → 全量重灌全国口径
                if total < 30:
                    from src.db import INDICATORS, engine
                    from src.loader import generate_national_sample_data
                    with engine.begin() as conn:
                        conn.execute(INDICATORS.delete())
                    generate_national_sample_data()
                    # 删除旧 KV key，避免下次冷启动又恢复旧数据
                    try:
                        _kv_del("qu_stat_ap:indicators")
                    except Exception:
                        pass
                else:
                    # 恢复成功：补齐缺失年份的全国示例数据
                    from src.loader import generate_national_sample_data
                    from src.db import query_indicators
                    try:
                        existing = {r["year"] for r in query_indicators()}
                        missing = [y for y in (2024, 2025, 2026) if y not in existing]
                        if missing:
                            generate_national_sample_data(missing)
                    except Exception as exc:
                        app.logger.warning("year seeding skipped: %s", exc)
                # 知识库为空则补种子
                if kb.count_knowledge() == 0:
                    kb.seed_default_knowledge()
                return
        except Exception as exc:  # KV 恢复失败不应阻断看板启动
            app.logger.warning("kv restore skipped: %s", exc)

    # KV 不可用或为空：播种示例数据 + 知识库（仅首次空库）
    if count_indicators() == 0:
        from src.loader import generate_national_sample_data
        try:
            generate_national_sample_data()
        except Exception as exc:  # 播种失败不应阻断看板启动
            app.logger.warning("sample data seeding skipped: %s", exc)
    if kb.count_knowledge() == 0:
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
