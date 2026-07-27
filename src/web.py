"""Web 看板（Flask，纯离线、无外部 CDN 依赖）。

启动：python -m src.cli web   访问 http://127.0.0.1:5000
页面数据全部来自本地 SQLite / 统计函数；图表用内联 SVG 绘制。
"""
from __future__ import annotations

from flask import Flask, request, jsonify

from src import report
from src.db import query_indicators
from src.stats import indicators as ind
from src.stats import query as nlq

app = Flask(__name__)


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


PAGE = """
<!doctype html><html lang=zh><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>宝山区统计系统</title>
<style>
:root{--bg:#f6f8fa;--card:#fff;--bd:#e1e4e8;--blue:#2563eb;--ink:#1f2d3d;--mut:#6b7280}
*{box-sizing:border-box}
body{font-family:system-ui,"Microsoft YaHei",sans-serif;margin:0;background:var(--bg);color:var(--ink)}
header{background:linear-gradient(90deg,#1e3a8a,#2563eb);color:#fff;padding:1.2rem 2rem}
header h1{margin:0;font-size:1.4rem}header p{margin:.2rem 0 0;opacity:.85;font-size:.85rem}
.wrap{max-width:1080px;margin:1.5rem auto;padding:0 1rem}
.bar{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;margin-bottom:1rem}
input,select{padding:.5rem .6rem;border:1px solid #ccc;border-radius:6px;font-size:.95rem}
button{padding:.5rem 1rem;border:0;background:var(--blue);color:#fff;border-radius:6px;cursor:pointer}
button.ghost{background:#fff;color:var(--blue);border:1px solid var(--blue)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:.9rem}
.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:1rem 1.1rem}
.card .label{font-size:.8rem;color:var(--mut)}.card .val{font-size:1.5rem;font-weight:700;margin:.3rem 0}
.card .sub{font-size:.75rem;color:var(--mut)}
section{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:1.1rem 1.3rem;margin-top:1.2rem}
section h2{margin:.1rem 0 .8rem;font-size:1.05rem}
pre{white-space:pre-wrap;word-break:break-word;background:#0f172a;color:#e2e8f0;padding:.9rem;border-radius:8px;overflow:auto;max-height:360px;font-size:.85rem}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{border:1px solid #eee;padding:.45rem .6rem;text-align:left}
th{background:#f1f5f9}
.bars{display:flex;flex-direction:column;gap:.5rem}
.row{display:flex;align-items:center;gap:.6rem}
.row .name{width:5rem;font-size:.85rem;color:var(--mut)}
.track{flex:1;background:#eef2f7;border-radius:6px;overflow:hidden}
.fill{height:1.4rem;background:linear-gradient(90deg,#3b82f6,#2563eb);border-radius:6px}
.row .num{width:5rem;text-align:right;font-size:.85rem}
</style></head>
<body>
<header><h1>宝山区统计系统</h1><p>离线数据分析 · 参考 agent_infini 的「数据源 + 多轮分析」本地化实现</p></header>
<div class=wrap>

  <div class=bar>
    <label>年份</label><input id=year type=number value=2024 style="width:6rem">
    <button onclick=loadAll()>刷新看板</button>
    <span id=status style="color:var(--mut);font-size:.8rem"></span>
  </div>

  <div id=cards class=grid></div>

  <section><h2>各街镇规上工业总产值（亿元）</h2><div id=townChart class=bars></div></section>

  <section>
    <h2>自然语言查询</h2>
    <div class=bar>
      <input id=q placeholder='如：2024年宝山区GDP；各街镇工业排名' style="width:70%">
      <button onclick=ask()>分析</button>
      <button class=ghost onclick="ask(true)">云端解读</button>
    </div>
    <pre id=out>在上方输入问题后点击「分析」。</pre>
  </section>

  <section>
    <h2>指标总表</h2>
    <div class=bar>
      <label>专业</label>
      <select id=cat><option value="">全部</option></select>
      <button onclick=loadTable()>查询</button>
    </div>
    <div style="overflow:auto;max-height:420px">
      <table id=tbl><thead><tr>
        <th>年份</th><th>专业</th><th>指标</th><th>维度</th><th>数值</th><th>单位</th><th>说明</th>
      </tr></thead><tbody></tbody></table>
    </div>
  </section>

  <section>
    <h2>统计公报</h2>
    <pre id=bulletin></pre>
    <button class=ghost onclick=aiInterpret()>AI 解读（云端）</button>
    <pre id=ai style="margin-top:.6rem"></pre>
  </section>

</div>
<script>
const Y = () => document.getElementById('year').value;
const setStatus = t => document.getElementById('status').textContent = t;

async function loadAll(){
  loadOverview(); loadTable(); loadBulletin();
}

async function loadOverview(){
  setStatus('加载中…');
  const r = await fetch('/api/overview?year='+Y());
  const d = await r.json();
  document.getElementById('cards').innerHTML = d.cards.map(c=>
    `<div class=card><div class=label>${c.label}</div><div class=val>${c.value}</div><div class=sub>${c.sub}</div></div>`).join('');
  renderTownChart(d.towns||[]);
  const sel = document.getElementById('cat');
  sel.innerHTML = '<option value="">全部</option>' + d.categories.map(c=>`<option>${c}</option>`).join('');
  setStatus('已更新 · '+d.year+' 年');
}

function renderTownChart(towns){
  if(!towns.length){document.getElementById('townChart').innerHTML='（暂无分街镇数据）';return;}
  const max = Math.max(...towns.map(t=>t.产值));
  document.getElementById('townChart').innerHTML = towns.map(t=>{
    const w = max? (t.产值/max*100):0;
    return `<div class=row><div class=name>${t.街镇}</div>
      <div class=track><div class=fill style="width:${w}%"></div></div>
      <div class=num>${t.产值} 亿</div></div>`;
  }).join('');
}

async function loadTable(){
  const cat = document.getElementById('cat').value;
  const u = '/api/indicators?year='+Y()+(cat?('&category='+encodeURIComponent(cat)):'');
  const r = await fetch(u); const rows = await r.json();
  const tb = document.querySelector('#tbl tbody');
  if(!rows.length){tb.innerHTML='<tr><td colspan=7>无数据</td></tr>';return;}
  tb.innerHTML = rows.map(r=>`<tr>
    <td>${r.year}</td><td>${r.category}</td><td>${r.indicator}</td>
    <td>${r.dimension}</td><td>${r.value}</td><td>${r.unit}</td><td>${r.note||''}</td>
  </tr>`).join('');
}

async function ask(cloud=false){
  const t = document.getElementById('q').value; if(!t) return;
  const el = document.getElementById('out'); el.textContent='分析中…';
  const u = '/api/ask?text='+encodeURIComponent(t)+(cloud?('&cloud=1'):'');
  try{
    const r = await fetch(u); const d = await r.json();
    el.textContent = JSON.stringify(d, null, 2);
  }catch(e){ el.textContent='请求失败：'+e; }
}

async function loadBulletin(){
  const r = await fetch('/api/report?year='+Y());
  document.getElementById('bulletin').textContent = await r.text();
}
async function aiInterpret(){
  const el = document.getElementById('ai'); el.textContent='解读中…';
  const r = await fetch('/api/report?year='+Y()+'&cloud=1');
  el.textContent = await r.text();
}

loadAll();
</script></body></html>
"""


@app.route("/")
def index() -> str:
    return PAGE


@app.route("/api/overview")
def api_overview():
    year = int(request.args.get("year", 2024))
    return jsonify(_overview(year))


@app.route("/api/indicators")
def api_indicators():
    year = request.args.get("year", type=int)
    category = request.args.get("category")
    rows = query_indicators(year=year, category=category or None)
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
