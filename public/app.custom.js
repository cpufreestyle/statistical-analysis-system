/* ═══════ 自定义分析分块（app.custom.js） ═══════
   由 core 的 loadChunk('custom') 在用户第一次打开「自定义分析」tab 时动态拉取，
   首访载荷里没有它。

   与另两个分块同一套约定：可以直接引用 core 的 STATE / API / h() / a() / tr() /
   compactNum() / showToast() / langQ() / switchTab()，而 core 不引用本文件里的任何
   东西，入口只有 openTab('custom') 回调里的 initCustom() 与语言切换钩子。 */
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
/* ───── 打开本面板时由 core 的 openTab('custom') 调用 ─────
   两件事：灌一次「选择已有分析」下拉；以及消费从指标总表带过来的待建分析
   （window._customFromIndicator，由那里的 createFromSelected() 暂存）。
   走 window 而不是直接调指标分块的函数，同理——分块之间不互相引用。 */
function initCustom() {
  var pend = window._customFromIndicator;
  if (pend) {
    window._customFromIndicator = null;
    openAddCustom();
    var vr = document.getElementById('varRows');
    if (vr) {
      vr.innerHTML = '';
      addVarRow();
      var row = vr.lastElementChild;
      if (row) {
        row.querySelector('.vname').value = 'x';
        row.querySelector('.vcat').value = pend.cat || '';
        row.querySelector('.vind').value = pend.ind || '';
        row.querySelector('.vdim').value = pend.dim || '';
      }
    }
    var msg = document.getElementById('caddMsg');
    if (msg) msg.textContent = tr('已带入所选指标，填好名称与公式即可保存');
  }
  return loadCustomList();
}
/* ───── 语言切换 ─────
   core 的 refreshLang() 按当前激活的面板挑一条钩子调用；下拉要重取，
   若此前跑过一个分析则用同一份选择在新语言下重跑。 */
onLangRefresh('custom', function () {
  loadCustomList().then(function () {
    if (!window._lastCustom) return;
    var cs = document.getElementById('customSelect');
    if (cs) { cs.value = window._lastCustom; runCustom(); }
  });
}, function () { return !!window._lastCustom; });
