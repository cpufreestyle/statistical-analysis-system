/* ═══════ 图表分块（app.charts.js） ═══════
   由 core 的 loadChunk('charts') 在用户第一次打开「图表」tab 时动态拉取。
   首屏（智能查询）用不到图表，所以这不占首访载荷。

   这里可以直接引用 core 的 const 与函数（STATE / API / THEME_* / fmtNum …）：
   经典 <script> 共享同一个全局词法环境，不需要模块打包器。反过来，core 不引用
   本文件里的任何东西——所以本文件加载失败时，首屏与其它 tab 完全不受影响。

   图表自绘 SVG，无图表库依赖；配色引用 style.css 的 --ch-* 令牌，深色模式自动
   换成亮色，不写死十六进制值。 */

/* ═══════ 图表（自绘 SVG，无图表库依赖） ═══════ */
/* 图表状态 CHART / 色板 CHART_COLORS 定义在 core（public/app.js）：分享链接的
   updateShareUrl() 与「导出当前指标 CSV」的 exportChartCsv() 都要读
   CHART.currentKey / CHART.selDims，而它们是 core 的能力、不等图表分块加载。
   var 声明挂到全局对象上，所以本分块照样能读写同一个对象。 */

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
    svg += '<text class="svg-num" x="' + (mL - 10) + '" y="' + (ty + 4) + '" text-anchor="end" font-size="12" fill="var(--gray-500)" font-family="' + ff + '">' + h(fmtNum(Math.round(tv * 100) / 100)) + '</text>';
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
    svg += '<text class="svg-num" x="' + (barX + bw + 8) + '" y="' + (y + 17) + '" font-size="12" fill="var(--gray-700)" font-family="' + ff + '" font-weight="600">' + h(fmtNum(r.value)) + '</text>'
      + '</g>';
  });
  svg += '</svg>';
  box.innerHTML = svg;
  attachRankTip(box, rows, CHART.unit);
}
