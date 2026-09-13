/* ============================================
   全国统计分析系统 · 国际化（中 / 英）
   字典以「中文原文」为 key，英文为 value；
   静态文案用 data-i18n / data-i18n-html / data-i18n-ph 标注，
   动态数据（指标名、专业、维度、单位等）用 tr() 在渲染时翻译。
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

  /* ── 中文 → 英文 全量字典 ── */
  var ZH2EN = {
    /* 通用 / 框架 */
    "page.title": "China Statistics System",
    "home.link": "🏠 Home",
    "搜索": "Search",
    "搜索指标、地区、分析主题…": "Search indicators, regions, topics…",
    "仅使用公开数据": "Public Data Only",
    "badge.public": "Public Data Only",

    /* 应用页头 */
    "数据概览": "Data Overview",
    "subtitle.text": " National Economic Data Statistics & Analysis",
    "全国统计分析": "National Statistics",

    /* 工作台 Tab */
    "🌟 智能查询": "🌟 AI Query",
    "📊 指标总表": "📊 Indicators",
    "📋 自定义分析": "📋 Custom Analysis",

    /* 智能查询 */
    "输入你的分析问题，AI 将基于全国统计数据为你生成分析结果":
      "Enter your analysis question; the AI generates results from national statistics.",
    "例如：2024年社会消费品零售总额是多少？":
      "e.g. What is the 2024 total retail sales of consumer goods?",
    "📡 开始分析": "📡 Analyze",
    "💡 试试这些问题": "💡 Try these",
    "chip.gdp": "What is 2024 GDP?",
    "chip.retail": "Total Retail Sales",
    "chip.invest": "Fixed Asset Investment",
    "chip.pop": "Resident Population",

    /* 指标总表 */
    "勾选指标后点「用所选建分析」可一键带入自定义分析；也可在上方自然语言框直接问具体指标名。":
      "Tick an indicator then “Build from selection” to reuse it in Custom Analysis; or just ask the AI box above by name.",
    "全部专业": "All Categories",
    "国民经济核算": "National Economic Accounting",
    "工业": "Industry",
    "对外贸易": "Foreign Trade",
    "金融": "Finance",
    "人口与就业": "Population & Employment",
    "服务业": "Services",
    "农业": "Agriculture",
    "关键词搜索指标 / 说明 / 维度": "Search indicator / note / dimension",
    "🔍 查询": "🔍 Query",
    "用所选指标创建分析": "Build Analysis from Selection",
    "选择": "Select",
    "指标": "Indicator",
    "专业": "Category",
    "维度": "Dimension",
    "数值": "Value",
    "单位": "Unit",
    "说明": "Note",

    /* 自定义分析 */
    "选择已有分析…": "Select an analysis…",
    "运行": "Run",
    "＋ 新建": "＋ New",
    "选择并运行分析": "Select & Run an Analysis",
    "从下拉列表选择一个已有的自定义分析，或点击「新建」创建自己的分析模板":
      "Pick an existing custom analysis, or click “New” to build your own template.",
    "分析名称（必填）": "Analysis name (required)",
    "单位，如 %、亿元": "Unit, e.g. %, 100M yuan",
    "说明（可选）": "Note (optional)",
    "变量绑定": "Variable Binding",
    "变量": "Var",
    "维度（可选）": "Dimension (opt)",
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

    /* 关键指标 / 快速开始 */
    "关键指标": "Key Indicators",
    "公开数据": "Public Data",
    "查看全部指标 →": "View All Indicators →",
    "快速开始": "Quick Start",
    "GDP 构成分析": "GDP Composition",
    "查看三大产业增加值及占比": "Primary, secondary & tertiary value-added and shares",
    "工业运行": "Industrial Performance",
    "对比规上工业总产值与增加值": "Compare total vs. added value of above-scale industry",
    "贸易统计": "Trade Statistics",
    "社会消费品零售总额等数据": "Total retail sales of consumer goods, etc.",
    "投资与人口": "Investment & Population",
    "固定资产投资与常住人口": "Fixed asset investment & resident population",

    /* 侧边栏 */
    "知识库与数据源": "Knowledge Base & Sources",
    "管理": "Manage",
    "国家统计局（公开数据）": "National Bureau of Statistics (Public)",
    "海关总署（公开数据）": "General Administration of Customs (Public)",
    "世界银行 Open Data": "World Bank Open Data",
    "权威统计年鉴": "Authoritative Yearbooks",
    "本项目仅使用公开数据，不含任何内部或涉密数据":
      "This project uses <b>public data</b> only — no internal or classified data.",
    "数据收集": "Data Collection",
    "国家统计局": "National Bureau of Statistics",
    "海关总署": "General Administration of Customs",
    "指标名，如 GDP、CPI": "Indicator name, e.g. GDP, CPI",
    "从公开数据源采集": "Collect from Public Sources",
    "统计公报": "Statistical Bulletins",
    "更多": "More",
    "2024年国民经济和社会发展统计公报": "2024 Statistical Bulletin on National Economic & Social Development",
    "2024年全国统计年鉴": "2024 China Statistical Yearbook",
    "查看全部公报": "View All Bulletins",
    "今日动态": "Today's Activity",
    "完成查询：2024年GDP构成分析": "Query done: 2024 GDP composition",
    "数据源「国家统计局」已更新": 'Source "National Bureau of Statistics" updated',
    "统计公报「2024年度全国经济概览」已发布": 'Bulletin "2024 National Economic Overview" published',
    "数据采集任务「海关月度数据」完成": 'Data collection "Customs Monthly" completed',
    "完成查询：固定资产投资对比": "Query done: fixed asset investment comparison",

    /* 落地页 */
    "nav.title": "China Statistics System",
    "功能特性": "Features",
    "工作流程": "Workflow",
    "系统架构": "Architecture",
    "技术栈": "Tech Stack",
    "进入系统 →": "Enter System →",
    "hero.title": 'Redefining National<br>Economic Data Analysis with <span>AI</span>',
    "hero.subtitle":
      'Built on <b>public data</b> from the National Bureau of Statistics, Customs, etc. — combining natural-language query and custom analysis into an end-to-end pipeline from collection to AI interpretation.',
    "开始分析 →": "Start Analysis →",
    "了解更多 ↓": "Learn More ↓",
    "公开数据来源": "Public Sources",
    "分析工作台": "Workbenches",
    "云端智能解读": "Cloud AI",
    "自然语言查询": "NL Query",
    "四大分析引擎，覆盖完整工作流":
      "Four Engines Covering the Full Workflow",
    "section.desc.features":
      "From natural-language questions to deep statistical analysis, from indicator lookup to custom modeling — one workbench for every national macroeconomic analytics need.",
    "智能查询": "Smart Query",
    "feature.desc.query":
      "Ask in natural language; the AI understands intent, retrieves data and produces an analysis report. No complex syntax — ask “2024 total retail sales of consumer goods” and get the number.",
    "指标总表": "Indicator Catalog",
    "feature.desc.catalog":
      "A structured indicator lookup UI with keyword search. Tick indicators and build an analysis in one click — no JSON, no hand-typed expressions.",
    "自定义分析": "Custom Analysis",
    "feature.desc.custom":
      "Pick profession / indicator / dimension from dropdowns; one-click formulas for share / diff / ratio / sum, with YoY support; results shown as cards.",
    "AI 云端解读": "AI Cloud Interpretation",
    "feature.desc.ai":
      "Deep semantic interpretation of results via the InfiniSynapse Server API — not just numbers, but actionable insights.",
    "知识库管理": "Knowledge Base",
    "feature.desc.kb":
      "Integrated statistical-caliber notes from public sources like the NBS and Customs. Unified source management with online custom entries.",
    "数据采集": "Data Collection",
    "feature.desc.collect":
      "Automated collection pipeline that only fetches public, auth-free data, synced to local SQLite for offline use and history.",
    "四步完成深度分析": "Deep Analysis in Four Steps",
    "section.desc.process":
      "From question to insight, AI is involved at every step — not just a query tool, but a complete analytics workflow.",
    "自然语言提问": "Ask in Natural Language",
    "process.desc.1": "Describe your need in Chinese; the AI parses intent and matches data.",
    "智能数据检索": "Smart Retrieval",
    "process.desc.2": "Retrieve from public sources; auto-match indicators and reconcile units & caliber.",
    "统计分析计算": "Statistical Computing",
    "process.desc.3": "Run statistics in local SQLite; generate charts and data tables.",
    "AI 深度解读": "AI Interpretation",
    "process.desc.4": "Cloud AI semantically interprets results; outputs insights and risk notes.",
    "系统架构设计": "System Architecture",
    "section.desc.arch":
      "Decoupled frontend/backend, locally stored data, cloud-scheduled AI. Balancing performance, security and scalability.",
    "前端交互层": "Frontend",
    "arch.desc.1": "原生 HTML/CSS/JS<br>瑞士排版风格<br>响应式设计",
    "API 网关层": "API Gateway",
    "arch.desc.2": "Flask 后端服务<br>自动扩缩容<br>边缘计算加速",
    "数据存储层": "Data Storage",
    "arch.desc.3": "本地 SQLite<br>知识库索引<br>历史数据追溯",
    "AI 能力层": "AI Layer",
    "arch.desc.4": "InfiniSynapse API<br>多模型调度<br>流式响应",
    "技术栈详情": "Tech Stack",
    "前端": "Frontend",
    "tech.desc.1": "原生 HTML5 + CSS3 + JavaScript<br>零依赖，轻量高效<br>思源黑体 + Roboto 字体",
    "后端": "Backend",
    "tech.desc.2": "Python + Flask<br>RESTful API 设计<br>本地 SQLite 存储",
    "AI 模型": "AI Models",
    "tech.desc.3": "InfiniSynapse Server API<br>多模型智能路由<br>SSE 流式响应",
    "数据科学": "Data Science",
    "tech.desc.4": "SQLite 本地存储<br>统计分析引擎<br>数据可视化",
    "准备好开始分析了吗？": "Ready to start analyzing?",
    "cta.desc": "Experience the national statistics system now and let AI surface the insights behind the data.",
    "进入分析系统 →": "Enter Analysis System →",
    "footer.text":
      'China Statistics System<br>Data sources: National Bureau of Statistics · General Administration of Customs (all public)<br>This project uses public data only — no internal or classified data<br><br>',
    "footer.enter": "Enter System",
    "footer.features": "Features",
    "footer.arch": "Architecture",

    /* ── 动态数据词汇（tr 使用）── */
    /* 专业 / 分类 */
    "综合": "General",
    "贸易": "Trade",
    "投资": "Investment",
    "人口": "Population",
    /* 维度 */
    "亚太": "Asia-Pacific",
    "全区": "Whole Region",
    "全国": "National",
    /* 街镇名（专有名词用拼音，不意译） */
    "大场镇": "Dachang Town",
    "杨行镇": "Yanghang Town",
    "顾村镇": "Gucun Town",
    "月浦镇": "Yuepu Town",
    "罗店镇": "Luodian Town",
    "中国": "China",
    "日本": "Japan",
    "韩国": "South Korea",
    "印度": "India",
    "印度尼西亚": "Indonesia",
    /* 单位 */
    "亿元": "100M yuan",
    "万元": "10K yuan",
    "元": "yuan",
    "亿人": "100M",
    "万人": "10K",
    /* 指标 */
    "地区生产总值": "GDP",
    "规模以上工业总产值": "Industrial Output (Above-scale)",
    "规模以上工业增加值": "Industrial Added Value (Above-scale)",
    "社会消费品零售总额": "Total Retail Sales of Consumer Goods",
    "限额以上商品销售额": "Above-Quota Commodity Sales",
    "固定资产投资总额": "Total Fixed Asset Investment",
    "第二产业投资": "Secondary Industry Investment",
    "第三产业投资": "Tertiary Industry Investment",
    "常住人口": "Resident Population",
    "居民人均可支配收入": "Per Capita Disposable Income",
    "规模以上服务业营业收入": "Service Revenue (Above-scale)",
    "农业总产值": "Total Agricultural Output",
    "地区生产总值 (GDP)": "GDP",
    "规上工业总产值": "Industrial Output (Above-scale)",
    "第一产业增加值": "Primary Industry Added Value",
    "第二产业增加值": "Secondary Industry Added Value",
    "第三产业增加值": "Tertiary Industry Added Value",
    "货物进出口总额": "Total Imports & Exports of Goods",
    /* 卡片副文案术语 */
    "同比": "YoY",
    "增加值": "Added Value",
    "限上销售额": "Above-Quota Sales",
    "工业投资占比": "Industrial Investment Share",
    "人均可支配收入": "Per Capita Disposable Income",
    /* 分析结果键 */
    "知识库参考": "KB Reference",
    "年份": "Year",
    "地区": "Region",
    "增长率": "Growth Rate",
    "占比": "Share",
    "备注": "Remark",
    "来源": "Source",

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
    "年份已切换至": "Year switched to"
  };

  /* 翻译一段数据文本（未知则原样返回） */
  function tr(s) {
    if (s == null) return s;
    // 只有英文模式才翻译；中文模式原样返回（否则切回中文仍显示英文）
    if (window.CUR_LANG !== "en") return s;
    return ZH2EN[s] !== undefined ? ZH2EN[s] : s;
  }

  /* 组合串（如 "同比 5.2"、"增加值 800 亿元"）无法整串命中字典，
     故按「长词优先」逐个替换其中的专业术语。仅英文模式生效。 */
  var DATA_TERMS = [
    "规模以上服务业营业收入", "规模以上工业增加值", "规模以上工业总产值",
    "居民人均可支配收入", "社会消费品零售总额", "限额以上商品销售额",
    "固定资产投资总额", "货物进出口总额",
    "第一产业增加值", "第二产业增加值", "第三产业增加值",
    "第二产业投资", "第三产业投资",
    "工业投资占比", "人均可支配收入", "地区生产总值", "农业总产值",
    "限上销售额", "规上工业总产值", "常住人口",
    "全国", "增加值", "综合", "工业", "贸易", "投资", "人口", "服务业", "农业", "同比",
    "亿元", "万元", "亿人", "万人", "元"
  ];

  function trData(s) {
    if (s == null) return s;
    if (window.CUR_LANG !== "en") return s;
    var out = String(s);
    for (var i = 0; i < DATA_TERMS.length; i++) {
      var k = DATA_TERMS[i];
      if (ZH2EN[k] != null) out = out.split(k).join(ZH2EN[k]);
    }
    return out;
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

    /* 年份下拉：中文加“年”后缀 */
    document.querySelectorAll("#globalYear option").forEach(function (o) {
      o.textContent = o.value + (lang === "zh" ? "年" : "");
    });

    /* 副标题年份同步 */
    var sy = document.getElementById("subtitleYear");
    if (sy) {
      var gy = document.getElementById("globalYear");
      if (gy) sy.textContent = gy.value;
    }

    /* 切换按钮文字 */
    var tb = document.getElementById("langToggle");
    if (tb) tb.textContent = lang === "zh" ? "EN" : "中文";

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
