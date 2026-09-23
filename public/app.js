/* ============================================
   亚太统计分析系统 · 前端逻辑
   对接真实 Flask API（/api/overview, /api/ask, /api/indicators,
   /api/custom, /api/report, /api/collect, /api/stats）
   注意：/api/db、/api/reseed、/api/kv-status、/api/collect 是**管理端点**，
   生产环境需令牌（无令牌一律 403），前端展示类数据一律走公开端点 /api/stats。
   数据全部来自公开官方数据源（世界银行 Open Data / 国家统计局 / 海关总署）。
   ============================================ */

const API = '';

/* 全局状态：年份 + 维度（地区/经济体） */
const STATE = {
  year: '2024',
  dimension: '亚太'
};

/* 维度 -> 世界银行 ISO/地区码（用于在线采集） */
const DIM_ISO = {
  '亚太': 'EAS', '亚太(发展中)': 'EAP', '中国': 'CHN', '日本': 'JPN',
  '韩国': 'KOR', '印度': 'IND', '印度尼西亚': 'IDN', '泰国': 'THA',
  '越南': 'VNM', '马来西亚': 'MYS', '菲律宾': 'PHL',   '新加坡': 'SGP'
};

function isZh() { return window.CUR_LANG === 'zh'; }
function enc(s) { return encodeURIComponent(s == null ? '' : String(s)); }

/* 数据接口统一带上界面语言：服务端据此本地化专业 / 指标 / 维度 / 单位标识符，
   前端不再对数据做二次词条替换（i18n.js 只负责静态 UI 文案）。 */
function langQ() { return 'lang=' + (isZh() ? 'zh' : 'en'); }

/* ═══════ 分享链接 + 导出 CSV ═══════
   分享链接：把当前筛选状态（年份 / 维度 / 语言，图表 Tab 下再加指标）同步到
   URL 的查询串，复制给其他人打开即可还原同一视图（出海场景：海外用户无需读中文）。
   导出 CSV：复用服务端 /api/export.csv，按当前语言与筛选条件下载。 */
function initShareState() {
  try {
    var p = new URLSearchParams(window.location.search);
    var year = p.get('year');
    if (year && /^\d{4}$/.test(year)) STATE.year = year;
    var dim = p.get('dimension');
    if (dim) STATE.dimension = dim;          // 规范键或英文标签均可，服务端 key_of 会归一
    var lang = p.get('lang');
    if (lang === 'zh' || lang === 'en') window.CUR_LANG = lang;
    var ind = p.get('indicator');
    if (ind) window._pendingChartIndicator = ind;   // 图表初始化后再带入
    var dims = p.get('dims');
    if (dims) window._pendingChartDims = dims.split(',').filter(Boolean);   // 图表维度多选同理
  } catch (e) { /* 解析失败不影响主流程 */ }
}

/* 用 history.replaceState 同步当前状态到地址栏（不产生历史记录，刷新/分享即用） */
function updateShareUrl() {
  try {
    var p = new URLSearchParams();
    p.set('year', STATE.year);
    p.set('dimension', STATE.dimension);
    p.set('lang', window.CUR_LANG === 'zh' ? 'zh' : 'en');
    var pc = document.getElementById('panel-charts');
    if (pc && pc.classList.contains('active') && CHART && CHART.currentKey) {
      p.set('indicator', CHART.currentKey);
      if (CHART.selDims && CHART.selDims.length) p.set('dims', CHART.selDims.join(','));
    }
    var qs = p.toString();
    history.replaceState(null, '', qs ? '?' + qs : window.location.pathname);
  } catch (e) { /* 不支持时静默 */ }
}

function copyShareLink() {
  updateShareUrl();
  var url = window.location.href;
  var ok = function () { showToast(tr('分享链接已复制'), 'success'); };
  var fail = function () { showToast(tr('复制失败，请手动复制地址栏'), 'error'); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(ok, function () { legacyCopy(url); ok(); });
  } else {
    legacyCopy(url); ok();
  }
}

function legacyCopy(text) {
  try {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  } catch (e) { /* 忽略 */ }
}

/* 触发浏览器下载一个接口返回的 CSV（服务端已带 Content-Disposition: attachment） */
function exportCsv(url) {
  var a = document.createElement('a');
  a.href = url;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/* 指标总表：按当前年份 / 维度 / 专业 / 关键词导出 */
function exportIndicatorsCsv() {
  var cat = (document.getElementById('indCat') || {}).value || '';
  var q = (document.getElementById('indSearch') || {}).value || '';
  var u = API + '/api/export.csv?year=' + enc(STATE.year)
    + '&dimension=' + enc(STATE.dimension)
    + (cat ? '&category=' + enc(cat) : '')
    + (q ? '&q=' + enc(q.trim()) : '')
    + '&' + langQ();
  exportCsv(u);
  showToast(tr('已导出 CSV'), 'success');
}

/* 图表：导出当前选中指标的完整跨年 × 全经济体序列（不传 year/dimension = 全部） */
function exportChartCsv() {
  if (!CHART.currentKey) { showToast(tr('请先选择指标'), 'error'); return; }
  var u = API + '/api/export.csv?indicator=' + enc(CHART.currentKey) + '&' + langQ();
  exportCsv(u);
  showToast(tr('已导出 CSV'), 'success');
}

/* ───── 页面入口 ───── */
(function init() {
  initShareState();   // 从 URL 还原分享状态（年份/维度/语言/图表指标）后再取数
  document.querySelectorAll('.wb-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.wb-tab').forEach(b => {
        const on = b === btn;
        b.classList.toggle('active', on);
        b.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      document.querySelectorAll('.wb-panel').forEach(p => p.classList.remove('active'));
      const panel = document.getElementById('panel-' + btn.dataset.tab);
      if (!panel) return;
      panel.classList.add('active');
      if (btn.dataset.tab === 'indicators') loadIndicators();
      if (btn.dataset.tab === 'charts') initCharts();
    });
  });

  /* WAI-ARIA tablist 键盘导航：ArrowLeft/Right + Home/End，roving tabindex */
  const tablist = document.querySelector('[role="tablist"]');
  if (tablist) {
    tablist.addEventListener('keydown', (e) => {
      const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
      if (!tabs.length) return;
      const idx = tabs.indexOf(e.target);
      if (idx < 0) return;
      let next = -1;
      if (e.key === 'ArrowRight') next = (idx + 1) % tabs.length;
      else if (e.key === 'ArrowLeft') next = (idx - 1 + tabs.length) % tabs.length;
      else if (e.key === 'Home') next = 0;
      else if (e.key === 'End') next = tabs.length - 1;
      if (next < 0) return;
      e.preventDefault();
      tabs.forEach((t, i) => t.setAttribute('tabindex', i === next ? '0' : '-1'));
      tabs[next].focus();
      tabs[next].click();
    });
    /* 初始 roving tabindex：只有 active tab 可 Tab 到 */
    tablist.querySelectorAll('[role="tab"]').forEach((t, i) => {
      t.setAttribute('tabindex', i === 0 ? '0' : '-1');
    });
  }
  loadOverview();
  loadCustomList();
  loadDbStats();
  loadInsights();
  /* 主题预设 / 全局快捷键 / 命令面板：增强能力，单独 try 避免影响主流程 */
  try { initTheme(); initShortcuts(); initPalette(); } catch (e) { /* 忽略 */ }
})();

/* ───── 下拉框填充（统一入口，保证语言切换后可重填） ───── */
function fillSelect(id, values, current, labelFn) {
  const sel = document.getElementById(id);
  if (!sel) return;
  const prev = current != null ? String(current) : sel.value;
  sel.innerHTML = values.map(v => {
    const val = String(v);
    const label = labelFn ? labelFn(val) : val;
    return '<option value="' + a(val) + '">' + h(label) + '</option>';
  }).join('');
  if (values.some(v => String(v) === prev)) sel.value = prev;
  return sel.value;
}

/* 用服务端返回的 {label, key, slug} 选项填充下拉框。
   value 用**中文规范键**（`key`）：它是内部连接键，跨语言稳定，
   不会因为界面语言变化而让已选中的项失效；展示文案用 `label`（已按 lang 本地化）。 */
function fillSelectOptions(id, options, current) {
  const sel = document.getElementById(id);
  if (!sel) return '';
  const prev = current != null ? String(current) : sel.value;
  const opts = (options || []).filter(o => o && (o.key || o.slug));
  sel.innerHTML = opts.map(o => {
    const val = o.key || o.slug;
    return '<option value="' + a(val) + '" data-slug="' + a(o.slug || '') + '">' + h(o.label || val) + '</option>';
  }).join('');
  if (opts.some(o => String(o.key || o.slug) === prev)) sel.value = prev;
  return sel.value;
}

/* ───── 年份 / 维度切换 ───── */
function syncYear(y) {
  STATE.year = String(y);
  const gy = document.getElementById('globalYear');
  if (gy) gy.value = STATE.year;
  loadOverview();
  loadIndicators();
  loadInsights();
  updateShareUrl();
  showToast(tr('年份已切换至') + ' ' + STATE.year + (isZh() ? '年' : ''), 'success');
}

function syncDimension(d) {
  STATE.dimension = d;
  const gd = document.getElementById('globalDimension');
  if (gd) gd.value = d;
  loadOverview();
  loadIndicators();
  loadInsights();
  updateShareUrl();
  showToast(tr('维度已切换至') + ' ' + tr(d), 'success');
}

/* ───── Tab 切换（来自快捷按钮） ───── */
function switchTab(tabId) {
  document.querySelectorAll('.wb-tab').forEach(b => {
    const on = b.dataset.tab === tabId;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  document.querySelectorAll('.wb-panel').forEach(p => p.classList.toggle('active', p.id === 'panel-' + tabId));
  if (tabId === 'indicators') loadIndicators();
  if (tabId === 'charts') initCharts();
  updateShareUrl();
}

/* ───── 快捷查询（中英文按当前语言取词） ───── */
function pickQ(el) {
  if (isZh()) return el.dataset.qZh || el.dataset.qEn || '';
  return el.dataset.qEn || el.dataset.qZh || '';
}
function fillQuery(text) {
  switchTab('nlq');
  const i = document.getElementById('nlqInput');
  if (!i) return;
  i.value = text;
  i.focus();
}
function fillQueryI18n(el) { fillQuery(pickQ(el)); }

/* ═══════ 关键指标卡片 ═══════ */
/* 首屏骨架：数据到达前先占位，避免「白屏 → 内容突现」的跳动 */
function metricsSkeleton(n) {
  var one = '<div class="metric-card" aria-hidden="true">'
    + '<div class="skeleton skeleton-line" style="width:52%"></div>'
    + '<div class="skeleton skeleton-line" style="width:72%;height:22px;margin:10px 0"></div>'
    + '<div class="skeleton skeleton-line" style="width:40%"></div>'
    + '</div>';
  return new Array(n || 8).fill(one).join('');
}

async function loadOverview() {
  const grid = document.getElementById('metricsGrid');
  if (!grid) return;
  if (!grid.querySelector('.metric-card')) {
    grid.setAttribute('aria-busy', 'true');
    grid.innerHTML = metricsSkeleton(8);
  }
  try {
    const r = await fetch(API + '/api/overview?year=' + enc(STATE.year) + '&dimension=' + enc(STATE.dimension) + '&' + langQ());
    const d = await r.json();
    if (d.dimension) STATE.dimension = d.dimension;
    if (d.year) STATE.year = String(d.year);

    updateShareUrl();   // 状态已就绪，同步一次分享链接

    // 下拉框用服务端返回的 {label,key,slug} 选项：value 是规范键，label 已按 lang 本地化
    fillSelectOptions('globalDimension', d.dimension_options, STATE.dimension);
    fillSelect('globalYear', d.years || [], STATE.year, v => v + (isZh() ? '年' : ''));
    if (d.category_options) {
      var curCat = (document.getElementById('indCat') || {}).value || '';
      var sel = document.getElementById('indCat');
      if (sel) {
        sel.innerHTML = '<option value="">' + h(tr('全部专业')) + '</option>'
          + d.category_options.map(function (o) {
              return '<option value="' + a(o.key || o.slug) + '">' + h(o.label) + '</option>';
            }).join('');
        if (Array.from(sel.options).some(function (o) { return o.value === curCat; })) sel.value = curCat;
      }
    }

    const sy = document.getElementById('subtitleYear');
    if (sy) sy.textContent = STATE.year;

    // 命令面板的「切换年份 / 切换经济体」直接复用最近一次概览结果，不另建接口
    window._years = d.years || [];
    window._dimOptions = d.dimension_options || [];

    grid.removeAttribute('aria-busy');
    // 卡片字段全部来自服务端本地化结果，前端不再做数据词条替换
    if (!(d.cards || []).length) {
      /* 空视图不能是死路：给出切回亚太聚合口径的出口（旧分享链接 / 无数据维度）。
         判重用 dimension_key——STATE.dimension 存的是本地化标签，跨语言不可靠。 */
      var back = (d.dimension_key || STATE.dimension) !== '亚太'
        ? ' <button type="button" class="btn btn-secondary" onclick="syncDimension(\'亚太\')">'
          + h(tr('切换到亚太')) + '</button>'
        : '';
      grid.innerHTML = '<div class="metric-card" style="grid-column:1/-1">'
        + emptyState('🗺️', tr('该维度暂无数据')) + back + '</div>';
      return;
    }
    grid.innerHTML = (d.cards || []).map(c => `
      <div class="metric-card">
        <div class="metric-header">
          <span class="metric-label">${h(c.label)}</span>
          <span class="metric-tag">${h(c.dimension || '')}</span>
        </div>
        <div class="metric-value" title="${a(c.value)}">${h(compactNum(c.value))}<span class="metric-unit">${h(c.unit || '')}</span></div>
        <div class="metric-footer">
          ${c.yoy ? `<span class="metric-change">${h(tr('同比'))} ${h(c.yoy)}</span>` : ''}
          <span class="metric-spark" aria-hidden="true"></span>
        </div>
        <div class="metric-src" title="${a(c.note || '')}">${h(c.note || '')}</div>
      </div>`).join('');
    loadSparks(d.dimension_key || STATE.dimension, d.cards || []);
  } catch (e) {
    grid.removeAttribute('aria-busy');
    grid.innerHTML = '<div class="metric-card" style="grid-column:1/-1">' + emptyState('⚠️', tr('加载失败')) + '</div>';
  }
}

/* ═══════ 数据洞察 ═══════
   数字全部来自服务端 /api/insights（本地公开数据实时计算），前端只负责排版；
   同比口径 = 同维度、同指标、相邻两年，可在指标总表按同样条件逐条复算。 */
function insightsSkeleton() {
  var one = '<div class="insight-card" aria-hidden="true">'
    + '<div class="skeleton skeleton-line" style="width:46%"></div>'
    + '<div class="skeleton skeleton-line" style="width:80%"></div>'
    + '<div class="skeleton skeleton-line" style="width:64%"></div></div>';
  return new Array(3).fill(one).join('');
}

async function loadInsights() {
  var grid = document.getElementById('insightsGrid');
  if (!grid) return;
  if (!grid.querySelector('.insight-card')) {
    grid.setAttribute('aria-busy', 'true');
    grid.innerHTML = insightsSkeleton();
  }
  try {
    var r = await fetch(API + '/api/insights?year=' + enc(STATE.year)
      + '&dimension=' + enc(STATE.dimension) + '&' + langQ());
    var d = await r.json();
    grid.removeAttribute('aria-busy');
    grid.innerHTML = renderInsights(d);
  } catch (e) {
    grid.removeAttribute('aria-busy');
    grid.innerHTML = '<div class="insight-card" style="grid-column:1/-1">'
      + emptyState('⚠️', tr('加载失败')) + '</div>';
  }
}

function insightCard(icon, title, sub, body) {
  return '<div class="insight-card">'
    + '<div class="insight-head"><span class="insight-title">' + h(icon) + ' ' + h(title) + '</span>'
    + (sub ? '<span class="insight-sub">' + h(sub) + '</span>' : '') + '</div>'
    + body + '</div>';
}

/* 变化方向：上行绿、下行红；箭头与正负号一起给，色盲用户也能读 */
function insightDelta(pct) {
  var v = Number(pct);
  if (!isFinite(v)) return { cls: '', arrow: '—', abs: '—' };
  return {
    cls: v >= 0 ? 'up' : 'down',
    arrow: v >= 0 ? '▲' : '▼',
    abs: Math.abs(v).toFixed(1) + '%'
  };
}

function renderInsights(d) {
  if (!d || typeof d !== 'object') return '';
  var years = (d.year || STATE.year) + ' vs ' + (d.prev_year || (Number(STATE.year) - 1));

  /* 卡 1：同比变化最大的指标 */
  var movers = d.movers || [];
  var mBody = movers.length
    ? movers.map(function (m) {
        var k = insightDelta(m.change_pct);
        return '<div class="insight-row"><span class="insight-name" title="' + a(m.indicator) + '">'
          + h(m.indicator) + '</span><span class="insight-val ' + k.cls + '">' + k.arrow + ' ' + h(k.abs) + '</span></div>';
      }).join('')
    : emptyState('📈', tr('暂无洞察'));
  var c1 = insightCard('📈', tr('同比变化最大'), tr('较上年'), mBody);

  /* 卡 2：名次变动最大的经济体（指标由服务端选覆盖最广的那个） */
  var shifts = d.rank_shifts || [];
  var rTitle = tr('名次变动') + (d.rank_indicator ? ' · ' + d.rank_indicator : '');
  var rBody = shifts.length
    ? shifts.map(function (s) {
        var cls = s.delta > 0 ? 'up' : (s.delta < 0 ? 'down' : '');
        var arrow = s.delta > 0 ? '▲' : (s.delta < 0 ? '▼' : '—');
        return '<div class="insight-row"><span class="insight-name">' + h(s.dimension) + '</span>'
          + '<span class="insight-rank">' + s.rank_prev + ' → ' + s.rank_now + '</span>'
          + '<span class="insight-val ' + cls + '">' + arrow + ' ' + Math.abs(s.delta) + '</span></div>';
      }).join('')
    : emptyState('🏅', tr('暂无洞察'));
  var c2 = insightCard('🏅', rTitle, tr('名次'), rBody);

  /* 卡 3：覆盖规模（计数本身就是洞察：数据到底有多全） */
  var cov = d.coverage || {};
  var chips = [
    { label: tr('指标行'), value: cov.rows },
    { label: tr('覆盖经济体'), value: cov.economies },
    { label: tr('可比指标'), value: cov.comparable }
  ].map(function (x) {
    return '<div class="insight-chip">' + h(x.label) + '<b>' + h(x.value == null ? '—' : x.value) + '</b></div>';
  }).join('');
  var c3 = insightCard('🗄️', tr('覆盖规模'), years, '<div class="insight-chips">' + chips + '</div>');
  return c1 + c2 + c3;
}

/* ═══════ 智能查询 ═══════ */
async function runAnalyze() {
  var input = document.getElementById('nlqInput').value.trim();
  if (!input) { showToast(tr('请先输入查询问题'), 'error'); return; }
  window._lastQuery = input;
  var useCloud = !!(document.getElementById('nlqCloud') || {}).checked;
  var btn = document.getElementById('btnAnalyze');
  btn.classList.add('loading');
  btn.disabled = true;
  var el = document.getElementById('nlqResult');
  el.setAttribute('aria-busy', 'true');
  el.innerHTML = '<div class="skeleton skeleton-line" style="width:60%"></div><div class="skeleton skeleton-line" style="width:40%"></div>';
  if (useCloud) el.innerHTML += '<div class="cloud-note">' + h(tr('AI 云端解读')) + ' · InfiniSynapse …</div>';
  try {
    var u = API + '/api/ask?text=' + enc(input) + '&lang=' + (isZh() ? 'zh' : 'en')
      + '&dimension=' + enc(STATE.dimension) + (useCloud ? '&cloud=1' : '');
    var r = await fetch(u);
    var d = await r.json();
    var html = '';
    var ai = pick(d, 'AI 解读', 'ai_interpretation');
    if (ai) {
      html += '<div class="ai-card"><div class="ai-head">🤖 ' + tr('AI 云端解读') + '</div>'
        + '<div class="ai-body">' + mdToHtml(ai) + '</div>'
        + (d.task_id ? '<div class="ai-foot">' + tr('task_id') + ': ' + h(d.task_id) + '</div>' : '')
        + '</div>';
    }
    html += renderAsk(d);
    var ref = pick(d, '知识库参考', 'kb_reference');
    if (ref) html += '<div class="kb-ref"><b>' + tr('知识库参考') + '</b>' + mdToHtml(ref) + '</div>';
    el.innerHTML = html || '<div class="rk">' + tr('无结果') + '</div>';
    showToast(tr('分析完成'), 'success');
  } catch (e) {
    el.innerHTML = '<div style="color:var(--red-500)">' + tr('请求失败') + ': ' + h(e) + '</div>';
    showToast(tr('请求失败'), 'error');
  } finally {
    el.removeAttribute('aria-busy');
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

/* 结果对象 -> 可读卡片 / 表格（结构键中英两套，取值时都要认） */
function pick(d, zhKey, enKey) {
  if (!d) return undefined;
  if (d[zhKey] !== undefined) return d[zhKey];
  return d[enKey];
}

function renderAsk(d) {
  if (!d || typeof d !== 'object') return tval(d);
  var html = '';
  var sep = isZh() ? '：' : ': ';
  var jsep = isZh() ? '； ' : '; ';
  var lsep = isZh() ? '、' : ', ';
  for (var k in d) {
    if (k === '知识库参考' || k === 'AI 解读' || k === 'kb_reference' || k === 'ai_interpretation') continue;
    var v = d[k];
    var kk = tr(k);
    if (Array.isArray(v) && v.length) {
      html += '<div class="rk"><b>' + h(kk) + '</b>';
      if (typeof v[0] === 'object') {
        var keys = Object.keys(v[0]);
        html += '<table class="rkt"><thead><tr>' + keys.map(c => '<th>' + h(tr(c)) + '</th>').join('') + '</tr></thead><tbody>'
          + v.map(row => '<tr>' + keys.map(c => '<td>' + h(tval(row[c])) + '</td>').join('') + '</tr>').join('')
          + '</tbody></table>';
      } else {
        html += '<div>' + v.map(x => h(tval(x))).join(lsep) + '</div>';
      }
      html += '</div>';
    } else if (v && typeof v === 'object') {
      html += '<div class="rk"><b>' + h(kk) + '</b><div class="rki">'
        + Object.keys(v).map(function (key) {
            return h(tr(key)) + sep + h(tval(v[key]));
          }).join(jsep)
        + '</div></div>';
    } else {
      html += '<div class="rk"><b>' + h(kk) + '</b>' + sep + '<span>' + h(tval(v)) + '</span></div>';
    }
  }
  return html;
}

/* ═══════ 指标总表 ═══════ */
async function loadIndicators() {
  var cat = (document.getElementById('indCat') || {}).value || '';
  var q = (document.getElementById('indSearch') || {}).value || '';
  var u = API + '/api/indicators?year=' + enc(STATE.year)
    + '&dimension=' + enc(STATE.dimension)
    + (cat ? '&category=' + enc(cat) : '')
    + (q ? '&q=' + enc(q.trim()) : '')
    + '&' + langQ();
  var tb = document.querySelector('#indTable tbody');
  if (!tb) return;
  /* 二次查询也给加载态：骨架 + aria-busy，避免「点了没反应」 */
  var indTable = document.getElementById('indTable');
  if (indTable) indTable.setAttribute('aria-busy', 'true');
  tb.innerHTML = '<tr aria-hidden="true"><td colspan="7">'
    + '<div class="skeleton skeleton-line" style="width:70%"></div>'
    + '<div class="skeleton skeleton-line" style="width:50%"></div></td></tr>';
  try {
    var r = await fetch(u);
    var rows = await r.json();
    var cnt = document.getElementById('indCount');
    if (cnt) cnt.textContent = rows.length ? rows.length + (isZh() ? ' 条' : ' rows') : '';
    if (!rows.length) {
      tb.innerHTML = '<tr><td colspan="7">' + emptyState('📭', tr('无可展示数据')) + '</td></tr>';
      if (indTable) indTable.removeAttribute('aria-busy');
      return;
    }
    // 数据字段（indicator/category/dimension/unit/note）已由服务端按 lang 本地化；
    // 单选钮的 data-* 存**规范键**（*_key），供新增自定义分析时回填稳定标识。
    tb.innerHTML = rows.map(function (r) { return '<tr>'
      + '<td><input type=radio name=selrow class=selrow data-c="' + a(r.category_key || r.category) + '" data-i="' + a(r.indicator_key || r.indicator) + '" data-d="' + a(r.dimension_key || r.dimension) + '" onclick="toggleCb(this,event)"></td>'
      + '<td class="ind-name" title="' + a(r.note || '') + '">' + h(r.indicator) + '</td>'
      + '<td><span class="tag tag-blue">' + h(r.category) + '</span></td>'
      + '<td>' + h(r.dimension) + '</td>'
      + '<td class="num">' + (r.value !== null && r.value !== undefined ? Number(r.value).toLocaleString() : '—') + '</td>'
      + '<td>' + h(r.unit || '') + '</td>'
      + '<td class="note-cell" style="color:var(--gray-500)" title="' + a(r.note || '') + '">' + h(r.note || '') + '</td>'
      + '</tr>'; }).join('');
    if (indTable) indTable.removeAttribute('aria-busy');
  } catch (e) {
    tb.innerHTML = '<tr><td colspan="7" style="color:var(--red-500)">' + tr('加载失败') + '</td></tr>';
    if (indTable) indTable.removeAttribute('aria-busy');
  }
}

function toggleCb(el, ev) {
  ev.stopPropagation();
  document.querySelectorAll('#indTable .selrow').forEach(function (r) { r.checked = false; });
  el.checked = true;
}

function createFromSelected() {
  var sel = document.querySelector('#indTable .selrow:checked');
  if (!sel) { showToast(tr('请先选中一个指标'), 'error'); return; }
  switchTab('custom');
  openAddCustom();
  var vr = document.getElementById('varRows');
  vr.innerHTML = '';
  addVarRow();
  var row = vr.lastElementChild;
  row.querySelector('.vname').value = 'x';
  row.querySelector('.vcat').value = sel.dataset.c || '';
  row.querySelector('.vind').value = sel.dataset.i || '';
  row.querySelector('.vdim').value = sel.dataset.d || '';
  document.getElementById('caddMsg').textContent = tr('已带入所选指标，填好名称与公式即可保存');
}

/* ═══════ 自定义分析 ═══════ */
async function loadCustomList() {
  try {
    var r = await fetch(API + '/api/custom?' + langQ());
    var list = await r.json();
    var sel = document.getElementById('customSelect');
    if (!sel) return;
    // value 用规范名（name_key）：跨语言稳定，切换界面语言后已选项仍然有效
    sel.innerHTML = '<option value="">' + tr('选择已有分析…') + '</option>'
      + list.map(function (a2) {
          var val = a2.name_key || a2.name;
          return '<option value="' + a(val) + '">' + h(a2.name)
            + (a2.description ? ' — ' + h(a2.description) : '') + '</option>';
        }).join('');
  } catch (e) { /* 忽略 */ }
}

async function runCustom() {
  var sel = document.getElementById('customSelect');
  if (!sel || !sel.value) { showToast(tr('请先选择一个分析'), 'error'); return; }
  window._lastCustom = sel.value;
  var btn = document.getElementById('btnRunCustom');
  btn.classList.add('loading');
  var el = document.getElementById('customResult');
  el.setAttribute('aria-busy', 'true');
  try {
    var r = await fetch(API + '/api/custom?name=' + enc(sel.value) + '&year=' + enc(STATE.year) + '&' + langQ());
    var d = await r.json();
    if (d.error) {
      el.innerHTML = '<div class="rk" style="color:var(--red-500)">' + h(d.error) + '</div>';
      return;
    }
    el.innerHTML = '<div class="custom-card">'
      + '<div class="custom-value" title="' + a(d.value) + '">' + (d.value !== undefined && d.value !== null ? compactNum(d.value) : '—')
      + (d.unit ? ' <span class="custom-unit">' + h(tr(d.unit)) + '</span>' : '') + '</div>'
      + (d.yoy !== undefined ? '<div class="custom-yoy ' + (d.yoy >= 0 ? 'up' : 'down') + '">'
          + (d.yoy >= 0 ? '▲' : '▼') + ' ' + tr('同比') + ' ' + d.yoy + '%</div>' : '')
      + (d.expr ? '<div class="custom-expr">' + tr('公式：') + h(d.expr) + '</div>' : '')
      + '</div>';
    showToast(tr('分析完成'), 'success');
  } catch (e) {
    el.innerHTML = '<div style="color:var(--red-500)">' + tr('请求失败') + '</div>';
  } finally {
    el.removeAttribute('aria-busy');
    btn.classList.remove('loading');
  }
}

function openAddCustom() {
  document.getElementById('customAdd').style.display = 'block';
  document.getElementById('customResult').innerHTML = '';
}
function closeAddCustom() { document.getElementById('customAdd').style.display = 'none'; }

function addVarRow() {
  var tpl = document.getElementById('varTpl').content.cloneNode(true);
  document.getElementById('varRows').appendChild(tpl);
  // 新增行的 placeholder 来自模板（中文），需按当前语言重新应用一次
  if (typeof window.applyLang === 'function') window.applyLang(window.CUR_LANG);
}
function removeVarRow(btn) { var row = btn.closest('.var-row'); if (row) row.remove(); }

function fillExpr(kind) {
  var vars = [].map.call(document.querySelectorAll('#varRows .vname'), function (i) { return i.value.trim(); }).filter(Boolean);
  var x = vars[0] || 'x', y = vars[1] || 'y';
  var map = { share: x + ' / ' + y + ' * 100', diff: x + ' - ' + y, ratio: x + ' / ' + y, sum: x + ' + ' + y };
  document.getElementById('customExpr').value = map[kind] || '';
}

async function saveCustom() {
  var name = document.getElementById('customName').value.trim();
  var expr = document.getElementById('customExpr').value.trim();
  if (!name || !expr) { showToast(tr('名称和表达式必填'), 'error'); return; }
  var vars = {};
  var valid = true;
  document.querySelectorAll('#varRows .var-row').forEach(function (row) {
    var vn = row.querySelector('.vname').value.trim();
    var vc = row.querySelector('.vcat').value.trim();
    var vi = row.querySelector('.vind').value.trim();
    if (!vn || !vc || !vi) { valid = false; return; }
    vars[vn] = [vc, vi, row.querySelector('.vdim').value.trim() || STATE.dimension];
  });
  if (!valid || Object.keys(vars).length === 0) {
    showToast(tr('请至少填一个有效变量（名称/专业/指标）'), 'error');
    return;
  }
  var body = {
    name: name, expr: expr,
    name_en: (document.getElementById('customNameEn') || {}).value ? document.getElementById('customNameEn').value.trim() : '',
    unit: document.getElementById('customUnit').value.trim(),
    description: document.getElementById('customDesc').value.trim(),
    description_en: (document.getElementById('customDescEn') || {}).value ? document.getElementById('customDescEn').value.trim() : '',
    compare: document.getElementById('customCmp').checked,
    variables: vars
  };
  try {
    var r = await fetch(API + '/api/custom?' + langQ(), {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    });
    var d = await r.json();
    if (d.ok) {
      showToast(isZh() ? '已保存「' + name + '」' : 'Saved "' + name + '"', 'success');
      closeAddCustom();
      loadCustomList();
    } else {
      showToast(d.error || tr('保存失败'), 'error');
    }
  } catch (e) {
    showToast(tr('保存失败') + ': ' + e, 'error');
  }
}

/* ═══════ 统计公报 ═══════ */
async function loadBulletin() {
  var out = document.getElementById('bulletinOut');
  if (!out) return;
  var btn = document.getElementById('btnBulletin');
  var useCloud = !!(document.getElementById('bulletinCloud') || {}).checked;
  out.setAttribute('aria-busy', 'true');
  btn.classList.add('loading');
  btn.disabled = true;
  out.textContent = tr('正在生成…');
  try {
    // 取结构化数据，用与页面同一份 i18n 字典渲染 —— 中英文都不会漏译
    var u = API + '/api/report?format=json&year=' + enc(STATE.year)
      + '&dimension=' + enc(STATE.dimension)
      + '&lang=' + (isZh() ? 'zh' : 'en') + (useCloud ? '&cloud=1' : '');
    var r = await fetch(u);
    var d = await r.json();
    window._lastBulletin = d;
    out.innerHTML = renderBulletin(d);
  } catch (e) {
    out.textContent = tr('请求失败') + ': ' + e;
  } finally {
    out.removeAttribute('aria-busy');
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

function renderBulletin(d) {
  var zh = isZh();
  var html = '';
  // 公报的结构化字段已由服务端按 lang 本地化，这里不再做词条替换
  html += '<div class="bul-title">' + h(d.dimension) + ' · '
    + (zh ? '国民经济和社会发展统计公报（摘要）' : 'Economic and Social Development Statistical Bulletin (Summary)')
    + ' — ' + h(d.year) + (zh ? '年' : '') + '</div>';
  html += '<div class="bul-src">' + (zh
    ? '数据来源：世界银行 Open Data · 国家统计局 · 海关总署（均为公开数据）'
    : 'Sources: World Bank Open Data · National Bureau of Statistics · General Administration of Customs (all public)')
    + '</div>';
  (d.sections || []).forEach(function (sec) {
    html += '<div class="bul-sec">' + h(sec.category) + '</div>';
    (sec.rows || []).forEach(function (row) {
      html += '<div class="bul-row">'
        + '<span class="bul-ind">' + h(row.indicator) + '</span>'
        + '<span class="bul-val">' + h(row.value)
        + (row.unit === '%' ? '%' : (row.unit ? ' ' + h(row.unit) : '')) + '</span>'
        + (row.yoy ? '<span class="bul-yoy">' + h(tr('同比')) + ' ' + h(row.yoy) + '</span>' : '')
        + '</div>';
    });
  });
  if (d.ai) {
    html += '<div class="ai-card"><div class="ai-head">🤖 ' + tr('AI 云端解读') + '</div>'
      + '<div class="ai-body">' + mdToHtml(d.ai) + '</div></div>';
  } else if (d.ai_note) {
    html += '<div class="ai-note">' + h(d.ai_note) + '</div>';
  }
  if ((d.knowledge || []).length) {
    html += '<div class="bul-kb"><b>' + tr('知识库参考') + '</b>';
    d.knowledge.forEach(function (k) {
      html += '<div class="bul-kb-item"><span class="bul-kb-t">' + h(k.title) + '</span>'
        + '<span class="bul-kb-c">' + h(k.content) + '</span></div>';
    });
    html += '</div>';
  }
  return html;
}

/* ═══════ 公开数据采集 ═══════ */
async function collectNow() {
  var src = (document.getElementById('collectSource') || {}).value || 'worldbank';
  var ind = (document.getElementById('collectInd') || {}).value.trim();
  if (!ind) { showToast(tr('请先输入要采集的指标'), 'error'); return; }
  var btn = document.getElementById('btnCollect');
  btn.classList.add('loading');
  btn.disabled = true;
  showToast(tr('开始采集公开数据…'), 'success');
  try {
    var r = await fetch(API + '/api/collect', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source: src, year: Number(STATE.year),
        country: DIM_ISO[STATE.dimension] || undefined,
        indicators: ind
      })
    });
    var d = await r.json();
    if (r.status === 403) {
      /* 管理端点在生产环境被禁用（无持久盘，抓取也无处落库）→ 给明确提示而非静默失败 */
      showToast(tr('线上版本已关闭实时采集（本地运行可用）'), 'error');
      return;
    }
    if (d.ok) {
      showToast(tr('已从公开数据源采集：新增') + ' ' + d.count + ' ' + tr('条记录'), 'success');
      loadOverview();
      loadIndicators();
      loadDbStats();
    } else {
      showToast(tr('采集失败') + ': ' + (d.error || ''), 'error');
    }
  } catch (e) {
    showToast(tr('采集失败') + ': ' + e, 'error');
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

/* ═══════ 数据来源与规模（真实库统计） ═══════ */
/* 用公开的 /api/stats，而非管理端点 /api/db —— 后者线上 403，会让整块显示「—」。 */
async function loadDbStats() {
  try {
    var r = await fetch(API + '/api/stats');
    var db = await r.json();
    setText('dbIndicators', db.indicator_rows);
    setText('dbKnowledge', db.knowledge_rows);
    setText('dbDimensions', db.dimension_count);
    setText('dbYears', (db.years || []).join(' · '));
  } catch (e) { /* 忽略 */ }
}
function setText(id, v) { var el = document.getElementById(id); if (el) el.textContent = v; }

/* ═══════ 工具函数 ═══════ */
function h(s) { return (s == null ? '' : String(s)).replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function a(s) { return (s == null ? '' : String(s)).replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
/* 翻译结果里的「值」：字符串才处理（tr 内部已含组合串替换） */
function tval(v) {
  if (typeof v !== 'string') return v == null ? '—' : v;
  return tr(v);
}
/* 轻量 Markdown -> HTML（只放行列表、粗体、换行，避免注入） */
function mdToHtml(md) {
  var out = h(md || '');
  out = out.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  out = out.replace(/^\s*[-*]\s+/gm, '• ');
  out = out.replace(/\n/g, '<br>');
  return out;
}

/* ═══════ Toast ═══════ */
function showToast(msg, type) {
  var toast = document.getElementById('toast');
  if (!toast) return;
  clearTimeout(window._toastTimer);
  /* 同一条消息重复触发（如切换语言后重放上一次分析）时只续期不重播，避免连弹多条 */
  if (toast.textContent === msg && toast.classList.contains('show')) {
    window._toastTimer = setTimeout(function () { toast.className = 'toast'; }, 2600);
    return;
  }
  toast.textContent = msg;
  toast.className = 'toast show' + (type ? ' ' + type : '');
  window._toastTimer = setTimeout(function () { toast.className = 'toast'; }, 2600);
}

/* 切换语言后刷新依赖接口的动态区域 */
function refreshLang() {
  loadOverview();
  loadIndicators();
  loadDbStats();
  loadInsights();
  var bo = document.getElementById('bulletinOut');
  // 公报内容已由服务端按 lang 本地化，切换语言必须重新取数（缓存的是上一语言的文本）
  if (bo && window._lastBulletin) loadBulletin();
  if (window._lastQuery) {
    var qi = document.getElementById('nlqInput');
    if (qi) { qi.value = window._lastQuery; runAnalyze(); }
  }
  loadCustomList().then(function () {
    if (!window._lastCustom) return;
    var cs = document.getElementById('customSelect');
    if (cs) { cs.value = window._lastCustom; runCustom(); }
  });
  var pc = document.getElementById('panel-charts');
  if (pc && pc.classList.contains('active')) initCharts();
  updateShareUrl();
  // 主题按钮图标之外的文案、快捷键帮助内容随语言重渲染
  themeApply(themeMode());
  var shEl = document.getElementById('shortcuts');
  if (shEl && !shEl.hidden) renderHelp();
}

/* ═══════ 侧边栏卡片折叠 ═══════ */
function toggleSidebarCard(headerEl) {
  var card = headerEl.closest('.side-card');
  card.classList.toggle('collapsed');
}

/* ═══════ 主题：跟随系统 / 浅色 / 深色 ═══════
   app.html 的内联脚本已按 localStorage + 系统偏好提前写好 data-theme（无闪白）；
   本模块管三态循环、持久化、系统偏好变化时跟随，以及头部按钮的图标与文案。 */
const THEME_KEY = 'qu_theme_v1';
const THEME_ORDER = ['auto', 'light', 'dark'];
const THEME_META = {
  auto:  { icon: '🌗', zh: '跟随系统', en: 'Match system', key: '跟随系统' },
  light: { icon: '☀️', zh: '浅色',   en: 'Light',        key: '浅色模式' },
  dark:  { icon: '🌙', zh: '深色',   en: 'Dark',         key: '深色模式' }
};
/* 工作台五个视图的顺序（与 app.html 的 .wb-tab 一致），快捷键 1–5 用它寻址 */
const TAB_IDS = ['nlq', 'indicators', 'custom', 'bulletin', 'charts'];

function themeMode() {
  try {
    var v = localStorage.getItem(THEME_KEY);
    return THEME_ORDER.indexOf(v) >= 0 ? v : 'auto';
  } catch (e) { return 'auto'; }
}

function themeIsDarkSystem() {
  try { return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches); }
  catch (e) { return false; }
}

function themeApply(mode) {
  var meta = THEME_META[mode] || THEME_META.auto;
  var dark = mode === 'auto' ? themeIsDarkSystem() : mode === 'dark';
  var root = document.documentElement;
  if (root) root.setAttribute('data-theme', dark ? 'dark' : 'light');
  var btn = document.getElementById('themeToggle');
  if (btn) {
    btn.textContent = meta.icon;
    var label = '主题：' + meta.zh + ' / Theme: ' + meta.en;
    btn.title = label;
    btn.setAttribute('aria-label', label);
  }
}

function cycleTheme() {
  var next = THEME_ORDER[(THEME_ORDER.indexOf(themeMode()) + 1) % THEME_ORDER.length];
  try { localStorage.setItem(THEME_KEY, next); }
  catch (e) { /* 隐私模式取不到存储时仅本次会话生效 */ }
  themeApply(next);
  showToast(tr('主题已切换') + '：' + tr(THEME_META[next].key), 'success');
}

function initTheme() {
  themeApply(themeMode());
  try {
    var mq = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
    if (!mq) return;
    var onChange = function () { if (themeMode() === 'auto') themeApply('auto'); };
    if (mq.addEventListener) mq.addEventListener('change', onChange);
    else if (mq.addListener) mq.addListener(onChange);   // 旧版 Safari
  } catch (e) { /* 忽略 */ }
}

/* ═══════ 命令面板（Ctrl/⌘+K） ═══════
   零依赖浮层：命令清单由当前真实状态（年份 / 经济体 / 示例问题）动态生成，
   模糊匹配 + 键盘导航，全部复用已有函数，不新增接口。 */
const PAL = { open: false, all: [], view: [], idx: 0, lastFocus: null };

/* 子序列模糊匹配：连续命中加分、起始命中加分；任一字符缺席返回 -1 */
function paletteScore(text, q) {
  if (!q) return 1;
  var t = String(text).toLowerCase(), s = String(q).toLowerCase();
  var ti = 0, score = 0, prev = -2;
  for (var si = 0; si < s.length; si++) {
    var ch = s.charAt(si);
    if (ch === ' ') continue;
    var found = t.indexOf(ch, ti);
    if (found < 0) return -1;
    score += found === prev + 1 ? 3 : 1;
    if (found === 0) score += 2;
    prev = found;
    ti = found + 1;
  }
  return score;
}

function paletteCommands() {
  var cmds = [];
  [
    { id: 'nlq', icon: '💬', key: '智能查询' },
    { id: 'indicators', icon: '📋', key: '指标总表' },
    { id: 'custom', icon: '🧮', key: '自定义分析' },
    { id: 'bulletin', icon: '📄', key: '统计公报' },
    { id: 'charts', icon: '📈', key: '图表' }
  ].forEach(function (t) {
    cmds.push({
      group: tr('视图'), icon: t.icon, label: tr(t.key), keywords: 'view tab ' + t.id,
      hint: String(TAB_IDS.indexOf(t.id) + 1),
      run: function () { switchTab(t.id); }
    });
  });
  (window._years || []).forEach(function (y) {
    y = String(y);
    cmds.push({
      group: tr('切换年份'), icon: '📅', label: y + (isZh() ? '年' : ''),
      hint: y === STATE.year ? '✓' : '', keywords: 'year ' + y,
      run: function () { syncYear(y); }
    });
  });
  (window._dimOptions || []).forEach(function (o) {
    var key = o.key || o.slug;
    if (!key) return;
    cmds.push({
      group: tr('切换经济体'), icon: '🌏', label: o.label || key,
      keywords: 'dimension economy ' + key + ' ' + (o.slug || ''),
      hint: key === STATE.dimension ? '✓' : '',
      run: function () { syncDimension(key); }
    });
  });
  cmds.push({ group: tr('外观'), icon: '🌓', label: tr('切换主题'),
    hint: tr(THEME_META[themeMode()].key), keywords: 'theme dark light auto', run: cycleTheme });
  cmds.push({ group: tr('外观'), icon: '🔤', label: tr('切换语言'),
    hint: isZh() ? '中文 → EN' : 'EN → 中文', keywords: 'language lang', run: function () { toggleLang(); } });
  cmds.push({ group: tr('操作'), icon: '🔗', label: tr('复制分享链接'), keywords: 'share link copy', run: copyShareLink });
  cmds.push({ group: tr('操作'), icon: '⬇️', label: tr('导出指标 CSV'), keywords: 'export csv download', run: exportIndicatorsCsv });
  cmds.push({ group: tr('操作'), icon: '⬇️', label: tr('导出当前指标 CSV'), keywords: 'export csv chart indicator', run: exportChartCsv });
  cmds.push({ group: tr('操作'), icon: '📄', label: tr('生成统计公报'), keywords: 'bulletin report',
    run: function () { switchTab('bulletin'); loadBulletin(); } });
  cmds.push({ group: tr('操作'), icon: '⌨️', label: tr('键盘快捷键'), hint: '?',
    keywords: 'shortcuts help keyboard', run: openShortcuts });
  Array.prototype.slice.call(document.querySelectorAll('.suggestion-chip')).forEach(function (el) {
    var q = pickQ(el);
    if (!q) return;
    cmds.push({ group: tr('示例问题'), icon: '💬', label: q, keywords: 'ask ' + q,
      run: function () { fillQuery(q); runAnalyze(); } });
  });
  return cmds;
}

function openPalette() {
  var el = document.getElementById('palette');
  if (!el) return;
  PAL.lastFocus = document.activeElement;
  el.hidden = false;
  PAL.open = true;
  PAL.all = paletteCommands();
  PAL.idx = 0;
  if (document.body) document.body.style.overflow = 'hidden';
  var input = document.getElementById('paletteInput');
  if (input) input.value = '';
  paletteRender('');
  if (input && input.focus) input.focus();
}

function closePalette() {
  var el = document.getElementById('palette');
  if (el) el.hidden = true;
  PAL.open = false;
  if (document.body) document.body.style.overflow = '';
  if (PAL.lastFocus && PAL.lastFocus.focus) { try { PAL.lastFocus.focus(); } catch (e) { /* 忽略 */ } }
  PAL.lastFocus = null;
}

function paletteRender(q) {
  var list = document.getElementById('paletteList');
  if (!list) return;
  var scored = [];
  PAL.all.forEach(function (c) {
    var s = paletteScore(c.label + ' ' + (c.keywords || ''), q);
    if (s >= 0) scored.push({ c: c, s: s });
  });
  scored.sort(function (a, b) { return b.s - a.s; });
  PAL.view = scored.map(function (x) { return x.c; });
  if (PAL.idx >= PAL.view.length) PAL.idx = 0;
  if (!PAL.view.length) {
    list.innerHTML = '<div class="palette-empty">' + h(tr('没有匹配的命令')) + '</div>';
    return;
  }
  var html = '', group = null;
  PAL.view.forEach(function (c, i) {
    if (c.group !== group) { html += '<div class="palette-group">' + h(c.group) + '</div>'; group = c.group; }
    html += '<div class="palette-item" role="option" id="pal-opt-' + i + '" data-i="' + i + '"'
      + ' aria-selected="' + (i === PAL.idx ? 'true' : 'false') + '">'
      + '<span class="pi-icon" aria-hidden="true">' + h(c.icon || '') + '</span>'
      + '<span class="pi-label">' + h(c.label) + '</span>'
      + (c.hint ? '<span class="pi-hint">' + h(c.hint) + '</span>' : '')
      + '</div>';
  });
  list.innerHTML = html;
  var input = document.getElementById('paletteInput');
  if (input) input.setAttribute('aria-activedescendant', 'pal-opt-' + PAL.idx);
  paletteScrollIntoView(PAL.idx);
}

function paletteMove(delta) {
  if (!PAL.view.length) return;
  PAL.idx = (PAL.idx + delta + PAL.view.length) % PAL.view.length;
  var input = document.getElementById('paletteInput');
  paletteRender(input ? input.value : '');
}

function paletteRun(i) {
  var c = PAL.view[i == null ? PAL.idx : i];
  if (!c) return;
  closePalette();
  try { c.run(); } catch (e) { /* 单个命令失败不影响面板本身 */ }
}

/* 鼠标悬停只改高亮，不重建列表（重建会打断 hover 造成抖动） */
function paletteHighlight(i) {
  PAL.idx = i;
  var list = document.getElementById('paletteList');
  if (list) {
    list.querySelectorAll('.palette-item').forEach(function (el) {
      el.setAttribute('aria-selected', el.getAttribute('data-i') === String(i) ? 'true' : 'false');
    });
  }
  var input = document.getElementById('paletteInput');
  if (input) input.setAttribute('aria-activedescendant', 'pal-opt-' + i);
  paletteScrollIntoView(i);
}

/* 键盘移动后把选中项滚进可视区（列表超过一屏时必需） */
function paletteScrollIntoView(i) {
  var list = document.getElementById('paletteList');
  if (!list || !list.querySelector) return;
  var el = list.querySelector('#pal-opt-' + i);
  if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
}

function initPalette() {
  var input = document.getElementById('paletteInput');
  if (!input) return;
  input.addEventListener('keydown', function (e) {
    var k = e.key;
    if (k === 'ArrowDown') { e.preventDefault(); paletteMove(1); }
    else if (k === 'ArrowUp') { e.preventDefault(); paletteMove(-1); }
    else if (k === 'Home') { e.preventDefault(); PAL.idx = 0; paletteRender(input.value); }
    else if (k === 'End') { e.preventDefault(); PAL.idx = PAL.view.length - 1; paletteRender(input.value); }
    else if (k === 'Enter') { e.preventDefault(); paletteRun(); }
    else if (k === 'Escape') { e.preventDefault(); closePalette(); }
  });
  input.addEventListener('input', function () { PAL.idx = 0; paletteRender(input.value); });
  var list = document.getElementById('paletteList');
  if (!list) return;
  list.addEventListener('click', function (e) {
    var item = e && e.target && e.target.closest ? e.target.closest('.palette-item') : null;
    if (item) paletteRun(Number(item.getAttribute('data-i')));
  });
  list.addEventListener('mousemove', function (e) {
    var item = e && e.target && e.target.closest ? e.target.closest('.palette-item') : null;
    if (!item) return;
    var i = Number(item.getAttribute('data-i'));
    if (i !== PAL.idx) paletteHighlight(i);
  });
}

/* ═══════ 全局快捷键 + 帮助 ═══════ */
const SHORTCUT_ROWS = [
  { group: '全局快捷键', keys: ['Ctrl', 'K'], label: '打开命令面板' },
  { group: '全局快捷键', keys: ['/'], label: '聚焦查询输入框' },
  { group: '全局快捷键', keys: ['1', '–', '5'], label: '切换视图标签' },
  { group: '全局快捷键', keys: ['←', '→'], label: '标签行切换视图' },
  { group: '全局快捷键', keys: ['?'], label: '打开本帮助' },
  { group: '全局快捷键', keys: ['Esc'], label: '关闭当前浮层' }
];

function renderHelp() {
  var box = document.getElementById('helpBody');
  if (!box) return;
  var html = '', group = null;
  SHORTCUT_ROWS.forEach(function (r) {
    if (r.group !== group) { html += '<div class="help-group">' + h(tr(r.group)) + '</div>'; group = r.group; }
    html += '<div class="help-row"><span>' + h(tr(r.label)) + '</span><span>'
      + r.keys.map(function (k) { return '<kbd class="kbd">' + h(k) + '</kbd>'; }).join(' ')
      + '</span></div>';
  });
  box.innerHTML = html;
}

function openShortcuts() {
  var el = document.getElementById('shortcuts');
  if (!el) return;
  renderHelp();
  el.hidden = false;
}

function closeShortcuts() {
  var el = document.getElementById('shortcuts');
  if (el) el.hidden = true;
}

/* 输入类控件聚焦时让位给控件本身，避免快捷键抢按键 */
function isTypingTarget(t) {
  if (!t) return false;
  var tag = String(t.tagName || '').toLowerCase();
  return tag === 'input' || tag === 'textarea' || tag === 'select' || t.isContentEditable === true;
}

function initShortcuts() {
  document.addEventListener('keydown', function (e) {
    var k = e.key;
    if ((e.ctrlKey || e.metaKey) && (k === 'k' || k === 'K')) {
      e.preventDefault();
      if (PAL.open) closePalette(); else openPalette();
      return;
    }
    if (k === 'Escape') {
      if (PAL.open) { closePalette(); return; }
      var sh = document.getElementById('shortcuts');
      if (sh && !sh.hidden) { closeShortcuts(); return; }
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (isTypingTarget(e.target)) return;
    if (k === '/') {
      e.preventDefault();
      switchTab('nlq');
      var input = document.getElementById('nlqInput');
      if (input && input.focus) input.focus();
      return;
    }
    if (k === '?') { e.preventDefault(); openShortcuts(); return; }
    var n = Number(k);
    if (n >= 1 && n <= TAB_IDS.length) { e.preventDefault(); switchTab(TAB_IDS[n - 1]); }
  });
}

/* ═══════ 指标卡迷你趋势 ═══════
   卡片只展示当前年数值；这里用一次公开接口取该经济体的跨年序列，在每张卡
   footer 右侧画 72×22 折线（纯装饰，对读屏隐藏，title 给出起止值与单位）。
   取数失败完全静默——趋势是增强信息，不能影响卡片本身。 */
async function loadSparks(dimKey, cards) {
  try {
    if (!dimKey || !cards || !cards.length) return;
    var r = await fetch(API + '/api/indicators?dimension=' + enc(dimKey) + '&' + langQ());
    var rows = await r.json();
    if (!Array.isArray(rows) || !rows.length) return;
    var series = {};
    rows.forEach(function (row) {
      var key = row.indicator_key || row.indicator;
      var v = Number(row.value);
      if (!key || row.value == null || row.value === '' || !isFinite(v)) return;
      (series[key] = series[key] || []).push({ year: Number(row.year), value: v });
    });
    var grid = document.getElementById('metricsGrid');
    if (!grid) return;
    var boxes = grid.querySelectorAll('.metric-spark');
    cards.forEach(function (c, i) {
      var pts = (series[c.label_key || c.label] || []).sort(function (a, b) { return a.year - b.year; });
      var box = boxes[i];
      if (!box || pts.length < 2) return;
      box.innerHTML = sparkSvg(pts);
      box.setAttribute('title', sparkTitle(pts, c.unit));
    });
  } catch (e) { /* 静默：趋势失败不波及卡片 */ }
}

function sparkSvg(pts) {
  var W = 72, H = 22, pad = 2.5;
  var xMin = pts[0].year, xMax = pts[pts.length - 1].year;
  var yMin = Infinity, yMax = -Infinity;
  pts.forEach(function (p) { if (p.value < yMin) yMin = p.value; if (p.value > yMax) yMax = p.value; });
  var spanX = (xMax - xMin) || 1, spanY = (yMax - yMin) || 1;
  var d = pts.map(function (p, i) {
    var x = pad + ((p.year - xMin) / spanX) * (W - pad * 2);
    var y = H - pad - ((p.value - yMin) / spanY) * (H - pad * 2);
    return (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
  }).join(' ');
  var last = pts[pts.length - 1];
  var lx = pad + ((last.year - xMin) / spanX) * (W - pad * 2);
  var ly = H - pad - ((last.value - yMin) / spanY) * (H - pad * 2);
  return '<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '" aria-hidden="true" focusable="false">'
    + '<path d="' + d + '" fill="none" stroke="var(--blue-500)" stroke-width="1.5"'
    + ' stroke-linecap="round" stroke-linejoin="round"/>'
    + '<circle cx="' + lx.toFixed(1) + '" cy="' + ly.toFixed(1) + '" r="2" fill="var(--blue-600)"/>'
    + '</svg>';
}

function sparkTitle(pts, unit) {
  var a0 = pts[0], b0 = pts[pts.length - 1];
  return tr('迷你趋势') + ' ' + a0.year + '–' + b0.year + ' · '
    + fmtNum(a0.value) + ' → ' + fmtNum(b0.value) + (unit ? ' ' + unit : '');
}

/* ═══════ 图表（自绘 SVG，无图表库依赖） ═══════ */
var CHART = { indicators: [], dimOptions: [], years: [], rows: [], currentKey: null, unit: '', selDims: [] };
/* 图表序列色板：引用 style.css 的 --ch-* 令牌，深色模式自动换成亮色（保证对比度），
   不再写死十六进制值。 */
var CHART_COLORS = [];
for (var _ci = 1; _ci <= 14; _ci++) CHART_COLORS.push('var(--ch-' + _ci + ')');

/* 拉取指标列表 + 维度选项 + 年份；构建下拉与维度多选；已选指标则重新取数 */
async function initCharts() {
  try {
    var rk = await fetch(API + '/api/indicator_keys?' + langQ());
    var keys = await rk.json();
    var seen = {};
    CHART.indicators = [];
    (keys || []).forEach(function (k) {
      var ik = k.indicator_key || k.indicator;
      if (ik && !seen[ik]) { seen[ik] = true; CHART.indicators.push({ key: ik, label: k.indicator }); }
    });
    var ro = await fetch(API + '/api/overview?year=' + enc(STATE.year) + '&dimension=' + enc(STATE.dimension) + '&' + langQ());
    var ov = await ro.json();
    CHART.dimOptions = (ov.dimension_options || []).map(function (o) { return { key: o.key, label: o.label }; });
    CHART.years = (ov.years || []).slice().sort(function (a, b) { return a - b; });
    /* 分享链接带来的维度多选优先于默认值：刷新/换指标后仍能还原对比组合 */
    if (window._pendingChartDims && window._pendingChartDims.length) {
      var pend = window._pendingChartDims;
      window._pendingChartDims = null;
      CHART.selDims = CHART.dimOptions.filter(function (d) { return pend.indexOf(d.key) >= 0; }).map(function (d) { return d.key; });
    }
    if (!CHART.selDims.length) {
      var def = ['中国','日本','韩国','印度','亚太'];
      CHART.selDims = CHART.dimOptions.filter(function (d) { return def.indexOf(d.key) >= 0; }).map(function (d) { return d.key; });
      if (!CHART.selDims.length && CHART.dimOptions.length) CHART.selDims = [CHART.dimOptions[0].key];
    }
  } catch (e) { /* 忽略 */ }
  fillChartIndicator();
  // 分享链接带 indicator 时，下拉填充后带入并取数
  if (window._pendingChartIndicator) {
    var pk = window._pendingChartIndicator;
    window._pendingChartIndicator = null;
    if (CHART.indicators.some(function (it) { return it.key === pk; })) {
      var sel = document.getElementById('chartIndicator');
      if (sel) sel.value = pk;
      CHART.currentKey = pk;
    }
  }
  renderDimChips();
  fillChartYear();
  if (CHART.currentKey) loadChartSeries();
  else renderCharts();
}

function fillChartIndicator() {
  var sel = document.getElementById('chartIndicator');
  if (!sel) return;
  var prev = sel.value;
  sel.innerHTML = '<option value="">' + h(tr('选择指标…')) + '</option>'
    + CHART.indicators.map(function (it) { return '<option value="' + a(it.key) + '">' + h(it.label) + '</option>'; }).join('');
  if (CHART.indicators.some(function (it) { return it.key === prev; })) sel.value = prev;
}

function renderDimChips() {
  var box = document.getElementById('chartDimPick');
  if (!box) return;
  box.innerHTML = CHART.dimOptions.map(function (d) {
    var on = CHART.selDims.indexOf(d.key) >= 0;
    return '<label class="dim-chip' + (on ? ' on' : '') + '">'
      + '<input type="checkbox" ' + (on ? 'checked' : '') + ' data-dim="' + a(d.key) + '" onchange="toggleDim(this)">'
      + '<span>' + h(d.label) + '</span></label>';
  }).join('');
}

function toggleDim(cb) {
  var k = cb.dataset.dim;
  var i = CHART.selDims.indexOf(k);
  if (cb.checked) { if (i < 0) CHART.selDims.push(k); }
  else { if (i >= 0) CHART.selDims.splice(i, 1); }
  var chip = cb.closest('.dim-chip');
  if (chip) chip.classList.toggle('on', cb.checked);
  renderLine();
}

function fillChartYear() {
  var sel = document.getElementById('chartYear');
  if (!sel) return;
  var prev = sel.value || (CHART.years.length ? String(CHART.years[CHART.years.length - 1]) : '');
  sel.innerHTML = CHART.years.map(function (y) { return '<option value="' + a(y) + '">' + h(y + (isZh() ? '年' : '')) + '</option>'; }).join('');
  if (CHART.years.some(function (y) { return String(y) === prev; })) sel.value = prev;
}

/* 取数期间：两个图表区块显示顶部进度条 + aria-busy；旧图保留到新数据到达，避免闪烁 */
function chartBlocksLoading(on) {
  document.querySelectorAll('#panel-charts .chart-block').forEach(function (b) { b.classList.toggle('loading', on); });
  ['lineChart', 'rankChart'].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    if (on) el.setAttribute('aria-busy', 'true'); else el.removeAttribute('aria-busy');
  });
}

async function loadChartSeries() {
  var sel = document.getElementById('chartIndicator');
  if (!sel || !sel.value) {
    CHART.currentKey = null; CHART.rows = []; CHART.unit = '';
    var cu0 = document.getElementById('chartUnit'); if (cu0) cu0.textContent = '';
    renderCharts(); return;
  }
  CHART.currentKey = sel.value;
  updateShareUrl();
  chartBlocksLoading(true);
  try {
    var r = await fetch(API + '/api/indicators?indicator=' + enc(sel.value) + '&' + langQ());
    var rows = await r.json();
    CHART.rows = rows || [];
    var u = '';
    for (var i = 0; i < CHART.rows.length; i++) { if (CHART.rows[i].unit) { u = CHART.rows[i].unit; break; } }
    CHART.unit = u;
    var cu = document.getElementById('chartUnit');
    if (cu) cu.textContent = u ? (isZh() ? '单位：' : 'Unit: ') + u : '';
  } catch (e) { CHART.rows = []; }
  renderCharts();
  chartBlocksLoading(false);
}

function renderCharts() { renderLine(); renderRank(); }

function dimLabel(key) {
  for (var i = 0; i < CHART.dimOptions.length; i++) if (CHART.dimOptions[i].key === key) return CHART.dimOptions[i].label;
  return key;
}
function dimColor(key) {
  var idx = 0;
  for (var i = 0; i < CHART.dimOptions.length; i++) { if (CHART.dimOptions[i].key === key) { idx = i; break; } }
  return CHART_COLORS[idx % CHART_COLORS.length];
}
function fmtNum(v) {
  if (v == null || v === '') return '—';
  var n = Number(v);
  if (!isFinite(n)) return '—';
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
/* 卡片大数字紧凑化：28px 大字下全精度会溢出换行；紧凑记数（zh: 万/亿，en: K/M/B/T）
   更易读。精确值保留在卡片 title 属性与表格/CSV 里，两种语言都走 Intl 标准记数。 */
function compactNum(v) {
  var raw = v == null ? '' : String(v);
  if (raw === '') return '—';
  var n = Number(raw.replace(/,/g, ''));
  if (!isFinite(n)) return raw;
  if (Math.abs(n) < 1e6) return n.toLocaleString(isZh() ? 'zh-CN' : 'en-US', { maximumFractionDigits: 2 });
  return n.toLocaleString(isZh() ? 'zh-CN' : 'en-US', { notation: 'compact', maximumFractionDigits: 2 });
}
/* 统一空态（图标 + 标题 + 说明），替代各处纯文字提示；结构见 .empty-state */
function emptyState(icon, title, desc) {
  return '<div class="empty-state" role="status">'
    + '<div class="empty-icon">' + h(icon) + '</div>'
    + '<div class="empty-title">' + h(title) + '</div>'
    + (desc ? '<div class="empty-desc">' + h(desc) + '</div>' : '')
    + '</div>';
}
function chartEmpty(msg, icon) { return emptyState(icon || '📈', msg); }

/* ═══════ 图表悬浮读数（桌面 hover / 触屏 touch） ═══════
   自绘 SVG 的数值不在 DOM 文本里，鼠标悬停时按几何反查数据，用跟随指针的
   浮层给出精确读数（折线图附加竖直参考线），解决「只能目测轴刻度」的问题。
   浮层 aria-hidden：等价信息已由 SVG 的 <desc> 与结果区 aria-live 提供。 */
function chartTipBox(box) {
  var tip = box.querySelector('.chart-tip');
  if (!tip) {
    tip = document.createElement('div');
    tip.className = 'chart-tip';
    tip.setAttribute('aria-hidden', 'true');
    box.appendChild(tip);
  }
  return tip;
}
function chartTipPlace(tip, box, px, py) {
  var bw = box.clientWidth, bh = box.clientHeight;
  var tw = tip.offsetWidth, th = tip.offsetHeight;
  var left = px + 14;
  if (left + tw > bw - 6) left = px - tw - 14;
  var top = py - th - 12;
  if (top < 6) top = py + 18;
  tip.style.left = Math.max(6, left) + 'px';
  tip.style.top = Math.min(Math.max(6, top), Math.max(6, bh - th - 6)) + 'px';
}
/* 折线图：按最近年份吸附，浮层列出该年份全部可见经济体的数值 */
function attachLineTip(box, ctx) {
  var svgEl = box.querySelector('svg');
  if (!svgEl || ctx.years.length < 2) return;
  var tip = chartTipBox(box);
  var guide = svgEl.querySelector('.chart-guide');
  function show(clientX, clientY) {
    var r = svgEl.getBoundingClientRect();
    if (!r.width) return;
    var px = clientX - r.left, py = clientY - r.top;
    var vx = px * (ctx.W / r.width);
    var idx = 0, best = Infinity;
    ctx.years.forEach(function (y, i) {
      var dx = Math.abs(ctx.xFor(i) - vx);
      if (dx < best) { best = dx; idx = i; }
    });
    var y = ctx.years[idx];
    var series = ctx.active.filter(function (d) { return ctx.byDim[d][y] != null; });
    if (!series.length) { hide(); return; }
    if (guide) {
      guide.setAttribute('x1', ctx.xFor(idx));
      guide.setAttribute('x2', ctx.xFor(idx));
      guide.setAttribute('visibility', 'visible');
    }
    tip.innerHTML = '<div class="chart-tip-title">' + h(String(y) + (ctx.unit ? ' · ' + ctx.unit : '')) + '</div>'
      + series.map(function (d) {
          return '<div class="chart-tip-row"><i style="background:' + dimColor(d) + '"></i>'
            + '<span class="tip-name">' + h(dimLabel(d)) + '</span>'
            + '<span class="tip-val">' + h(fmtNum(ctx.byDim[d][y])) + '</span></div>';
        }).join('');
    tip.classList.add('show');
    chartTipPlace(tip, box, px, py);
  }
  function hide() {
    tip.classList.remove('show');
    if (guide) guide.setAttribute('visibility', 'hidden');
  }
  svgEl.addEventListener('mousemove', function (e) { show(e.clientX, e.clientY); });
  svgEl.addEventListener('mouseleave', hide);
  svgEl.addEventListener('touchstart', function (e) { var t = e.touches[0]; if (t) show(t.clientX, t.clientY); }, { passive: true });
  svgEl.addEventListener('touchmove', function (e) { var t = e.touches[0]; if (t) show(t.clientX, t.clientY); }, { passive: true });
  svgEl.addEventListener('touchend', hide);
}
/* 排名图：标签超 6 字会被截断，悬浮给出完整经济体名 + 数值 + 单位 + 年份 */
function attachRankTip(box, rows, unit) {
  var svgEl = box.querySelector('svg');
  if (!svgEl) return;
  var tip = chartTipBox(box);
  svgEl.querySelectorAll('.rank-row').forEach(function (g) {
    var r = rows[Number(g.getAttribute('data-i'))];
    if (!r) return;
    function show(e) {
      var bx = box.getBoundingClientRect();
      var dk = r.dimension_key || r.dimension;
      tip.innerHTML = '<div class="chart-tip-title">' + h(dimLabel(dk)) + '</div>'
        + '<div class="chart-tip-row"><span class="tip-name">' + h(tr('数值')) + '</span><span class="tip-val">' + h(fmtNum(r.value) + (unit ? ' ' + unit : '')) + '</span></div>'
        + '<div class="chart-tip-row"><span class="tip-name">' + h(tr('年份')) + '</span><span class="tip-val">' + h(String(r.year)) + '</span></div>';
      tip.classList.add('show');
      chartTipPlace(tip, box, e.clientX - bx.left, e.clientY - bx.top);
    }
    g.addEventListener('mousemove', show);
    g.addEventListener('mouseleave', function () { tip.classList.remove('show'); });
    g.addEventListener('touchstart', show, { passive: true });
  });
}
/* 当前所选指标的展示名（用于图表 aria-label / title 的无障碍文案） */
function chartIndicatorLabel() {
  for (var i = 0; i < CHART.indicators.length; i++) {
    if (CHART.indicators[i].key === CHART.currentKey) return CHART.indicators[i].label;
  }
  return CHART.currentKey || '';
}
function fontFamily() { return "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif"; }

/* 折线图：所选经济体跨年趋势 */
function renderLine() {
  var box = document.getElementById('lineChart');
  if (!box) return;
  if (!CHART.currentKey) { box.innerHTML = chartEmpty(tr('请先选择指标'), '📈'); return; }
  var dims = CHART.selDims.slice();
  var byDim = {};
  CHART.rows.forEach(function (r) {
    var dk = r.dimension_key || r.dimension;
    if (dims.indexOf(dk) < 0) return;
    if (r.value == null || r.value === '') return;
    byDim[dk] = byDim[dk] || {};
    byDim[dk][r.year] = Number(r.value);
  });
  var years = CHART.years.slice().sort(function (a, b) { return a - b; });
  var active = dims.filter(function (d) { return byDim[d] && Object.keys(byDim[d]).length >= 1; });
  if (years.length < 2) { box.innerHTML = chartEmpty(tr('需至少两个年份才能绘制趋势线'), '📈'); return; }
  if (!active.length) { box.innerHTML = chartEmpty(tr('该指标在所选经济体无数据'), '📈'); return; }

  var allV = [];
  active.forEach(function (d) { for (var y in byDim[d]) allV.push(byDim[d][y]); });
  var yMin = Math.min.apply(null, allV), yMax = Math.max.apply(null, allV);
  if (yMin === yMax) { var pad = (Math.abs(yMin) * 0.1) || 1; yMin -= pad; yMax += pad; }

  /* 无障碍：SVG 加 role=img 后子树被视为一张图，故必须自带等价文字描述。
     desc 逐经济体给出「首年值 → 末年值」，颜色因此不再是唯一的信息载体。 */
  var a11yLabel = tr('跨年趋势') + ': ' + chartIndicatorLabel() +
                  ' (' + years[0] + '–' + years[years.length - 1] + ')';
  var a11yDesc = active.map(function (d) {
    var ys = years.filter(function (y) { return byDim[d][y] != null; });
    if (!ys.length) return '';
    var f = ys[0], l = ys[ys.length - 1], unit = CHART.unit ? ' ' + CHART.unit : '';
    return dimLabel(d) + ': ' + f + ' ' + fmtNum(byDim[d][f]) + unit +
           (f === l ? '' : ' → ' + l + ' ' + fmtNum(byDim[d][l]) + unit);
  }).filter(Boolean).join('; ');

  var W = 760, H = 360, mL = 72, mR = 20, mT = 18, mB = 38;
  var pW = W - mL - mR, pH = H - mT - mB;
  function xFor(i) { return mL + (years.length === 1 ? pW / 2 : (i / (years.length - 1)) * pW); }
  function yFor(v) { return mT + pH - ((v - yMin) / (yMax - yMin)) * pH; }

  var ff = fontFamily();
  var svg = '<svg role="img" aria-label="' + a(a11yLabel) + '" '
    + 'viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" '
    + 'style="width:100%;height:auto">'
    + '<title>' + h(a11yLabel) + '</title>'
    + '<desc>' + h(a11yDesc) + '</desc>';
  var ticks = 4;
  /* 坐标轴与网格 */
  svg += '<line x1="' + mL + '" y1="' + mT + '" x2="' + mL + '" y2="' + (H - mB) + '" stroke="var(--gray-200)" stroke-width="1"/>';
  for (var t = 0; t <= ticks; t++) {
    var tv = yMin + (yMax - yMin) * t / ticks;
    var ty = yFor(tv);
    svg += '<line x1="' + mL + '" y1="' + ty + '" x2="' + (W - mR) + '" y2="' + ty + '" stroke="var(--gray-200)" stroke-width="1"/>';
    svg += '<text x="' + (mL - 10) + '" y="' + (ty + 4) + '" text-anchor="end" font-size="12" fill="var(--gray-500)" font-family="' + ff + '">' + h(fmtNum(Math.round(tv * 100) / 100)) + '</text>';
  }
  years.forEach(function (y, i) {
    svg += '<text x="' + xFor(i) + '" y="' + (H - 12) + '" text-anchor="middle" font-size="12" fill="var(--gray-500)" font-family="' + ff + '">' + h(y) + '</text>';
  });
  active.forEach(function (d) {
    var color = dimColor(d);
    var pts = [];
    years.forEach(function (y, i) { if (byDim[d][y] != null) pts.push(xFor(i) + ',' + yFor(byDim[d][y])); });
    if (pts.length > 1) {
      svg += '<polyline points="' + pts.join(' ') + '" fill="none" stroke="' + color + '" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>';
    }
    years.forEach(function (y, i) {
      if (byDim[d][y] != null) {
        svg += '<circle cx="' + xFor(i) + '" cy="' + yFor(byDim[d][y]) + '" r="3.5" fill="var(--surface)" stroke="' + color + '" stroke-width="2.5"/>';
      }
    });
  });
  /* 竖直参考线：hover 到最近年份时可见，辅助多序列对齐读数 */
  svg += '<line class="chart-guide" x1="0" y1="' + mT + '" x2="0" y2="' + (H - mB) + '" stroke="var(--gray-300)" stroke-width="1" stroke-dasharray="3 2" visibility="hidden"/>';
  svg += '</svg>';
  /* 图例对屏幕阅读器隐藏：经济体与数值的对应关系已写进上面的 <desc>，
     重复播报只会增加噪音（视觉用户仍可正常看到色块）。 */
  var legend = '<div class="chart-legend" aria-hidden="true">' + active.map(function (d) {
    return '<span class="lg-item"><i style="background:' + dimColor(d) + '"></i>' + h(dimLabel(d)) + '</span>';
  }).join('') + '</div>';
  box.innerHTML = svg + legend;
  attachLineTip(box, {
    W: W, H: H, xFor: xFor,
    years: years, active: active, byDim: byDim, unit: CHART.unit
  });
}

/* 排名条形图：所选年份分经济体排名 */
function renderRank() {
  var box = document.getElementById('rankChart');
  if (!box) return;
  if (!CHART.currentKey) { box.innerHTML = chartEmpty(tr('请先选择指标'), '📊'); return; }
  var yr = (document.getElementById('chartYear') || {}).value;
  var rows = CHART.rows.filter(function (r) {
    return String(r.year) === String(yr) && r.value != null && r.value !== '';
  });
  if (!rows.length) { box.innerHTML = chartEmpty(tr('该指标在所选年份无数据'), '📊'); return; }
  rows.sort(function (a, b) { return Number(b.value) - Number(a.value); });

  /* 无障碍：同折线图，role=img 需要等价的文字描述（按降序给出名次 + 数值） */
  var a11yLabel = tr('分经济体排名') + ': ' + chartIndicatorLabel() + ' (' + yr + ')';
  var a11yDesc = rows.map(function (r, i) {
    var dk = r.dimension_key || r.dimension;
    return (i + 1) + '. ' + dimLabel(dk) + ' ' + fmtNum(r.value) +
           (CHART.unit ? ' ' + CHART.unit : '');
  }).join('; ');

  var labelW = 108, barX = labelW + 12, valW = 80;
  var rowH = 28, padT = 8;
  var W = 760, H = padT * 2 + rows.length * rowH;
  var max = Number(rows[0].value) || 1;
  var chartW = W - barX - valW;
  var ff = fontFamily();

  var svg = '<svg role="img" aria-label="' + a(a11yLabel) + '" '
    + 'viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" '
    + 'style="width:100%;height:auto">'
    + '<title>' + h(a11yLabel) + '</title>'
    + '<desc>' + h(a11yDesc) + '</desc>';
  rows.forEach(function (r, i) {
    var dk = r.dimension_key || r.dimension;
    var color = CHART_COLORS[i % CHART_COLORS.length];
    var y = padT + i * rowH;
    var bw = Math.max(2, (Number(r.value) / max) * chartW);
    var label = dimLabel(dk);
    if (label.length > 7) label = label.slice(0, 6) + '…';
    svg += '<g class="rank-row" data-i="' + i + '">'
      + '<text x="' + (labelW - 8) + '" y="' + (y + 17) + '" text-anchor="end" font-size="12" fill="var(--gray-600)" font-family="' + ff + '">' + h(label) + '</text>';
    svg += '<rect x="' + barX + '" y="' + (y + 5) + '" width="' + bw + '" height="18" rx="4" fill="' + color + '"/>';
    svg += '<text x="' + (barX + bw + 8) + '" y="' + (y + 17) + '" font-size="12" fill="var(--gray-700)" font-family="' + ff + '" font-weight="600">' + h(fmtNum(r.value)) + '</text>'
      + '</g>';
  });
  svg += '</svg>';
  box.innerHTML = svg;
  attachRankTip(box, rows, CHART.unit);
}
