/* ═══════ 增强能力分块（app.palette.js） ═══════
   命令面板（Ctrl/⌘+K）+ 全局快捷键 + 帮助浮层。core 在主体初始化完之后调用
   loadChunk('palette') 拉取本文件，然后由本文件自己完成初始化——core 末尾只负责
   把文件拉下来，不关心里面怎么初始化。

   首屏（智能查询）用不到这些能力，所以这不占首访载荷；用户按第一个快捷键之前
   文件早已就位。失败时 console.error 留痕，不会静默变成「快捷键全失效」。

   本文件可以直接引用 core 的 const 与函数（STATE / TAB_IDS / switchTab …）。 */

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
    { id: 'nlq', icon: 'message', key: '智能查询' },
    { id: 'indicators', icon: 'table', key: '指标总表' },
    { id: 'custom', icon: 'calculator', key: '自定义分析' },
    { id: 'bulletin', icon: 'filetext', key: '统计公报' },
    { id: 'charts', icon: 'linechart', key: '图表' }
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
      group: tr('切换年份'), icon: 'calendar', label: y + (isZh() ? '年' : ''),
      hint: y === STATE.year ? '✓' : '', keywords: 'year ' + y,
      run: function () { syncYear(y); }
    });
  });
  (window._dimOptions || []).forEach(function (o) {
    var key = o.key || o.slug;
    if (!key) return;
    cmds.push({
      group: tr('切换经济体'), icon: 'globe', label: o.label || key,
      keywords: 'dimension economy ' + key + ' ' + (o.slug || ''),
      hint: key === STATE.dimension ? '✓' : '',
      run: function () { syncDimension(key); }
    });
  });
  cmds.push({ group: tr('外观'), icon: 'theme', label: tr('切换主题'),
    hint: tr(THEME_META[themeMode()].key), keywords: 'theme dark light auto', run: cycleTheme });
  cmds.push({ group: tr('外观'), icon: 'translate', label: tr('切换语言'),
    hint: isZh() ? '中文 → EN' : 'EN → 中文', keywords: 'language lang', run: function () { toggleLang(); } });
  cmds.push({ group: tr('操作'), icon: 'link', label: tr('复制分享链接'), keywords: 'share link copy', run: copyShareLink });
  /* 导出指标 CSV 的实现在指标总分块里：不能在 paletteCommands() 执行时就地引用
     ——那时分块还没加载，裸引用会 ReferenceError，命令面板自己先打不开。
     改为按名字延迟解析，tabAction 会先把分块拉下来再跑。 */
  cmds.push({ group: tr('操作'), icon: 'download', label: tr('导出指标 CSV'), keywords: 'export csv download',
    run: function () { tabAction('indicators', 'exportIndicatorsCsv'); } });
  cmds.push({ group: tr('操作'), icon: 'download', label: tr('导出当前指标 CSV'), keywords: 'export csv chart indicator', run: exportChartCsv });
  /* 同理：loadBulletin() 在统计公报分块里。switchTab 的返回值就是分块加载
     任务，等它兑现后再按名字解析执行，分块没加载时运行命令也不会 ReferenceError。 */
  cmds.push({ group: tr('操作'), icon: 'filetext', label: tr('生成统计公报'), keywords: 'bulletin report',
    run: function () { switchTab('bulletin').then(function () { tabAction('bulletin', 'loadBulletin'); }); } });
  cmds.push({ group: tr('操作'), icon: 'keyboard', label: tr('键盘快捷键'), hint: '?',
    keywords: 'shortcuts help keyboard', run: openShortcuts });
  Array.prototype.slice.call(document.querySelectorAll('.suggestion-chip')).forEach(function (el) {
    var q = pickQ(el);
    if (!q) return;
    cmds.push({ group: tr('示例问题'), icon: 'message', label: q, keywords: 'ask ' + q,
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
      + '<span class="pi-icon" aria-hidden="true">' + icon(c.icon) + '</span>'
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

/* ───── 分块自带初始化：core 只负责拉文件，初始化在这里做 ───── */
try {
  initShortcuts();
  initPalette();
} catch (e) {
  console.error('增强能力初始化失败（快捷键/命令面板会不可用）', e);
}
