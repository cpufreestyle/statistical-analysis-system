"""Web 看板（Flask，纯离线、无外部 CDN 依赖）。

启动：python -m src.cli web   访问 http://127.0.0.1:5000
页面数据全部来自本地 SQLite / 统计函数；图表用内联 SVG 绘制。
数据源为公开开放数据（世界银行 Open Data + 国家统计局 / 海关总署公开发布）。
"""
from __future__ import annotations

import json
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

DEFAULT_DIMENSION = "亚太"
DEFAULT_YEAR = 2024


@app.after_request
def _no_cache(resp):
    """页面与静态资源一律不缓存。

    曾出过问题：改完前端后浏览器仍用启发式缓存的旧 /i18n.js
    （那版脚本抛 ReferenceError，导致 toggleLang 未定义、语言切换按钮失效）。
    """
    resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp


def _lang() -> str:
    """请求语言：zh / en（默认 en，与前端默认语言一致）。"""
    v = (request.args.get("lang") or "").strip().lower()
    return "zh" if v.startswith("zh") else "en"


def _fmt(v: object) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}" if abs(v) < 1e6 else f"{v:,.0f}"
    return str(v)


def _overview(year: int, dimension: str) -> dict[str, object]:
    """汇总首页需要的卡片（真实数据，按维度动态生成，附同比与出处）。"""
    raw = ind.dimension_cards(year, dimension)
    cards = [{
        "label": c["label"],
        "value": _fmt(c["value"]),
        "unit": c.get("unit", ""),
        "yoy": c.get("yoy", ""),
        "note": c.get("note", ""),
        "dimension": c.get("dimension", dimension),
    } for c in raw]
    return {
        "year": year,
        "dimension": dimension,
        "cards": cards,
        "dimensions": ind.available_dimensions(),
        "years": ind.available_years(),
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


@app.route("/favicon.svg")
def serve_favicon():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="14" fill="#2B6BDB"/>'
        '<path d="M14 44V28h7v16zM28 44V20h7v24zM42 44V32h7v12z" fill="#fff"/>'
        "</svg>"
    )
    return svg, 200, {"Content-Type": "image/svg+xml; charset=utf-8"}


@app.route("/api/overview")
def api_overview():
    year = request.args.get("year", type=int) or DEFAULT_YEAR
    dimension = (request.args.get("dimension") or DEFAULT_DIMENSION).strip()
    return jsonify(_overview(year, dimension))


@app.route("/api/db")
def api_db():
    init_db()
    return jsonify(db_info())


@app.route("/api/reseed", methods=["POST"])
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
    dimension = (request.args.get("dimension") or "").strip() or None
    q = (request.args.get("q") or "").strip().lower()
    rows = query_indicators(year=year, category=category or None,
                            dimension=dimension)
    if q:
        rows = [
            r for r in rows
            if q in r["indicator"].lower() or q in (r["note"] or "").lower()
            or q in r["dimension"].lower() or q in r["category"].lower()
        ]
    return jsonify(rows)


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
    dimension = (request.args.get("dimension") or "").strip() or None
    lang = _lang()
    local = nlq.ask(text, dimension=dimension)

    if not use_cloud:
        return jsonify(local)

    from src.analyzer import get_analyzer, AgentInfiniError
    try:
        az = get_analyzer(lang=lang)
        if az is None:
            local["注"] = ("Cloud AI is not enabled — showing local statistics only."
                           if lang == "en" else "云端未启用，仅本地统计")
            return jsonify(local)
        out = az.analyze(_cloud_prompt(text, local, lang))
        answer = str(out.get("result") or "").strip()
        if answer:
            local["AI 解读"] = answer
        if out.get("task_id"):
            local["task_id"] = out["task_id"]
        return jsonify(local)
    except AgentInfiniError as e:
        local["注"] = (f"Cloud analysis failed: {e}" if lang == "en"
                       else f"云端分析失败：{e}")
        return jsonify(local)


@app.route("/api/report")
def api_report():
    year = request.args.get("year", type=int) or DEFAULT_YEAR
    dimension = (request.args.get("dimension") or DEFAULT_DIMENSION).strip()
    use_cloud = request.args.get("cloud", "0") == "1"
    # format=json：返回结构化公报，由前端按界面语言渲染（避免服务端硬编码文案漏译）
    if request.args.get("format") == "json":
        return jsonify(report.build_report(
            year, use_cloud=use_cloud, dimension=dimension, lang=_lang()))
    return report.generate_report(year, use_cloud=use_cloud,
                                  dimension=dimension, lang=_lang())


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
    year = request.args.get("year", type=int) or DEFAULT_YEAR
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
                if count_indicators() < 30:
                    # 旧版 KV 里是已废弃的合成示例数据 → 清掉重灌真实数据
                    from src.db import INDICATORS, engine
                    with engine.begin() as conn:
                        conn.execute(INDICATORS.delete())
                    load_seed_data()
                    try:
                        _kv_del("qu_stat_ap:indicators")
                    except Exception:
                        pass
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
