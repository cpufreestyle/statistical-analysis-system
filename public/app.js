/* ============================================
   全国统计分析系统 · 前端逻辑
   对接真实 Flask API（/api/overview, /api/ask, /api/indicators, /api/custom）
   ============================================ */

const API = '';

/* ───── 页面入口 ───── */
(function init() {
  // Tab 切换
  document.querySelectorAll('.wb-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.wb-tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.wb-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const panel = document.getElementById('panel-' + btn.dataset.tab);
      if (panel) { panel.classList.add('active'); btn.dataset.tab === 'indicators' && loadIndicators(); }
    });
  });
  // Radio (单选)
  document.querySelectorAll('.selrow').forEach(cb => {
    cb.addEventListener('click', (e) => { e.stopPropagation(); });
  });
  // 页面加载
  loadOverview();
  loadCustomList();
  loadIndicators();
})();

/* ───── 年份同步 ───── */
function syncYear(y) {
  const s = document.getElementById('globalYear');
  if (s) s.value = y;
  loadOverview();
  loadIndicators();
  showToast(tr('年份已切换至') + ' ' + y + (window.CUR_LANG === 'zh' ? '年' : ''), 'success');
}

/* ───── Tab 切换（来自快捷按钮） ───── */
function switchTab(tabId) {
  document.querySelectorAll('.wb-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
  document.querySelectorAll('.wb-panel').forEach(p => p.classList.toggle('active', p.id === 'panel-' + tabId));
  if (tabId === 'indicators') loadIndicators();
}

/* ───── 快捷查询 ───── */
function fillQuery(text) { switchTab('nlq'); document.getElementById('nlqInput').value = text; document.getElementById('nlqInput').focus(); }

/* ═══════ 关键指标卡片 ═══════ */
async function loadOverview() {
  const y = document.getElementById('globalYear')?.value || '2024';
  const grid = document.getElementById('metricsGrid');
  if (!grid) return;
  try {
    const r = await fetch(API + '/api/overview?year=' + y);
    const d = await r.json();
    grid.innerHTML = (d.cards || []).map(c => `
      <div class="metric-card">
        <div class="metric-header"><span class="metric-label">${h(tr(c.label))}</span><span class="metric-tag">${y}${window.CUR_LANG === 'zh' ? '年' : ''}</span></div>
        <div class="metric-value">${h(c.value)}<span class="metric-unit"></span></div>
        <div class="metric-footer"><span class="metric-change">${h(trData(c.sub || ''))}</span></div>
      </div>`).join('');
  } catch (e) { grid.innerHTML = '<div class="metric-card" style="grid-column:1/-1;color:var(--gray-400)">' + tr('加载失败') + '</div>'; }
}

/* ═══════ 智能查询 ═══════ */
async function runAnalyze() {
  var input = document.getElementById('nlqInput').value.trim();
  if (!input) { showToast(tr('请先输入查询问题'), 'error'); return; }
  window._lastQuery = input;
  var btn = document.getElementById('btnAnalyze'); btn.classList.add('loading');
  var el = document.getElementById('nlqResult'); el.innerHTML = '<div class="skeleton skeleton-line" style="width:60%"></div><div class="skeleton skeleton-line" style="width:40%"></div>';
  try {
    var r = await fetch(API + '/api/ask?text=' + encodeURIComponent(input));
    var d = await r.json();
    var html = renderAsk(d);
    var ref = d['知识库参考'];
    if (ref) html += '<div class="kb-ref"><b>' + tr('知识库参考') + '：</b>' + h(ref) + '</div>';
    el.innerHTML = html || '(' + tr('无结果') + ')';
    showToast(tr('分析完成'), 'success');
  } catch (e) { el.innerHTML = '<div style=color:var(--red-500)>' + tr('请求失败') + '：' + h(e) + '</div>'; showToast(tr('请求失败'), 'error'); }
  finally { btn.classList.remove('loading'); }
}

function renderAsk(d) {
  if (!d || typeof d !== 'object') return String(d);
  var html = '';
  var sep = window.CUR_LANG === 'zh' ? '：' : ': ';
  var jsep = window.CUR_LANG === 'zh' ? '； ' : '; ';
  var lsep = window.CUR_LANG === 'zh' ? '、' : ', ';
  for (var k in d) { if (k === '知识库参考') continue;
    var v = d[k];
    var kk = tr(k);
    if (Array.isArray(v) && v.length) {
      html += '<div class="rk"><b>' + kk + '</b>';
      if (typeof v[0] === 'object') {
        var keys = Object.keys(v[0]);
        html += '<table class="rkt"><thead><tr>' + keys.map(c => '<th>' + tr(c) + '</th>').join('') + '</tr></thead><tbody>'
          + v.map(r => '<tr>' + keys.map(c => '<td>' + tv(r[c] ?? '') + '</td>').join('') + '</tr>').join('') + '</tbody></table>';
      } else { html += '<div>' + v.map(tv).join(lsep) + '</div>'; }
      html += '</div>';
    } else if (v && typeof v === 'object' && !Array.isArray(v)) {
      html += '<div class="rk"><b>' + kk + '</b><div class="rki">' + Object.entries(v).map(function(e) { return tr(e[0]) + sep + tv(e[1]); }).join(jsep) + '</div></div>';
    } else {
      html += '<div class="rk"><b>' + kk + '</b>' + sep + tv(v ?? '—') + '</div>';
    }
  }
  return html;
}

/* ═══════ 指标总表 ═══════ */
async function loadIndicators() {
  var y = document.getElementById('globalYear')?.value || '2024';
  var cat = (document.getElementById('indCat')?.value || '');
  var q = (document.getElementById('indSearch')?.value || '').trim();
  var u = API + '/api/indicators?year=' + y + (cat ? '&category=' + encodeURIComponent(cat) : '') + (q ? '&q=' + encodeURIComponent(q) : '');
  var tb = document.querySelector('#indTable tbody');
  if (!tb) return;
  try {
    var r = await fetch(u); var rows = await r.json();
    document.getElementById('indCount').textContent = rows.length ? rows.length + (window.CUR_LANG === 'zh' ? ' 条' : ' rows') : '';
    if (!rows.length) { tb.innerHTML = '<tr><td colspan=8 style="color:var(--gray-400)">无数据</td></tr>'; return; }
    tb.innerHTML = rows.map(function(r) { return '<tr>'
      + '<td><input type=radio name=selrow class=selrow data-c="' + a(r.category) + '" data-i="' + a(r.indicator) + '" data-d="' + a(r.dimension) + '" onclick="toggleCb(this,event)"></td>'
      + '<td class="ind-name" title="' + a(r.note || '') + '">' + h(tr(r.indicator)) + '</td>'
      + '<td><span class="tag tag-blue">' + h(tr(r.category)) + '</span></td>'
      + '<td>' + h(tr(r.dimension)) + '</td>'
      + '<td class="num">' + (r.value !== null && r.value !== undefined ? r.value.toLocaleString() : '—') + '</td>'
      + '<td>' + h(tr(r.unit || '')) + '</td>'
      + '<td class="note-cell" style="color:var(--gray-400)" title="' + a(r.note || '') + '">' + h(r.note || '') + '</td>'
      + '</tr>'; }).join('');

  } catch (e) { tb.innerHTML = '<tr><td colspan=8 style="color:var(--red-500)">' + tr('加载失败') + '</td></tr>'; }
}

function toggleCb(el, ev) { ev.stopPropagation(); var all=document.querySelectorAll('#indTable .selrow'); all.forEach(function(r){r.checked=false}); el.checked=true; }
function toggleAll(el) { document.querySelectorAll('#indTable .selrow').forEach(function(r){r.checked=false}); }

function createFromSelected() {
  var sel = document.querySelector('#indTable .selrow:checked');
  if (!sel) { showToast('请先选中一个指标', 'error'); return; }
  switchTab('custom');
  openAddCustom();
  var vr = document.getElementById('varRows'); vr.innerHTML = '';
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
    var r = await fetch(API + '/api/custom');
    var list = await r.json();
    var sel = document.getElementById('customSelect');
    if (!sel) return;
    sel.innerHTML = '<option value="">' + tr('选择已有分析…') + '</option>' + list.map(function(a) { return '<option value="' + a.name + '">' + h(a.name) + (a.description ? ' — ' + h(a.description) : '') + '</option>'; }).join('');
  } catch (e) { /* 忽略 */ }
}

async function runCustom() {
  var sel = document.getElementById('customSelect');
  if (!sel || !sel.value) { showToast(tr('请先选择一个分析'), 'error'); return; }
  window._lastCustom = sel.value;
  var y = document.getElementById('globalYear')?.value || '2024';
  var btn = document.getElementById('btnRunCustom'); btn.classList.add('loading');
  var el = document.getElementById('customResult');
  try {
    var r = await fetch(API + '/api/custom?name=' + encodeURIComponent(sel.value) + '&year=' + y);
    var d = await r.json();
    if (d.error) { el.innerHTML = '<div class="rk" style="color:var(--red-500)">' + h(d.error) + '</div>'; return; }
    el.innerHTML = '<div class="custom-card">'
      + '<div class="custom-value">' + (d.value !== undefined ? d.value.toLocaleString() : '—') + (d.unit ? ' <span class="custom-unit">' + h(tr(d.unit)) + '</span>' : '') + '</div>'
      + (d.yoy !== undefined ? '<div class="custom-yoy ' + (d.yoy >= 0 ? 'up' : 'down') + '">' + (d.yoy >= 0 ? '▲' : '▼') + ' ' + tr('同比') + ' ' + d.yoy + '%</div>' : '')
      + (d.expr ? '<div class="custom-expr">' + (window.CUR_LANG === 'zh' ? '公式：' : 'Expr: ') + h(d.expr) + '</div>' : '')
      + '</div>';
    showToast(tr('分析完成'), 'success');
  } catch (e) { el.innerHTML = '<div style="color:var(--red-500)">请求失败</div>'; }
  finally { btn.classList.remove('loading'); }
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
  var vars = [].map.call(document.querySelectorAll('#varRows .vname'), function(i) { return i.value.trim(); }).filter(Boolean);
  var a = vars[0] || 'x', b = vars[1] || 'y';
  var map = { share: a + ' / ' + b + ' * 100', diff: a + ' - ' + b, ratio: a + ' / ' + b, sum: a + ' + ' + b };
  document.getElementById('customExpr').value = map[kind] || '';
}

async function saveCustom() {
  var name = document.getElementById('customName').value.trim();
  var expr = document.getElementById('customExpr').value.trim();
  if (!name || !expr) { showToast(tr('名称和表达式必填'), 'error'); return; }
  var vars = {};
  var valid = true;
  document.querySelectorAll('#varRows .var-row').forEach(function(row) {
    var vn = row.querySelector('.vname').value.trim();
    var vc = row.querySelector('.vcat').value.trim();
    var vi = row.querySelector('.vind').value.trim();
    if (!vn || !vc || !vi) { valid = false; return; }
    vars[vn] = [vc, vi];
  });
  if (!valid || Object.keys(vars).length === 0) { showToast(tr('请至少填一个有效变量（名称/专业/指标）'), 'error'); return; }
  var body = { name: name, expr: expr, unit: document.getElementById('customUnit').value.trim(),
    description: document.getElementById('customDesc').value.trim(), compare: document.getElementById('customCmp').checked, variables: vars };
  try {
    var r = await fetch(API + '/api/custom', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    var d = await r.json();
    if (d.ok) { showToast((window.CUR_LANG === 'zh' ? '已保存「' + name + '」' : 'Saved "' + name + '"'), 'success'); closeAddCustom(); loadCustomList(); }
    else { showToast(d.error || tr('保存失败'), 'error'); }
  } catch (e) { showToast(tr('保存失败') + '：' + e, 'error'); }
}

/* ═══════ 工具函数 ═══════ */
function h(s) { return (s == null ? '' : String(s)).replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function a(s) { return (s == null ? '' : String(s)).replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
/* 翻译结果里的「值」：字符串才处理，先精确匹配再组合串替换 */
function tv(v) {
  if (typeof v !== 'string') return v;
  var t = tr(v);
  return t !== v ? t : trData(v);
}

/* ═══════ Toast ═══════ */
function showToast(msg, type) {
  var toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = 'toast show' + (type ? ' ' + type : '');
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(function() { toast.className = 'toast'; }, 2200);
}

/* 切换语言后刷新依赖接口的动态区域（卡片 / 指标表 / 自定义列表） */
function refreshLang() {
  loadOverview();
  loadIndicators();
  // 已展示过的分析结果按新语言重跑，避免结果面板停留在旧语言
  if (window._lastQuery) {
    var qi = document.getElementById('nlqInput');
    if (qi) { qi.value = window._lastQuery; runAnalyze(); }
  }
  // 自定义分析需等下拉选项重载后再回填并运行
  loadCustomList().then(function () {
    if (!window._lastCustom) return;
    var cs = document.getElementById('customSelect');
    if (cs) { cs.value = window._lastCustom; runCustom(); }
  });
  // 年份下拉文案与副标题已在 applyLang 内处理
}

/* ═══════ 侧边栏卡片折叠 ═══════ */
function toggleSidebarCard(headerEl) {
  var card = headerEl.closest('.side-card');
  card.classList.toggle('collapsed');
}
