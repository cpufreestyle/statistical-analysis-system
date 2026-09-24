/* ============================================
   亚太统计分析系统 · 落地页专用字典子集

   只收录 public/index.html 实际引用的 69 条（全量 332 条的 20.8%）。
   落地页没有服务端拼装的中文串，也不加载 app.js，
   既不需要 trData() 兜底，也不需要看板专属的那批词条。

   本文件是派生产物，两条不变式：
     · 键集合必须与 public/index.html 的 data-i18n* 引用完全一致；
     · 每条取值必须与 i18n-dict.js 逐字相同。
   漂移由 tests/test_i18n_split.py 把守。
   ============================================ */
window.ZH2EN = {
    "page.title": "Asia-Pacific Statistical Analysis System",
    "nav.title": "Asia-Pacific Statistics",
    "跳到主内容": "Skip to content",
    "badge.api": "Powered by InfiniSynapse Server API",
    "API 文档": "API reference",
    "隐私与数据声明": "Privacy and data",
    "AI 云端解读": "AI interpretation",
    "指标记录": "Indicator rows",
    "覆盖经济体": "Economies",
    "覆盖年份": "Years covered",
    "功能特性": "Features",
    "工作流程": "Workflow",
    "系统架构": "Architecture",
    "技术栈": "Tech stack",
    "进入系统 →": "Open the dashboard →",
    "hero.title": '<span>Asia-Pacific</span> macroeconomic statistics,<br>interpreted by <span>AI</span>',
    "hero.subtitle":
      'Built entirely on <b>official public data</b> — World Bank Open Data, the National Bureau of Statistics of China and China Customs — natural-language query, indicator catalog and custom analysis in one pipeline, from retrieval to AI interpretation.',
    "开始分析 →": "Start analysis →",
    "了解更多 ↓": "Learn more ↓",
    "云端智能解读": "Cloud AI",
    "四大分析引擎，覆盖完整工作流":
      "Four engines, one complete analytical workflow",
    "section.desc.features":
      "From natural-language questions to deep statistical analysis, from indicator lookup to cross-economy comparison — one workbench for Asia-Pacific macro analytics.",
    "智能查询": "Ask the AI",
    "feature.desc.query":
      "Ask in English or Chinese; the engine resolves the indicator, economy and year, then returns official figures with year-on-year change — no query syntax to learn.",
    "指标总表": "Indicator catalog",
    "feature.desc.catalog":
      "A structured indicator catalog with keyword search and filters by economy and category. Select a row and build an analysis in one click — no JSON, no hand-typed expressions.",
    "自定义分析": "Custom analysis",
    "feature.desc.custom":
      "Bind variables to any category / indicator / economy, use one-click formulas for share, difference, ratio or sum, and compare year on year. Results render as cards.",
    "feature.desc.ai":
      "The retrieved official figures are handed to the InfiniSynapse Server API as grounded context, so the interpretation explains real numbers instead of inventing them.",
    "知识库管理": "Knowledge base",
    "feature.desc.kb":
      "Bilingual caliber notes for every data source — how each series is defined, in what unit, and what it can and cannot be compared with. Used as retrieval context for the AI.",
    "数据采集": "Data collection",
    "feature.desc.collect":
      "A collection pipeline that only fetches public, auth-free open data, synced into local SQLite so the dashboard keeps working offline.",
    "四步完成深度分析": "Deep analysis in four steps",
    "section.desc.process":
      "From question to insight — every step is traceable back to an official source.",
    "自然语言提问": "Ask in plain language",
    "process.desc.1": "Describe what you need in English or Chinese; the engine parses indicator, economy and year.",
    "智能数据检索": "Grounded retrieval",
    "process.desc.2": "Pull the matching series from World Bank Open Data / China NBS / China Customs and keep the source code in every row.",
    "统计分析计算": "Statistical computation",
    "process.desc.3": "Compute year-on-year change, shares and cross-economy rankings in local SQLite; render tables and cards.",
    "AI 深度解读": "AI interpretation",
    "process.desc.4": "Cloud AI interprets the retrieved figures and returns highlights plus risks to watch.",
    "系统架构设计": "System architecture",
    "section.desc.arch":
      "Decoupled frontend and backend, data stored locally, AI scheduled in the cloud — balancing performance, cost and auditability.",
    "前端交互层": "Frontend",
    "arch.desc.1": "Vanilla HTML/CSS/JS<br>Zero build step<br>Responsive layout",
    "API 网关层": "API gateway",
    "arch.desc.2": "Python + Flask<br>Serverless on Vercel<br>Edge-delivered",
    "数据存储层": "Data storage",
    "arch.desc.3": "Local SQLite<br>Indicator wide table<br>Knowledge base index",
    "AI 能力层": "AI layer",
    "arch.desc.4": "InfiniSynapse API<br>Grounded prompting<br>Streaming response",
    "技术栈详情": "Tech stack",
    "前端": "Frontend",
    "tech.desc.1": "Vanilla HTML5 + CSS3 + JavaScript<br>No framework, no CDN at runtime<br>System font stack",
    "后端": "Backend",
    "tech.desc.2": "Python + Flask<br>RESTful JSON API<br>Local SQLite storage",
    "AI 模型": "AI models",
    "tech.desc.3": "InfiniSynapse Server API<br>Bearer-token auth<br>SSE streaming",
    "数据科学": "Data science",
    "tech.desc.4": "SQLite storage<br>Statistical engine<br>Data visualization",
    "准备好开始分析了吗？": "Ready to start analyzing?",
    "cta.desc": "Open the dashboard and interrogate real Asia-Pacific public data with AI-grounded interpretation.",
    "进入分析系统 →": "Open the dashboard →",
    "footer.text":
      'Asia-Pacific Statistical Analysis System<br>Data sources: World Bank Open Data · China NBS · China Customs (all public)<br>Official public data only — nothing internal or classified<br><br>',
    "footer.enter": "Open the dashboard",
    "footer.features": "Features",
    "footer.arch": "Architecture",
};
