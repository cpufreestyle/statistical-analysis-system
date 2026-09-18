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
  loadOverview();
  loadCustomList();
  loadDbStats();
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
  updateShareUrl();
  showToast(tr('年份已切换至') + ' ' + STATE.year + (isZh() ? '年' : ''), 'success');
}

function syncDimension(d) {
  STATE.dimension = d;
  const gd = document.getElementById('globalDimension');
  if (gd) gd.value = d;
  loadOverview();
  loadIndicators();
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

    grid.removeAttribute('aria-busy');
    // 卡片字段全部来自服务端本地化结果，前端不再做数据词条替换
    if (!(d.cards || []).length) {
      grid.innerHTML = '<div class="metric-card" style="grid-column:1/-1;color:var(--gray-400);text-align:center">' + h(tr('该维度暂无数据')) + '</div>';
      return;
    }
    grid.innerHTML = (d.cards || []).map(c => `
      <div class="metric-card">
        <div class="metric-header">
          <span class="metric-label">${h(c.label)}</span>
          <span class="metric-tag">${h(c.dimension || '')}</span>
        </div>
        <div class="metric-value">${h(c.value)}<span class="metric-unit">${h(c.unit || '')}</span></div>
        <div class="metric-footer">
          ${c.yoy ? `<span class="metric-change">${h(tr('同比'))} ${h(c.yoy)}</span>` : ''}
        </div>
        <div class="metric-src" title="${a(c.note || '')}">${h(c.note || '')}</div>
      </div>`).join('');
  } catch (e) {
    grid.removeAttribute('aria-busy');
    grid.innerHTML = '<div class="metric-card" style="grid-column:1/-1;color:var(--gray-400)">' + tr('加载失败') + '</div>';
  }
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
  try {
    var r = await fetch(u);
    var rows = await r.json();
    var cnt = document.getElementById('indCount');
    if (cnt) cnt.textContent = rows.length ? rows.length + (isZh() ? ' 条' : ' rows') : '';
    if (!rows.length) {
      tb.innerHTML = '<tr><td colspan="7" style="color:var(--gray-400)">' + tr('无可展示数据') + '</td></tr>';
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
      + '<td class="note-cell" style="color:var(--gray-400)" title="' + a(r.note || '') + '">' + h(r.note || '') + '</td>'
      + '</tr>'; }).join('');
  } catch (e) {
    tb.innerHTML = '<tr><td colspan="7" style="color:var(--red-500)">' + tr('加载失败') + '</td></tr>';
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
  try {
    var r = await fetch(API + '/api/custom?name=' + enc(sel.value) + '&year=' + enc(STATE.year) + '&' + langQ());
    var d = await r.json();
    if (d.error) {
      el.innerHTML = '<div class="rk" style="color:var(--red-500)">' + h(d.error) + '</div>';
      return;
    }
    el.innerHTML = '<div class="custom-card">'
      + '<div class="custom-value">' + (d.value !== undefined && d.value !== null ? Number(d.value).toLocaleString() : '—')
      + (d.unit ? ' <span class="custom-unit">' + h(tr(d.unit)) + '</span>' : '') + '</div>'
      + (d.yoy !== undefined ? '<div class="custom-yoy ' + (d.yoy >= 0 ? 'up' : 'down') + '">'
          + (d.yoy >= 0 ? '▲' : '▼') + ' ' + tr('同比') + ' ' + d.yoy + '%</div>' : '')
      + (d.expr ? '<div class="custom-expr">' + tr('公式：') + h(d.expr) + '</div>' : '')
      + '</div>';
    showToast(tr('分析完成'), 'success');
  } catch (e) {
    el.innerHTML = '<div style="color:var(--red-500)">' + tr('请求失败') + '</div>';
  } finally {
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
  toast.textContent = msg;
  toast.className = 'toast show' + (type ? ' ' + type : '');
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(function () { toast.className = 'toast'; }, 2600);
}

/* 切换语言后刷新依赖接口的动态区域 */
function refreshLang() {
  loadOverview();
  loadIndicators();
  loadDbStats();
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
}

/* ═══════ 侧边栏卡片折叠 ═══════ */
function toggleSidebarCard(headerEl) {
  var card = headerEl.closest('.side-card');
  card.classList.toggle('collapsed');
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

async function loadChartSeries() {
  var sel = document.getElementById('chartIndicator');
  if (!sel || !sel.value) {
    CHART.currentKey = null; CHART.rows = []; CHART.unit = '';
    var cu0 = document.getElementById('chartUnit'); if (cu0) cu0.textContent = '';
    renderCharts(); return;
  }
  CHART.currentKey = sel.value;
  updateShareUrl();
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
function chartEmpty(msg) { return '<div class="chart-empty" role="status">' + h(msg) + '</div>'; }
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
  if (!CHART.currentKey) { box.innerHTML = chartEmpty(tr('请先选择指标')); return; }
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
  if (years.length < 2) { box.innerHTML = chartEmpty(tr('需至少两个年份才能绘制趋势线')); return; }
  if (!active.length) { box.innerHTML = chartEmpty(tr('该指标在所选经济体无数据')); return; }

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
    svg += '<text x="' + (mL - 10) + '" y="' + (ty + 4) + '" text-anchor="end" font-size="12" fill="var(--gray-400)" font-family="' + ff + '">' + h(fmtNum(Math.round(tv * 100) / 100)) + '</text>';
  }
  years.forEach(function (y, i) {
    svg += '<text x="' + xFor(i) + '" y="' + (H - 12) + '" text-anchor="middle" font-size="12" fill="var(--gray-400)" font-family="' + ff + '">' + h(y) + '</text>';
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
  svg += '</svg>';
  /* 图例对屏幕阅读器隐藏：经济体与数值的对应关系已写进上面的 <desc>，
     重复播报只会增加噪音（视觉用户仍可正常看到色块）。 */
  var legend = '<div class="chart-legend" aria-hidden="true">' + active.map(function (d) {
    return '<span class="lg-item"><i style="background:' + dimColor(d) + '"></i>' + h(dimLabel(d)) + '</span>';
  }).join('') + '</div>';
  box.innerHTML = svg + legend;
}

/* 排名条形图：所选年份分经济体排名 */
function renderRank() {
  var box = document.getElementById('rankChart');
  if (!box) return;
  if (!CHART.currentKey) { box.innerHTML = chartEmpty(tr('请先选择指标')); return; }
  var yr = (document.getElementById('chartYear') || {}).value;
  var rows = CHART.rows.filter(function (r) {
    return String(r.year) === String(yr) && r.value != null && r.value !== '';
  });
  if (!rows.length) { box.innerHTML = chartEmpty(tr('该指标在所选年份无数据')); return; }
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
    svg += '<text x="' + (labelW - 8) + '" y="' + (y + 17) + '" text-anchor="end" font-size="12" fill="var(--gray-600)" font-family="' + ff + '">' + h(label) + '</text>';
    svg += '<rect x="' + barX + '" y="' + (y + 5) + '" width="' + bw + '" height="18" rx="4" fill="' + color + '"/>';
    svg += '<text x="' + (barX + bw + 8) + '" y="' + (y + 17) + '" font-size="12" fill="var(--gray-700)" font-family="' + ff + '" font-weight="600">' + h(fmtNum(r.value)) + '</text>';
  });
  svg += '</svg>';
  box.innerHTML = svg;
}
