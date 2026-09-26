/* ============================================
   亚太统计分析系统 · 前端逻辑（core）
   对接真实 Flask API（/api/overview, /api/ask, /api/indicators,
   /api/custom, /api/report, /api/collect, /api/stats）
   注意：/api/db、/api/reseed、/api/kv-status、/api/collect 是**管理端点**，
   生产环境需令牌（无令牌一律 403），前端展示类数据一律走公开端点 /api/stats。
   数据全部来自公开官方数据源（世界银行 Open Data / 国家统计局 / 海关总署）。

   代码分割：本文件只放**首屏必需**的部分（core）。图表与命令面板拆到
   public/app.charts.js 与 public/app.palette.js，首次用到时由 loadChunk()
   动态拉取——经典脚本共享全局词法环境，分块可以直接读写这里的 const。
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


/* ═══════ 图表状态 ═══════
   放在 core 而不是 app.charts.js，是因为 core 自己就要读它：updateShareUrl() 读
   CHART.currentKey / CHART.selDims 拼分享链接，exportChartCsv() 读
   CHART.currentKey 拼导出 URL。这两条都是 core 的能力，不能等图表分块加载。
   var 声明挂到全局对象上，所以分块照样读写同一个对象。 */
var CHART = { indicators: [], dimOptions: [], years: [], rows: [], currentKey: null, unit: '', selDims: [] };
/* 图表序列色板：引用 style.css 的 --ch-* 令牌，深色模式自动换成亮色（保证对比度），
   不再写死十六进制值。 */
var CHART_COLORS = [];
for (var _ci = 1; _ci <= 14; _ci++) CHART_COLORS.push('var(--ch-' + _ci + ')');

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

/* 图表：导出当前选中指标的完整跨年 × 全经济体序列（不传 year/dimension = 全部） */
function exportChartCsv() {
  if (!CHART.currentKey) { showToast(tr('请先选择指标'), 'error'); return; }
  var u = API + '/api/export.csv?indicator=' + enc(CHART.currentKey) + '&' + langQ();
  exportCsv(u);
  showToast(tr('已导出 CSV'), 'success');
}

/* ═══════ 最近提问 ═══════
   把本机最近问过的问题记在 localStorage，点一下直接重跑——与命令面板互补：
   面板适合「想到什么搜什么」，这里适合「刚才那个再问一遍」。
   只存纯文本；隐私模式下存取抛错时整体静默降级，不影响主链路。

   位置说明：这两个 const 必须留在 init() 之前。init() 是文件中部的一个 IIFE，
   一加载就跑；本文件历史上的回归就是「增强能力」的 const 声明在 init() 之后，
   一执行就踩暂时死区、又被 try/catch 吞掉。后来者请把这个顺序守住。 */
const RECENT_KEY = 'qu_recent_q_v1';
const RECENT_MAX = 6;

function readRecentQueries() {
  try {
    var raw = localStorage.getItem(RECENT_KEY);
    var arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr)
      ? arr.filter(function (x) { return typeof x === 'string' && x.trim(); }).slice(0, RECENT_MAX)
      : [];
  } catch (e) { return []; }
}

function writeRecentQueries(list) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, RECENT_MAX)));
  } catch (e) { /* 隐私模式：不记忆、不报错 */ }
}

function pushRecentQuery(text) {
  var q = String(text || '').trim();
  var cur = readRecentQueries();
  if (!q) return cur;
  var next = [q].concat(cur.filter(function (x) { return x !== q; })).slice(0, RECENT_MAX);
  writeRecentQueries(next);
  return next;
}

function clearRecentQueries() {
  writeRecentQueries([]);
  renderRecentQueries();
  showToast(tr('已清空最近提问'), 'success');
}

function renderRecentQueries() {
  var box = document.getElementById('nlqRecent');
  var chips = document.getElementById('nlqRecentChips');
  if (!box || !chips) return;
  var list = readRecentQueries();
  if (!list.length) { box.hidden = true; chips.innerHTML = ''; return; }
  box.hidden = false;
  chips.innerHTML = list.map(function (q) {
    return '<span class="suggestion-chip recent-chip" role="button" tabindex="0"'
      + ' data-q="' + a(q) + '" title="' + a(q) + '"'
      + ' onclick="fillQuery(this.dataset.q);runAnalyze()"'
      + ' onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();'
      + 'fillQuery(this.dataset.q);runAnalyze();}">' + h(q) + '</span>';
  }).join('');
}

/* ───── 页面入口 ───── */
(function init() {
  initShareState();   // 从 URL 还原分享状态（年份/维度/语言/图表指标）后再取数
  document.querySelectorAll('.wb-tab').forEach(btn => {
    /* 只做转发：激活态、懒加载、分享链接同步都写在 switchTab() 里一份，
       两边各写一遍必然漂移（这里此前就重复过一整套 class 切换）。 */
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
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
  /* 不在这里预取自定义分析下拉：loadCustomList() 在自定义分析分块里，首访就调
     会 ReferenceError（其实现已按需加载）。首次打开该 tab 时 initCustom() 会
     fill 下拉，预取反而让懒加载名存实亡。 */
  loadDbStats();
  loadInsights();
  renderRecentQueries();   // 有历史提问才显示「最近提问」一行

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
/* 指标总表已拆成按需分块：没打开过该 tab 时 loadIndicators 还不存在，直接调会
   ReferenceError 并把 syncYear/syncDimension 剩下的 toast、分享链接一起炸掉。
   typeof 守卫：打开过就刷新，没打开过就跳过——下次打开 tab 时 openTab 会拉下
   分块并按当时最新的年份/维度渲染，不会有脏数据。 */
function refreshIndicatorsIfLoaded() {
  if (typeof loadIndicators === 'function') loadIndicators();
}

function syncYear(y) {
  STATE.year = String(y);
  const gy = document.getElementById('globalYear');
  if (gy) gy.value = STATE.year;
  loadOverview();
  refreshIndicatorsIfLoaded();
  loadInsights();
  updateShareUrl();
  showToast(tr('年份已切换至') + ' ' + STATE.year + (isZh() ? '年' : ''), 'success');
}

function syncDimension(d) {
  STATE.dimension = d;
  const gd = document.getElementById('globalDimension');
  if (gd) gd.value = d;
  loadOverview();
  refreshIndicatorsIfLoaded();
  loadInsights();
  updateShareUrl();
  showToast(tr('维度已切换至') + ' ' + tr(d), 'success');
}

/* ───── Tab 切换（来自快捷按钮） ───── */
/* ───── 代码分割：按需加载 ─────
   看板首访只下发本文件（core）。图表、命令面板这些「打开才用到」的代码拆成独立
   文件，首次用到时动态插入 <script>。经典脚本共享同一个全局词法环境，所以分块可以
   直接读写 core 的 const（STATE / API / THEME_* …），不需要模块打包器，也不必将
   已有函数改成 export。

   为什么走注入而不是写死路径：服务端给分块发的是一年 immutable 缓存，URL 不带
   版本号的话，改了分块、用户浏览器也会继续用旧文件。版本号由 app.html 里的
   window.__CHUNK_URLS 带进来（各资产各自的内容哈希，由 _render_page 替换占位符），
   与 <script src> 上的同源；读不到注入时退回裸路径，至少不白屏。
/* 分块地址带**自己**的内容哈希（app.html 里的 window.__CHUNK_URLS 注入）：
   服务端给分块发的是一年 immutable 缓存，URL 不带版本号的话，改了分块
   浏览器也会继续用旧文件。读不到注入时退回裸路径，保证不白屏。 */
var CHUNK_SRC = {
  charts: (window.__CHUNK_URLS || {}).charts || '/app.charts.js',
  palette: (window.__CHUNK_URLS || {}).palette || '/app.palette.js',
  indicators: (window.__CHUNK_URLS || {}).indicators || '/app.indicators.js',
  custom: (window.__CHUNK_URLS || {}).custom || '/app.custom.js',
  bulletin: (window.__CHUNK_URLS || {}).bulletin || '/app.bulletin.js'
};
var CHUNK_LOADING = {};

/* 每个 tab 自己的「语言切换后刷新什么」：分块在加载末尾调用 onLangRefresh 注册。
   core 的 refreshLang() 据此按当前激活的面板刷新，**不点名任何 tab 专属函数**——
   那既是加载顺序地雷，也让分块拆不出去。

   hasCache 回答「我这个面板现在有没有值得重刷的内容」：没有就只在被激活时才刷，
   免得为看不见的空面板白发请求（上一版是无条件全刷）。 */
var LANG_HOOKS = {};
function onLangRefresh(tabId, refresh, hasCache) {
  LANG_HOOKS[tabId] = { refresh: refresh, hasCache: hasCache || function () { return false; } };
}

function activeTabId() {
  var el = document.querySelector('.wb-panel.active');
  return el && el.id ? el.id.replace(/^panel-/, '') : 'nlq';
}

function loadChunk(name) {
  /* 没有登记分块的 tab（nlq 的实现整块就在 core 里）直接兑现：
     否则会给一个不存在的 URL 造 <script>，浏览器 404 → onerror → reject，
     openTab 的 catch 随即弹「加载失败」，而该面板真正的初始化永远不跑。 */
  if (!CHUNK_SRC[name]) return Promise.resolve();
  if (CHUNK_LOADING[name]) return CHUNK_LOADING[name];
  var s = document.createElement('script');
  CHUNK_LOADING[name] = new Promise(function (resolve, reject) {
    s.src = CHUNK_SRC[name];
    s.onload = function () { resolve(); };
    s.onerror = function () {
      /* 失败时清掉缓存，让重试能再拉一次（网络恢复、刷新后） */
      delete CHUNK_LOADING[name];
      reject(new Error('chunk load failed: ' + name));
    };
    (document.body || document.documentElement).appendChild(s);
  });
  return CHUNK_LOADING[name];
}

/* 打开某个 tab：先把它的代码拉下来，再跑该 tab 的初始化。
   分块里的函数必须在 .then 内部才引用——openTab 是同步调用的，那时分块还没下来，
   在函数体里直接写 initCharts() 只会拿到 undefined。 */
function openTab(tabId) {
  return loadChunk(tabId).then(function () {
    if (tabId === 'charts') return initCharts();
    if (tabId === 'indicators') return loadIndicators();
    if (tabId === 'custom') return initCustom();
    // bulletin 的内容由「生成公报」按钮按需生成，打开面板时无需初始化
  }).catch(function (e) {
    console.error('打开 ' + tabId + ' 面板失败', e);
    showToast(tr('加载失败，请重试'), 'error');
  });
}

/* 面板内按钮的统一入口。分块是懒加载的：用户点了 tab 就立刻点里面的按钮时，
   分块可能还没下来，直接 onclick="loadBulletin()" 会撞上 undefined。
   先把分块拉下来（已加载则同步兑现），再跑真正的处理函数。
   fn 传**函数名的字符串**（HTML 里写作 tabAction('custom','saveCustom')），
   在 .then 里、分块到位之后才按名字解析——内联 onclick 若直接写裸函数名，
   点击瞬间就会把它当标识符求值，分块没加载就是 ReferenceError：头部命令面板
   按钮就这样在首访永远打不开（分块还没加载，面板又只能靠它打开，死锁）。
   额外参数原样转发（removeVarRow 要拿当前行、fillExpr 要拿公式种类）。 */
function tabAction(tabId, fnName) {
  var args = Array.prototype.slice.call(arguments, 2);
  return openTab(tabId).then(function () {
    var fn = typeof fnName === 'function' ? fnName : window[fnName];
    if (typeof fn !== 'function') {
      throw new Error('tab action missing: ' + tabId + '/' + fnName);
    }
    return fn.apply(null, args);
  });
}
function switchTab(tabId) {
  document.querySelectorAll('.wb-tab').forEach(b => {
    const on = b.dataset.tab === tabId;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  document.querySelectorAll('.wb-panel').forEach(p => p.classList.toggle('active', p.id === 'panel-' + tabId));
  /* 统一走 openTab：有分块的 tab 先把代码拉下来、再在 .then 里初始化；
     没有分块的（nlq）由 loadChunk 短路、立刻兑现。
     别再另起一份「哪些 tab 要懒加载」的名单——名单漏项正是上一轮
     指标面板静默失效的成因。 */
  var task = openTab(tabId);
  updateShareUrl();
  return task;
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
        + emptyState('globe', tr('该维度暂无数据'),
          tr('该经济体在此维度下暂无公开数据，可切换年份或回到亚太聚合口径查看')) + back + '</div>';
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
    grid.innerHTML = '<div class="metric-card" style="grid-column:1/-1">' + emptyState('alert', tr('加载失败'),
        tr('网络或服务端异常，请稍后重试；若持续失败请联系管理员')) + '</div>';
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
      + emptyState('alert', tr('加载失败'),
        tr('网络或服务端异常，请稍后重试；若持续失败请联系管理员')) + '</div>';
  }
}

function insightCard(iconName, title, sub, body) {
  return '<div class="insight-card">'
    + '<div class="insight-head"><span class="insight-title">' + icon(iconName, 'icon-svg insight-icon')
    + ' ' + h(title) + '</span>'
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
    : emptyState('trending', tr('暂无洞察'),
        tr('需要同指标的上一年数据才能算同比，当前维度暂时凑不齐'));
  var c1 = insightCard('trending', tr('同比变化最大'), tr('较上年'), mBody);

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
    : emptyState('medal', tr('暂无洞察'),
        tr('需要该指标在两年间都有排名的经济体，当前维度暂时凑不齐'));
  var c2 = insightCard('medal', rTitle, tr('名次'), rBody);

  /* 卡 3：覆盖规模（计数本身就是洞察：数据到底有多全） */
  var cov = d.coverage || {};
  var chips = [
    { label: tr('指标行'), value: cov.rows },
    { label: tr('覆盖经济体'), value: cov.economies },
    { label: tr('可比指标'), value: cov.comparable }
  ].map(function (x) {
    return '<div class="insight-chip">' + h(x.label) + '<b>' + h(x.value == null ? '—' : x.value) + '</b></div>';
  }).join('');
  var c3 = insightCard('database', tr('覆盖规模'), years, '<div class="insight-chips">' + chips + '</div>');
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
    var t0 = Date.now();
    var r = await fetch(u);
    var ms = Date.now() - t0;
    var d = await r.json();
    var html = '';
    var ai = pick(d, 'AI 解读', 'ai_interpretation');
    if (ai) {
      /* 命中缓存要让人看见：省下的是真金白银的 token 与 5-20 秒等待 */
      var badge = d.cached
        ? ' <span class="cache-badge" title="' + a(tr('同一问题与同一份数据')) + '">' + icon('zap', 'icon-svg cache-icon') + ' '
          + h(tr('来自缓存')) + '</span>'
        : '';
      html += '<div class="ai-card"><div class="ai-head">' + icon('sparkles', 'icon-svg ai-icon') + ' ' + tr('AI 云端解读') + badge
        + ' <span class="ai-elapsed">' + h(tr('耗时')) + ' ' + (ms / 1000).toFixed(1)
        + 's</span></div>'
        + '<div class="ai-body">' + mdToHtml(ai) + '</div>'
        + (d.task_id ? '<div class="ai-foot">' + tr('task_id') + ': ' + h(d.task_id) + '</div>' : '')
        + '</div>';
    }
    html += renderAsk(d);
    var ref = pick(d, '知识库参考', 'kb_reference');
    if (ref) html += '<div class="kb-ref"><b>' + tr('知识库参考') + '</b>' + mdToHtml(ref) + '</div>';
    el.innerHTML = html || '<div class="rk">' + tr('无结果') + '</div>';
    /* 记进「最近提问」：重复提问正是缓存能发挥作用的场景，顺手把入口铺出来 */
    pushRecentQuery(input);
    renderRecentQueries();
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
      refreshIndicatorsIfLoaded();
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


/* ═══════ 内联 SVG 图标集（线性 / currentColor）═══════
   为什么不再用 emoji：各家操作系统对 emoji 的字形与配色渲染互不相同
   （Windows / macOS / Android 三套设计语言），在空态这种大面积居中的位置
   差异最刺眼——同一个产品在三台设备上像三个版本，且 emoji 无法跟随主题
   令牌取色（深色模式下一排彩色emoji尤其违和）。改用内联 SVG 线性图标
  （heroicons / lucide / Bootstrap Icons 的共同做法）：24×24 网格、
   `currentColor` 描边、`fill:none`，颜色与粗细随 CSS 走，跨端完全一致，
   还能被 CSS 控制大小。图标是内部固定集合，不是用户输入，直接拼字符串
   不过 h()，由 ICONS 白名单兜底。 */
var ICONS = {
  globe: '<circle cx="12" cy="12" r="8.6"/><path d="M3.4 12h17.2"/><path d="M12 3.4c2.6 2.7 3.9 5.7 3.9 8.6s-1.3 5.9-3.9 8.6c-2.6-2.7-3.9-5.7-3.9-8.6S9.4 6.1 12 3.4z"/>',
  alert: '<path d="M10.3 4.2 2.6 17.6a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z"/><path d="M12 9.4v4"/><path d="M12 16.7h.01"/>',
  trending: '<path d="M3 17.4 9 10.9l4 4 8-8.4"/><path d="M15 6.4h6v6"/>',
  medal: '<circle cx="12" cy="9" r="5.2"/><path d="M8.8 13.5 7.2 21.4 12 18.9l4.8 2.5-1.6-7.9"/>',
  database: '<ellipse cx="12" cy="6" rx="7.4" ry="2.9"/><path d="M4.6 6v6c0 1.6 3.3 2.9 7.4 2.9s7.4-1.3 7.4-2.9V6"/><path d="M4.6 12v6c0 1.6 3.3 2.9 7.4 2.9s7.4-1.3 7.4-2.9v-6"/>',
  clipboard: '<path d="M9.4 4.2H7.4a2 2 0 0 0-2 2v12.6a2 2 0 0 0 2 2h9.2a2 2 0 0 0 2-2V6.2a2 2 0 0 0-2-2h-2"/><rect x="9.4" y="2.7" width="5.2" height="3.4" rx="1.2"/><path d="M9 12.4h6"/><path d="M9 16.4h4"/>',
  inbox: '<path d="M3.4 13h4.3l1.4 2.6h5.8l1.4-2.6h4.3"/><path d="M5.9 4.6h12.2l2.3 8.1V18a2 2 0 0 1-2 2H5.6a2 2 0 0 1-2-2v-5.3l2.3-8.1z"/>',
  linechart: '<path d="M4 4v16h16"/><path d="M7.5 14.4 11 10.5l3 2.6 4.4-5.5"/>',
  barchart: '<path d="M4 4v16h16"/><path d="M8.6 16.6v-4.4"/><path d="M13.4 16.6V8.4"/><path d="M18.2 16.6V6.2"/>',
  search: '<circle cx="11" cy="11" r="6.2"/><path d="M20.4 20.4 15.9 15.9"/>',
  sparkles: '<path d="M11 3.6l1.7 4.7 4.7 1.7-4.7 1.7L11 16.4l-1.7-4.7L4.6 10l4.7-1.7z"/><path d="M18.2 15.4l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>',
  calendar: '<rect x="3.6" y="5.6" width="16.8" height="14.8" rx="2"/><path d="M3.6 10.2h16.8"/><path d="M8.6 3.6v3.6"/><path d="M15.4 3.6v3.6"/>',
  message: '<path d="M4 6.6A2.6 2.6 0 0 1 6.6 4h10.8A2.6 2.6 0 0 1 20 6.6v6.8a2.6 2.6 0 0 1-2.6 2.6H9.8L5.2 19.9v-4H6.6A2.6 2.6 0 0 1 4 13.4z"/>',
  table: '<rect x="3.6" y="4.6" width="16.8" height="14.8" rx="2"/><path d="M3.6 9.4h16.8"/><path d="M9.6 9.4v10"/><path d="M15.2 9.4v10"/>',
  calculator: '<rect x="4.6" y="3.2" width="14.8" height="17.6" rx="2"/><path d="M8 7.4h8"/><path d="M8.6 12h.01"/><path d="M12 12h.01"/><path d="M15.4 12h.01"/><path d="M8.6 16h.01"/><path d="M12 16h.01"/><path d="M15.4 16h.01"/>',
  filetext: '<path d="M6 3.6h7.4L19 9.2v11.2a1.4 1.4 0 0 1-1.4 1.4H6a1.4 1.4 0 0 1-1.4-1.4V5A1.4 1.4 0 0 1 6 3.6z"/><path d="M13.4 3.6V9.2H19"/><path d="M8.6 13h6.8"/><path d="M8.6 16.4h4.6"/>',
  theme: '<circle cx="12" cy="12" r="8.4"/><path d="M12 3.6v16.8"/>',
  translate: '<path d="M4 5.6h9"/><path d="M8.5 3.6v2"/><path d="M11.4 5.6c0 4-2.5 7.4-6 8.4"/><path d="M6 9.4c1 2.5 3 4.2 5.4 5"/><path d="M13.4 20.4l3.8-9 3.8 9"/><path d="M14.9 17.4h5.6"/>',
  link: '<path d="M10 13.4a3.5 3.5 0 0 0 5 0l3-3a3.54 3.54 0 0 0-5-5l-1.5 1.5"/><path d="M14 10.6a3.5 3.5 0 0 0-5 0l-3 3a3.54 3.54 0 0 0 5 5l1.5-1.5"/>',
  download: '<path d="M12 3.6v11"/><path d="M7.6 10.4 12 14.8l4.4-4.4"/><path d="M4.6 20.4h14.8"/>',
  keyboard: '<rect x="2.6" y="6.6" width="18.8" height="10.8" rx="2"/><path d="M6.4 10h.01"/><path d="M9.9 10h.01"/><path d="M13.4 10h.01"/><path d="M16.9 10h.01"/><path d="M8.2 14h7.6"/>',
  sun: '<circle cx="12" cy="12" r="4.2"/><path d="M12 2.8v2.2"/><path d="M12 19v2.2"/>'
    + '<path d="M4.8 4.8l1.6 1.6"/><path d="M17.6 17.6l1.6 1.6"/><path d="M2.8 12h2.2"/>'
    + '<path d="M19 12h2.2"/><path d="M4.8 19.2l1.6-1.6"/><path d="M17.6 6.4l1.6-1.6"/>',
  moon: '<path d="M20.2 14.6A8.4 8.4 0 0 1 9.4 3.8a8.4 8.4 0 1 0 10.8 10.8z"/>',
  book: '<path d="M4.4 4.6h4.8a3 3 0 0 1 3 3v11.8a2.4 2.4 0 0 0-2.4-2.4H4.4z"/><path d="M19.6 4.6h-4.8a3 3 0 0 0-3 3v11.8a2.4 2.4 0 0 1 2.4-2.4h5.4z"/>'
};

/* 取图标：白名单未命中时退回 search，保证永远有可见图标而不是空白 */
function icon(name, cls) {
  var body = ICONS[name] || ICONS.search;
  return '<svg class="' + (cls || 'icon-svg') + '" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
    + ' stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + body + '</svg>';
}

/* ═══════ 数字与空态格式化 ═══════
   fmtNum / compactNum / emptyState 同时被首屏指标卡、sparkline 和图表用到，
   所以留在 core；图表专用的小工具（dimLabel / dimColor / chartEmpty）跟着
   图表分块走，见 public/app.charts.js。 */

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
/* 统一空态（图标 + 标题 + 说明），替代各处纯文字提示；结构见 .empty-state。
   图标入参是 ICONS 白名单里的名字而不是字符——见上面图标集的理由。 */
function emptyState(iconName, title, desc) {
  return '<div class="empty-state" role="status">'
    + '<div class="empty-icon">' + icon(iconName) + '</div>'
    + '<div class="empty-title">' + h(title) + '</div>'
    + (desc ? '<div class="empty-desc">' + h(desc) + '</div>' : '')
    + '</div>';
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

/* 智能查询面板的语言刷新：runAnalyze 留在 core 里，所以这条由 core 自己注册。
   没有 _lastQuery 说明从没问过，不必发请求。 */
onLangRefresh('nlq', function refreshNlqLang() {
  if (!window._lastQuery) return;
  var qi = document.getElementById('nlqInput');
  if (qi) { qi.value = window._lastQuery; runAnalyze(); }
}, function () { return !!window._lastQuery; });

/* 切换语言后刷新依赖接口的动态区域。
   指标卡 / 洞察 / 数据规模是三块**常驻**内容（排在 tab 面板下方、不随 tab 隐藏），
   任何语言下都要重取。其余只看当前激活的那一个面板，外加「真的生成过内容」的其它
   面板——上一版无条件把指标总表、公报、自定义分析、图表全刷一遍，为看不见的
   面板白发五六个请求。 */
function refreshLang() {
  loadOverview();
  loadInsights();
  loadDbStats();
  var id = activeTabId();
  var cur = LANG_HOOKS[id];
  if (cur) cur.refresh();
  Object.keys(LANG_HOOKS).forEach(function (k) {
    if (k === id) return;
    var h = LANG_HOOKS[k];
    if (h.hasCache()) h.refresh();
  });
  updateShareUrl();
  // 主题按钮图标之外的文案、快捷键帮助内容随语言重渲染
  themeApply(themeMode());
  var shEl = document.getElementById('shortcuts');
  if (shEl && !shEl.hidden && typeof renderHelp === 'function') renderHelp();
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
  auto:  { icon: 'theme', zh: '跟随系统', en: 'Match system', key: '跟随系统' },
  light: { icon: 'sun',    zh: '浅色',   en: 'Light',        key: '浅色模式' },
  dark:  { icon: 'moon',   zh: '深色',   en: 'Dark',         key: '深色模式' }
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
    /* 图标也是 ICONS 里的 SVG（与空态/命令面板同一套）：textContent 会把它当纯文本
       显示成标签源码，必须走 innerHTML。 */
    btn.innerHTML = icon(meta.icon);
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

/* ───── 初始化：先主题（同步，防闪白），再增强能力（独立分块） ─────
   initTheme 必须同步跑：<head> 里的防闪白脚本只落下 data-theme，按钮图标与
   aria-label 要靠它补齐，晚一个任务循环就会出现「深色页面 + 浅色图标」。

   同时它必须放在所有 const 声明之后：THEME_KEY / THEME_ORDER / THEME_META
   在本文件下方，const 的绑定虽被提升但处于暂时死区——早把这行搬进上面的
   init() 里，一执行就抛 ReferenceError，又被 try/catch 静默吞掉：主题切换
   全部失效而页面毫无异常。tests/frontend_behavior.mjs 的「加载即同步主题
   按钮 / 落地 data-theme」守着这个顺序。

   快捷键与命令面板搬到了 app.palette.js：首屏用不到，主体渲染完之后再拉，
   不占首访载荷；分块自己负责初始化自己。 */
try {
  initTheme();
} catch (e) {
  console.error('主题初始化失败', e);
}

loadChunk('palette');