/* Tab 切换 */
document.querySelectorAll('.wb-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.wb-tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.wb-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-' + btn.dataset.tab).classList.add('active');
  });
});

function switchTab(tabId) {
  document.querySelectorAll('.wb-tab').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tabId);
  });
  document.querySelectorAll('.wb-panel').forEach(p => {
    p.classList.toggle('active', p.id === 'panel-' + tabId);
  });
}

/* 年份同步 */
function syncYear(year) { showToast('数据年份已切换为 ' + year + '年', 'success'); }

/* 快捷查询 */
function fillQuery(text) {
  switchTab('nlq');
  document.getElementById('nlqInput').value = text;
  document.getElementById('nlqInput').focus();
}

/* Loading + Toast */
function simulateLoading(btnId, callback) {
  if (btnId) {
    var btn = document.getElementById(btnId);
    if (btn) { btn.classList.add('loading'); }
  }
  setTimeout(() => {
    if (btnId) {
      var btn = document.getElementById(btnId);
      if (btn) btn.classList.remove('loading');
    }
    if (callback) callback();
  }, 1200);
}

function runAnalyze() {
  var input = document.getElementById('nlqInput').value.trim();
  if (!input) { showToast('请先输入查询问题', 'error'); return; }
  simulateLoading('btnAnalyze', () => {
    showToast('分析完成', 'success');
  });
}

function runCustom() {
  var select = document.querySelector('#panel-custom select');
  if (!select.value) { showToast('请先选择一个分析', 'error'); return; }
  simulateLoading('btnRunCustom', () => {
    document.getElementById('customEmpty').innerHTML = '<div style="padding:16px;background:var(--green-50);border-radius:var(--radius-md);border:1px solid #A7F3D0;font-size:13px;color:var(--gray-700)"><strong style="color:var(--green-600)">✅ 分析完成</strong> — 「' + select.value + '」已执行</div>';
  });
}

function createFromSelected() {
  var checked = document.querySelectorAll('.data-table tbody .cb.checked');
  if (checked.length === 0) { showToast('请先勾选至少一个指标', 'error'); return; }
  showToast('已用 ' + checked.length + ' 个指标创建分析', 'success');
}

/* Checkbox */
document.querySelectorAll('.cb').forEach(cb => {
  cb.addEventListener('click', (e) => { e.stopPropagation(); cb.classList.toggle('checked'); });
});

function toggleAll(el) {
  el.classList.toggle('checked');
  var isChecked = el.classList.contains('checked');
  document.querySelectorAll('.data-table tbody .cb').forEach(cb => {
    cb.classList.toggle('checked', isChecked);
  });
}

/* Toast */
function showToast(msg, type) {
  var toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = 'toast show' + (type ? ' ' + type : '');
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => { toast.className = 'toast'; }, 2200);
}

/* 侧边栏卡片折叠/展开 */
function toggleSidebarCard(headerEl) {
  var card = headerEl.closest('.side-card');
  card.classList.toggle('collapsed');
}
