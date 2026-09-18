/* ============================================
   亚太统计分析系统 · 国际化（中 / 英）
   字典以「中文原文」为 key，英文为 value；
   静态文案用 data-i18n / data-i18n-html / data-i18n-ph 标注。

   注意：**数据标识符不再由前端翻译**。指标 / 专业 / 维度 / 单位 / 来源说明
   由服务端按 ?lang= 本地化（见 data/labels.csv 与 src/labels.py），
   接口返回什么就渲染什么；本文件只负责静态 UI 文案与结构键的展示名。

   翻译策略（两级，不依赖人工维护词表）：
     1) tr(s)     精确字典 → ASCII 结构键表（ASK_KEY_LABELS）→ trData()。
     2) trData(s) 用「字典里所有中文词条（长词优先）」逐个替换，
        兜底服务端新增、前端字典尚未收录的中文拼装串。
   ============================================ */
(function () {
  "use strict";

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

  /* ── 中文 → 英文 全量字典 ── */
  var ZH2EN = {
    /* 通用 / 框架 */
    "page.title": "Asia-Pacific Statistical Analysis System",
    "nav.title": "Asia-Pacific Statistics",
    "home.link": "🏠 Home",
    "搜索": "Search",
    "搜索指标、地区、分析主题…": "Search indicators, regions, topics…",
    "仅使用公开数据": "Public Data Only",
    "badge.public": "Public Data Only",
    "跳到主内容": "Skip to content",
    "该维度暂无数据": "No data available for this region",
    "badge.official": "Official Public Data",
    "badge.api": "Powered by InfiniSynapse Server API",

    /* 应用页头 */
    "数据概览": "Data Overview",
    "subtitle.text": " Asia-Pacific Economic Data — Statistics & Analysis",
    "全国统计分析": "Asia-Pacific Statistics",
    "地区/经济体": "Region / Economy",
    "年份": "Year",

    /* 工作台 Tab */
    "🌟 智能查询": "🌟 AI Query",
    "📊 指标总表": "📊 Indicators",
    "📋 自定义分析": "📋 Custom Analysis",
    "📄 统计公报": "📄 Bulletin",

    /* 智能查询 */
    "输入你的分析问题，AI 将基于公开统计数据为你生成分析结果":
      "Ask a question in natural language; the AI answers from official public data.",
    "例如：2024年GDP是多少？":
      "e.g. What was Asia-Pacific GDP in 2024?",
    "📡 开始分析": "📡 Analyze",
    "💡 试试这些问题": "💡 Try these",
    "chip.gdp": "What was 2024 GDP?",
    "chip.retail": "Retail sales",
    "chip.invest": "Fixed asset investment",
    "chip.pop": "Population of Japan",
    "AI 云端解读": "AI Cloud Interpretation",
    "本地统计": "Local stats",
    "注": "Note",
    "AI 解读": "AI Interpretation",
    "task_id": "Task ID",
    "匹配指标": "Matched Indicators",
    "指标概览": "Indicator Overview",
    "指标名": "Indicator",
    "数值": "Value",
    "分经济体排名": "Ranking by Economy",
    "经济体": "Economy",
    "排名": "Rank",
    "知识库参考": "KB Reference",

    /* 指标总表 */
    "勾选指标后点「用所选建分析」可一键带入自定义分析；也可在上方自然语言框直接问具体指标名。":
      "Tick a row then “Build from selection” to reuse it in Custom Analysis — or just ask the AI box above by indicator name.",
    "全部专业": "All Categories",
    "全部维度": "All Regions",
    "国民经济核算": "National Accounts",
    "综合": "National Accounts",
    "工业": "Industry",
    "对外贸易": "Foreign Trade",
    "贸易": "Trade",
    "金融": "Finance",
    "人口与就业": "Population & Employment",
    "人口": "Population",
    "服务业": "Services",
    "农业": "Agriculture",
    "投资": "Investment",
    "关键词搜索指标 / 说明 / 维度": "Search indicator / note / region",
    "🔍 查询": "🔍 Query",
    "用所选指标创建分析": "Build Analysis from Selection",
    "选择": "Select",
    "指标": "Indicator",
    "专业": "Category",
    "维度": "Region",
    "单位": "Unit",
    "说明": "Note",
    "无可展示数据": "No data available",

    /* 自定义分析 */
    "选择已有分析…": "Select an analysis…",
    "运行": "Run",
    "＋ 新建": "＋ New",
    "选择并运行分析": "Select & Run an Analysis",
    "从下拉列表选择一个已有的自定义分析，或点击「新建」创建自己的分析模板":
      "Pick an existing custom analysis, or click “New” to build your own template.",
    "分析名称（必填）": "Analysis name (required)",
    "单位，如 %、亿元": "Unit, e.g. %, CNY 100M",
    "说明（可选）": "Note (optional)",
    "变量绑定": "Variable Binding",
    "变量": "Var",
    "维度（可选）": "Region (opt)",
    "变量名，如 x": "Var name, e.g. x",
    "＋ 增加变量": "＋ Add Variable",
    "表达式，如 x / y * 100": "Expression, e.g. x / y * 100",
    "常用公式：": "Common formulas: ",
    "占比 x/y×100": "Share x/y×100",
    "差值 x−y": "Diff x−y",
    "倍数 x/y": "Ratio x/y",
    "合计 x+y": "Sum x+y",
    "计算同比": "YoY comparison",
    "取消": "Cancel",
    "保存分析": "Save Analysis",
    "公式：": "Expr: ",

    /* 关键指标 / 快速开始 */
    "关键指标": "Key Indicators",
    "公开数据": "Public Data",
    "查看全部指标 →": "View All Indicators →",
    "快速开始": "Quick Start",
    "GDP 构成分析": "GDP Composition",
    "查看三大产业增加值及占比": "Value added of the three industries",
    "工业运行": "Industry",
    "对比各经济体工业增加值": "Compare industrial value added across economies",
    "贸易统计": "Trade",
    "进出口与消费数据": "Exports, imports and retail sales",
    "投资与人口": "Investment & Population",
    "固定资产投资与人口指标": "Fixed asset investment and population",
    "加载中…": "Loading…",

    /* 侧边栏 */
    "知识库与数据源": "Knowledge Base & Sources",
    "管理": "Manage",
    "国家统计局（公开数据）": "China NBS (public)",
    "海关总署（公开数据）": "China Customs (public)",
    "世界银行 Open Data": "World Bank Open Data",
    "权威统计年鉴": "Official Statistical Yearbooks",
    "本项目仅使用公开数据，不含任何内部或涉密数据":
      "This project uses <b>official public data</b> only — nothing internal or classified.",
    "数据收集": "Data Collection",
    "国家统计局": "China NBS",
    "海关总署": "China Customs",
    "指标名，如 GDP、CPI": "Indicator, e.g. gdp, cpi, population",
    "从公开数据源采集": "Collect from Public Sources",
    "统计公报": "Statistical Bulletin",
    "更多": "More",
    "数据来源与规模": "Data Sources & Scale",
    "指标记录": "Indicator Rows",
    "知识条目": "Knowledge Entries",
    "覆盖经济体": "Economies",
    "覆盖年份": "Years Covered",
    "生成公报": "Generate Bulletin",
    "含云端 AI 解读": "Include cloud AI interpretation",
    "点击「生成公报」按当前年份与维度输出真实数据公报":
      "Click “Generate Bulletin” to build a bulletin from official data for the selected year and region.",
    "正在生成…": "Generating…",
    "已从公开数据源采集：新增": "Collected from public sources: added",
    "条记录": "rows",
    "采集失败": "Collection failed",
    "请先输入要采集的指标": "Enter an indicator to collect first",
    "采集说明：数据源为世界银行 Open Data（公开、无需鉴权）":
      "Source: World Bank Open Data (public, no API key required).",

    /* 落地页 */
    "功能特性": "Features",
    "工作流程": "Workflow",
    "系统架构": "Architecture",
    "技术栈": "Tech Stack",
    "进入系统 →": "Enter System →",
    "hero.title": 'Redefining <span>Asia-Pacific</span><br>Economic Analysis with <span>AI</span>',
    "hero.subtitle":
      'Built entirely on <b>official public data</b> — World Bank Open Data, China NBS and China Customs — combining natural-language query and custom analysis into one pipeline from collection to AI interpretation.',
    "开始分析 →": "Start Analysis →",
    "了解更多 ↓": "Learn More ↓",
    "公开数据来源": "Official Public Data",
    "分析工作台": "Workbenches",
    "云端智能解读": "Cloud AI",
    "自然语言查询": "NL Query",
    "四大分析引擎，覆盖完整工作流":
      "Four Engines Covering the Full Workflow",
    "section.desc.features":
      "From natural-language questions to deep statistical analysis, from indicator lookup to cross-economy comparison — one workbench for Asia-Pacific macro analytics.",
    "智能查询": "Smart Query",
    "feature.desc.query":
      "Ask in English or Chinese; the engine resolves the indicator, region and year and returns real figures with YoY change — no query syntax to learn.",
    "指标总表": "Indicator Catalog",
    "feature.desc.catalog":
      "A structured indicator lookup table with keyword search, region and category filters. Tick a row and build an analysis in one click — no JSON, no hand-typed expressions.",
    "自定义分析": "Custom Analysis",
    "feature.desc.custom":
      "Bind variables to any category / indicator / region, use one-click formulas for share, difference, ratio or sum, and compare year over year. Results render as cards.",
    "AI 云端解读": "AI Cloud Interpretation",
    "feature.desc.ai":
      "The retrieved official figures are handed to the InfiniSynapse Server API as grounded context, so the interpretation explains real numbers instead of inventing them.",
    "知识库管理": "Knowledge Base",
    "feature.desc.kb":
      "Bilingual caliber notes for every data source — how each series is defined, in what unit, and what it can and cannot be compared with. Used as retrieval context for the AI.",
    "数据采集": "Data Collection",
    "feature.desc.collect":
      "A collection pipeline that only fetches public, auth-free open data, synced into local SQLite so the dashboard keeps working offline.",
    "四步完成深度分析": "Deep Analysis in Four Steps",
    "section.desc.process":
      "From question to insight — every step is traceable back to an official source.",
    "自然语言提问": "Ask in Natural Language",
    "process.desc.1": "Describe what you need in English or Chinese; the engine parses indicator, region and year.",
    "智能数据检索": "Grounded Retrieval",
    "process.desc.2": "Pull the matching series from World Bank Open Data / NBS / Customs and keep the source code in every row.",
    "统计分析计算": "Statistical Computing",
    "process.desc.3": "Compute YoY, shares and cross-economy rankings in local SQLite; render tables and cards.",
    "AI 深度解读": "AI Interpretation",
    "process.desc.4": "Cloud AI interprets the retrieved figures and returns highlights plus risks to watch.",
    "系统架构设计": "System Architecture",
    "section.desc.arch":
      "Decoupled frontend and backend, data stored locally, AI scheduled in the cloud — balancing performance, cost and auditability.",
    "前端交互层": "Frontend",
    "arch.desc.1": "Vanilla HTML/CSS/JS<br>Zero build step<br>Responsive layout",
    "API 网关层": "API Gateway",
    "arch.desc.2": "Python + Flask<br>Serverless on Vercel<br>Edge-delivered",
    "数据存储层": "Data Storage",
    "arch.desc.3": "Local SQLite<br>Indicator wide table<br>Knowledge base index",
    "AI 能力层": "AI Layer",
    "arch.desc.4": "InfiniSynapse API<br>Grounded prompting<br>Streaming response",
    "技术栈详情": "Tech Stack",
    "前端": "Frontend",
    "tech.desc.1": "Vanilla HTML5 + CSS3 + JavaScript<br>No framework, no CDN at runtime<br>System font stack",
    "后端": "Backend",
    "tech.desc.2": "Python + Flask<br>RESTful JSON API<br>Local SQLite storage",
    "AI 模型": "AI Models",
    "tech.desc.3": "InfiniSynapse Server API<br>Bearer-token auth<br>SSE streaming",
    "数据科学": "Data Science",
    "tech.desc.4": "SQLite storage<br>Statistical engine<br>Data visualization",
    "准备好开始分析了吗？": "Ready to start analyzing?",
    "cta.desc": "Open the dashboard and interrogate real Asia-Pacific public data with AI-grounded interpretation.",
    "进入分析系统 →": "Enter Analysis System →",
    "footer.text":
      'Asia-Pacific Statistical Analysis System<br>Data sources: World Bank Open Data · China NBS · China Customs (all public)<br>Official public data only — nothing internal or classified<br><br>',
    "footer.enter": "Enter System",
    "footer.features": "Features",
    "footer.arch": "Architecture",

    /* ── 维度 / 经济体 ── */
    "亚太": "Asia-Pacific",
    "亚太(发展中)": "Asia-Pacific (developing)",
    "中国": "China",
    "日本": "Japan",
    "韩国": "South Korea",
    "印度": "India",
    "印度尼西亚": "Indonesia",
    "泰国": "Thailand",
    "越南": "Viet Nam",
    "马来西亚": "Malaysia",
    "菲律宾": "Philippines",
    "新加坡": "Singapore",
    "全区": "Whole Region",
    "全国": "National",
    "地区": "Region",

    /* ── 图表（自绘 SVG） ── */
    "📈 图表": "📈 Charts",
    "选择指标…": "Select indicator…",
    "跨年趋势": "Trend over Years",
    "分经济体排名": "Ranking by Economy",
    "勾选经济体叠加对比": "Tick economies to overlay",
    "选择指标后可查看跨年趋势与分经济体排名（自绘 SVG，无图表库依赖）":
      "Pick an indicator to see its trend over years and ranking across economies (hand-drawn SVG, no chart library).",
    "请先选择指标": "Select an indicator first",
    "需至少两个年份才能绘制趋势线": "At least two years are needed for a trend line",
    "该指标在所选经济体无数据": "No data for this indicator in the selected economies",
    "该指标在所选年份无数据": "No data for the selected year",

    /* ── 导出 + 分享链接 ── */
    "🔗 分享": "🔗 Share",
    "⬇ 导出 CSV": "⬇ Export CSV",
    "⬇ 导出当前指标": "⬇ Export indicator",
    "已导出 CSV": "CSV exported",
    "分享链接已复制": "Share link copied",
    "复制失败，请手动复制地址栏": "Copy failed — copy the address bar manually",

    /* ── 单位（对外统一用国际写法）── */
    "亿美元": "USD 100M",
    "美元": "USD",
    "亿元": "CNY 100M",
    "万元": "CNY 10K",
    "元": "CNY",
    "亿人": "100M people",
    "万人": "10K people",
    "岁": "years",

    /* ── 指标（世界银行 Open Data 口径）── */
    "国内生产总值(GDP)": "GDP (current US$)",
    "GDP增长率": "GDP Growth",
    "人均GDP": "GDP per Capita",
    "通货膨胀率(CPI)": "Inflation (CPI)",
    "工业增加值": "Industry Value Added",
    "货物服务出口总额": "Exports of Goods & Services",
    "货物服务进口总额": "Imports of Goods & Services",
    "总人口": "Total Population",
    "预期寿命": "Life Expectancy",
    "失业率": "Unemployment Rate",
    "第一产业增加值": "Primary Industry Value Added",
    "第二产业增加值": "Secondary Industry Value Added",
    "第三产业增加值": "Tertiary Industry Value Added",
    "货物进出口总额": "Total Imports & Exports",
    /* ── 指标（国家统计局 / 海关总署口径）── */
    "地区生产总值": "GDP (NBS)",
    "规模以上工业总产值": "Industrial Output (Above-scale)",
    "规模以上工业增加值": "Industrial Value Added (Above-scale)",
    "社会消费品零售总额": "Retail Sales of Consumer Goods",
    "限额以上商品销售额": "Above-Quota Commodity Sales",
    "固定资产投资总额": "Fixed Asset Investment",
    "第二产业投资": "Secondary Industry Investment",
    "第三产业投资": "Tertiary Industry Investment",
    "常住人口": "Resident Population",
    "居民人均可支配收入": "Per Capita Disposable Income",
    "规模以上服务业营业收入": "Service Revenue (Above-scale)",
    "农业总产值": "Total Agricultural Output",

    /* ── 组合串术语（trData 用；长词优先排序，此处顺序不敏感）── */
    "同比": "YoY",
    "增长率": "Growth Rate",
    "占比": "Share",
    "备注": "Remark",
    "来源": "Source",
    "世界银行OpenData": "World Bank Open Data",
    "初步核算": "preliminary accounting",
    "估算": "estimate",
    "年末": "year-end",
    "不含农户": "excl. rural households",
    "出口": "Exports",
    "进口": "Imports",

    /* ── Toast / 提示 ── */
    "请先输入查询问题": "Enter a query first",
    "加载失败": "Load failed",
    "分析完成": "Analysis complete",
    "请求失败": "Request failed",
    "无结果": "No result",
    "请先选中一个指标": "Select an indicator first",
    "已带入所选指标，填好名称与公式即可保存":
      "Selection imported — fill in name and formula to save",
    "请先选择一个分析": "Select an analysis first",
    "名称和表达式必填": "Name and expression are required",
    "请至少填一个有效变量（名称/专业/指标）":
      "Fill at least one valid variable (name / category / indicator)",
    "保存失败": "Save failed",
    "开始采集公开数据…": "Collecting public data…",
    "年份已切换至": "Year switched to",
    "维度已切换至": "Region switched to"
  };

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
    dimension: "Region",
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
    kb_reference: "Knowledge base",
    ai_interpretation: "AI interpretation",
    value_cny_100m: "Value (CNY 100M)",
    value_usd_100m: "Value (USD 100M)",
    secondary_industry_investment_share: "Secondary-industry investment share",
    title: "Title",
    source: "Source",
    content: "Content",
    category: "Profession",
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
