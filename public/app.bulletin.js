/* ═══════ 统计公报分块（app.bulletin.js） ═══════
   由 core 的 loadChunk('bulletin') 在用户第一次打开「统计公报」tab 时动态拉取。
   内容按「生成公报」按钮按需生成，所以本分块不在首访载荷里。

   与另两个分块同一套约定：可以直接引用 core 的 STATE / API / h() / a() / tr() /
   mdToHtml()，而 core 不引用本文件里的任何东西。 */
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
      var aiBadge = d.ai_cached
        ? ' <span class="cache-badge" title="' + a(tr('同一问题与同一份数据')) + '">⚡ '
          + h(tr('来自缓存')) + '</span>'
        : '';
      html += '<div class="ai-card"><div class="ai-head">🤖 ' + tr('AI 云端解读') + aiBadge + '</div>'
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
/* ───── 语言切换 ─────
   公报由服务端按 lang 本地化（缓存的是上一语言的文本），所以只有生成过才重取。 */
onLangRefresh('bulletin', function () { if (window._lastBulletin) loadBulletin(); },
              function () { return !!window._lastBulletin; });
