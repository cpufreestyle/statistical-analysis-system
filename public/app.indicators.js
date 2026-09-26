/* ═══════ 指标总表分块（app.indicators.js） ═══════
   由 core 的 loadChunk('indicators') 在用户第一次打开「指标总表」tab 时动态拉取。
   首屏（智能查询）用不到它，所以这不占首访载荷。

   这里可以直接引用 core 的 const 与函数（STATE / API / h() / tr() / emptyState …）：
   经典 <script> 共享同一个全局词法环境，不需要模块打包器。反过来，core 不引用本文件
   里的任何东西，入口只有 openTab() 与语言切换钩子——所以本文件加载失败时，首屏与
   其它 tab 完全不受影响。

   syncYear / syncDimension / fillSelect 留在 core：侧栏顶部的全局筛选与命令面板
   都在用它们，而它们是首屏能力、不等本分块加载。 */
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
      tb.innerHTML = '<tr><td colspan="7">' + emptyState('inbox', tr('无可展示数据'),
        tr('换个专业分类或关键词试试，也可清除筛选查看全部指标')) + '</td></tr>';
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
  /* openAddCustom() 在自定义分析分块里，这里不直接调——分块之间一旦互相引用，
     先打开的面板就会把后一个分块也拖下来，懒加载名存实亡。
     改为把选择暂存到 window 上，switchTab('custom') → openTab('custom') 拉完
     分块后由那边的 initCustom() 取走并回填表单。 */
  window._customFromIndicator = {
    cat: sel.dataset.c || '', ind: sel.dataset.i || '', dim: sel.dataset.d || ''
  };
  switchTab('custom');
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
/* ───── 语言切换 ─────
   core 的 refreshLang() 按当前激活的面板挑一条钩子调用（core 不点名本文件的函数）。
   列表是服务端按 lang 本地化的，切语言必须重取。 */
onLangRefresh('indicators', loadIndicators);
