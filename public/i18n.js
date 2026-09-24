/* ============================================
   亚太统计分析系统 · 国际化（中 / 英）运行时

   字典与运行时已拆成三个文件（都由 scripts/embed_pages.py 内嵌进 src/pages.py）：
     · public/i18n-dict.js          全量字典，看板 /app 加载；
     · public/i18n-dict-landing.js  落地页子集，/ 加载；
     · 本文件                       只有运行时，不含任何词条。

   为什么拆：全量字典 332 条，而落地页只引用其中 69 条（约 21%）。
   落地页 HTML 的 Cache-Control 是 no-store（每次访问都重下），把整套字典
   塞进它也等于每次访问都白付这笔流量；拆开后落地页只下载自己那 69 条。
   看板不能用子集——它的 trData() 要靠全量词条兜底翻译服务端拼装出来的中文串。

   加载顺序固定为「字典 → 运行时」：本文件在 IIFE 里读 window.ZH2EN，
   所以 i18n-dict*.js 必须排在它前面。该顺序由 tests/test_i18n_split.py 把守。

   翻译策略（两级，不依赖人工维护词表）：
     1) tr(s)     精确字典 → ASCII 结构键表（ASK_KEY_LABELS）→ trData()。
     2) trData(s) 用「字典里所有中文词条（长词优先）」逐个替换，
        兜底服务端新增、前端字典尚未收录的中文拼装串。
   ============================================ */
(function () {
  "use strict";


  /* 字典由同页更早加载的 i18n-dict.js / i18n-dict-landing.js 注入 window.ZH2EN。
     取不到就退化成空字典：宁可漏译，也不能让整页脚本跟着崩。 */
  var ZH2EN = window.ZH2EN || {};
  if (window.CUR_LANG == null) {
    try { window.CUR_LANG = localStorage.getItem("qu_lang_v2") || "en"; }
    catch (e) { window.CUR_LANG = "en"; }
  }

  /* 尽早暴露全局：函数声明会被提升，故此处赋值安全。
     这样即使下方字典/逻辑出现运行时错误，切换按钮依然可用。 */
  window.tr = tr;
  window.trData = trData;
  window.applyLang = applyLang;
  window.toggleLang = toggleLang;
  window.refreshI18nSelects = refreshI18nSelects;


  /* 单字/符号单位：长度 1，需显式列入组合串替换表 */
  var UNIT_TERMS = ["%", "元", "岁"];

  /* 组合串替换词表：直接由字典派生（长词优先），避免手工维护导致漏译。
     排除点号命名的小写 key（page.title / chip.gdp 等，只用于 data-i18n）。 */
  var DATA_TERMS = Object.keys(ZH2EN)
    .filter(function (k) { return k.length >= 2 && !/^[a-z0-9._]+$/.test(k); })
    .concat(UNIT_TERMS)
    .sort(function (a, b) { return b.length - a.length; });

  /* 结构键（服务端 lang=en 时返回的 ASCII 键）-> 英文标签。
     数据词条（指标名/专业/维度/单位）由服务端本地化，这里只管框架键。 */
  var ASK_KEY_LABELS = {
    year: "Year",
    dimension: "Economy",
    matched_indicators: "Matched indicators",
    indicator_overview: "Indicator overview",
    ranking_by_economy: "Ranking by economy",
    indicator: "Indicator",
    indicator_name: "Indicator",
    indicator_value: "Value",
    value: "Value",
    unit: "Unit",
    yoy: "YoY",
    rank: "Rank",
    economy: "Economy",
    note: "Note",
    remark: "Remark",
    kb_reference: "Knowledge base reference",
    ai_interpretation: "AI interpretation",
    value_cny_100m: "Value (100 million CNY)",
    value_usd_100m: "Value (100 million USD)",
    secondary_industry_investment_share: "Investment in secondary industry, share",
    title: "Title",
    source: "Source",
    content: "Content",
    category: "Category",
    sections: "Sections",
    rows: "Rows",
    knowledge: "Knowledge base",
    ai: "AI interpretation",
    ai_note: "Note",
    value_key: "Value",
    unit_key: "Unit"
  };

  /* 用「长词优先」逐个替换组合串中的术语。仅英文模式生效。 */
  function trData(s) {
    if (s == null) return s;
    if (window.CUR_LANG !== "en") return s;
    var out = String(s);
    for (var i = 0; i < DATA_TERMS.length; i++) {
      var k = DATA_TERMS[i];
      if (out.indexOf(k) === -1) continue;
      out = out.split(k).join(ZH2EN[k] != null ? ZH2EN[k] : k);
    }
    return out;
  }

  /* 翻译一段文本：精确字典 → ASCII 结构键 → 组合串替换（未知内容原样返回）。 */
  function tr(s) {
    if (s == null) return s;
    if (window.CUR_LANG !== "en") return s;
    if (ZH2EN[s] !== undefined) return ZH2EN[s];
    if (ASK_KEY_LABELS[s] !== undefined) return ASK_KEY_LABELS[s];
    return trData(s);
  }

  /* 语言相关的下拉框文案（年份后缀、按钮文字）——动态填充后需重新调用 */
  function refreshI18nSelects() {
    var zh = window.CUR_LANG === "zh";
    document.querySelectorAll("#globalYear option").forEach(function (o) {
      o.textContent = o.value + (zh ? "年" : "");
    });
    var sy = document.getElementById("subtitleYear");
    if (sy) {
      var gy = document.getElementById("globalYear");
      if (gy) sy.textContent = gy.value;
    }
    var tb = document.getElementById("langToggle");
    if (tb) tb.textContent = zh ? "EN" : "中文";
  }

  /* 应用语言到整页静态文案 */
  function applyLang(lang) {
    window.CUR_LANG = lang;
    var root = document.documentElement;
    if (root) root.lang = lang === "en" ? "en" : "zh-CN";

    /* 首次应用时把「原始中文」缓存到属性里，切换回中文时用它还原。
       （不能在非英文时不做处理：那样从英文切回中文会残留英文。） */
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var k = el.getAttribute("data-i18n");
      var orig = el.getAttribute("data-i18n-orig");
      if (orig == null) { orig = el.textContent; el.setAttribute("data-i18n-orig", orig); }
      el.textContent = (lang === "en" && ZH2EN[k] != null) ? ZH2EN[k] : orig;
    });
    document.querySelectorAll("[data-i18n-html]").forEach(function (el) {
      var k = el.getAttribute("data-i18n-html");
      var orig = el.getAttribute("data-i18n-orig");
      if (orig == null) { orig = el.innerHTML; el.setAttribute("data-i18n-orig", orig); }
      el.innerHTML = (lang === "en" && ZH2EN[k] != null) ? ZH2EN[k] : orig;
    });
    document.querySelectorAll("[data-i18n-ph]").forEach(function (el) {
      var k = el.getAttribute("data-i18n-ph");
      var orig = el.getAttribute("data-i18n-orig-ph");
      if (orig == null) { orig = el.getAttribute("placeholder") || ""; el.setAttribute("data-i18n-orig-ph", orig); }
      el.setAttribute("placeholder", (lang === "en" && ZH2EN[k] != null) ? ZH2EN[k] : orig);
    });

    refreshI18nSelects();

    try { localStorage.setItem("qu_lang_v2", lang); } catch (e) {}
    window.dispatchEvent(new CustomEvent("langchange", { detail: lang }));
  }

  function toggleLang() {
    applyLang(window.CUR_LANG === "zh" ? "en" : "zh");
    if (typeof window.refreshLang === "function") window.refreshLang();
  }

  document.addEventListener("DOMContentLoaded", function () {
    applyLang(window.CUR_LANG);
  });

})();
