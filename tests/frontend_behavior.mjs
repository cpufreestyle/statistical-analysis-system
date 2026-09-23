/* 真实前端逻辑的行为检查（零依赖、零构建）：
   在 Node 的 vm 沙箱里执行仓库里那份 public/i18n.js + public/app.js，
   用最小 DOM / fetch 桩驱动 loadOverview()，断言空看板兜底与语言切换的实际输出。

   由 tests/test_frontend.py 调起（`node tests/frontend_behavior.mjs`）。
   改坏 public/app.js 的兜底分支或维度键判断，这里就会红——不再只能靠人工点浏览器。 */
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (rel) => fs.readFileSync(path.resolve(ROOT, rel), "utf8");

/* 允许把被测 JS 换成临时副本（tests/test_frontend.py 用它验证本 harness 真会红），
   避免为了「破坏一下看看」去改写仓库里被跟踪的 public/ 文件。 */
const I18N_JS = process.env.QU_STAT_I18N_JS || path.join("public", "i18n.js");
const APP_JS = process.env.QU_STAT_APP_JS || path.join("public", "app.js");

/* ───────────────────────── 最小浏览器桩 ───────────────────────── */

function makeEl(id, tag = "div") {
  const listeners = {};
  const el = {
    id: id || "",
    tagName: tag,
    innerHTML: "",
    textContent: "",
    value: "",
    checked: false,
    style: {},
    dataset: {},
    options: [],
    children: [],
    classList: {
      _set: new Set(),
      add(c) { this._set.add(c); },
      remove(c) { this._set.delete(c); },
      toggle(c, on) { if (on === undefined || on) this._set.add(c); else this._set.delete(c); },
      contains(c) { return this._set.has(c); },
    },
    _attrs: {},
    setAttribute(k, v) { this._attrs[k] = v; if (k === 'title') this.title = v; },
    getAttribute(k) { return this._attrs[k] ?? null; },
    removeAttribute(k) { delete this._attrs[k]; },
    appendChild(c) { this.children.push(c); return c; },
    removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; },
    addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    removeEventListener() {},
    dispatchEvent(ev) {
      (listeners[ev.type] || []).forEach(fn => fn(ev));
      return true;
    },
    querySelector(sel) {
      if (sel === '[role="tablist"]' && el._tablist) return el._tablist;
      return null;
    },
    querySelectorAll(sel) {
      if (sel === '.wb-tab' || sel === '[role="tab"]') return el._tabs || [];
      if (sel === '.wb-panel') return el._panels || [];
      /* 通用兜底：测试可以按 class 精确注入子元素（如指标卡的 .metric-spark） */
      if (el.__qa) return el.__qa(sel) || [];
      return [];
    },
    click() { (listeners["click"] || []).forEach(fn => fn({ target: el })); },
    focus() { el._focused = true; },
    blur() { el._focused = false; },
    select() {}, scrollIntoView() {},
    getBoundingClientRect() { return { top: 0, left: 0, width: 0, height: 0 }; },
  };
  return el;
}

const elements = new Map();
/* document 级监听：记录后可由 dispatchEvent 派发。
   加载期绑定（initShortcuts 的 document keydown）必须有路可测，否则「增强能力
   初始化顺序写错、抛错被 try/catch 吞掉」这类回归只能靠人工按键盘才发现。 */
const docListeners = {};
const documentStub = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, makeEl(id, id === "globalYear" || id === "indCat" ? "select" : "div"));
    return elements.get(id);
  },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  createElement: (tag) => makeEl("", tag),
  addEventListener(type, fn) { (docListeners[type] = docListeners[type] || []).push(fn); },
  removeEventListener(type, fn) {
    docListeners[type] = (docListeners[type] || []).filter((f) => f !== fn);
  },
  dispatchEvent(ev) {
    (docListeners[ev.type] || []).forEach((fn) => fn(ev));
    return true;
  },
  body: makeEl("body"),
  documentElement: makeEl("html"),
  activeElement: null,
};

const sandbox = {
  console,
  document: documentStub,
  /* 可读写的 localStorage：主题持久化 / 语言偏好都走它，返回 null 的假存储测不出回归 */
  localStorage: (() => {
    const store = new Map();
    return {
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, String(v)),
      removeItem: (k) => store.delete(k),
      _store: store,
    };
  })(),
  history: { replaceState() {}, pushState() {} },
  navigator: {},
  location: { href: "http://127.0.0.1:5000/app", pathname: "/app", search: "", origin: "http://127.0.0.1:5000" },
  setTimeout, clearTimeout, setInterval, clearInterval,
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  URLSearchParams,
  /* 系统配色偏好：测试用 __darkSystem 切换，验证 auto 主题的跟随行为 */
  matchMedia: (q) => ({
    matches: /dark/.test(String(q)) ? !!sandbox.__darkSystem : false,
    media: String(q),
    addEventListener() {}, removeEventListener() {},
    addListener() {}, removeListener() {},
  }),
  CustomEvent: class CustomEvent { constructor(type, detail) { this.type = type; this.detail = detail; } },
  Event: class Event { constructor(type) { this.type = type; } },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.self = sandbox;
sandbox.dispatchEvent = () => true;
sandbox.addEventListener = () => {};

/* fetch 桩：/api/overview 走当前场景设定的载荷，其余端点返回最小可用响应。
   真实数据契约由 scripts/check_i18n.py 对活服务把守，这里只管前端行为。 */
sandbox.fetch = async (url) => {
  const u = String(url);
  let payload;
  if (u.includes("/api/overview")) payload = sandbox.__overview;
  else if (u.includes("/api/insights")) payload = sandbox.__insights || {};
  else if (u.includes("/api/indicators")) payload = sandbox.__indicators || [];
  else if (u.includes("/api/custom")) payload = [];
  else if (u.includes("/api/stats")) payload = { indicator_rows: 0, knowledge_rows: 0, dimension_count: 0, years: [] };
  else payload = {};
  if (sandbox.__fetchFails) throw new Error("network down");
  return { ok: true, status: 200, json: async () => payload, text: async () => JSON.stringify(payload) };
};

const context = vm.createContext(sandbox);

/* ───────────────────────── Tab 测试 DOM 桩 ───────────────────────── */
/* 在 app.js init() 跑之前建好最小 tablist，让 keydown handler 能挂上。
   真实渲染由 loadOverview 驱动，这里只测键盘导航逻辑。 */
const TAB_IDS = ["nlq", "indicators", "custom", "bulletin", "charts"];
const tabButtons = TAB_IDS.map((tid, i) => {
  const btn = makeEl("", "button");
  btn.dataset.tab = tid;
  btn.setAttribute("role", "tab");
  btn.setAttribute("aria-selected", i === 0 ? "true" : "false");
  btn.classList.toggle("active", i === 0);
  return btn;
});
const panels = TAB_IDS.map((tid) => {
  const p = makeEl("panel-" + tid);
  p.classList.toggle("active", tid === "nlq");
  return p;
});
const tablistEl = makeEl("", "div");
tablistEl._tabs = tabButtons;
tablistEl._panels = panels;
tablistEl.setAttribute("role", "tablist");

/* 把 tablist 挂到 body 的 querySelector 路径上 */
const bodyEl = sandbox.document.body;
bodyEl._tablist = tablistEl;
sandbox.document.querySelector = (sel) => {
  if (sel === '[role="tablist"]') return tablistEl;
  return null;
};
/* querySelectorAll('.wb-tab') 也要返回这些按钮（init 里两处都用） */
sandbox.document.querySelectorAll = (sel) => {
  if (sel === ".wb-tab" || sel === "[role=\"tab\"]") return tabButtons;
  if (sel === ".wb-panel") return panels;
  return [];
};

/* 单一脚本体：真实源码 + 场景驱动，保证 driver 与 app.js 处于同一词法作用域
   （app.js 的 STATE 是顶层 const，跨 runInContext 调用不可见）。 */
const DRIVER = `
(async function drive() {
  var results = [];
  function check(name, ok, detail) { results.push({ name: name, ok: !!ok, detail: detail == null ? "" : String(detail) }); }

  /* ── 加载期初始化（顺序回归防线） ──
     app.js 末尾的 initTheme/initShortcuts/initPalette 必须在所有 const 声明之后执行。
     放早了会在暂时死区抛 ReferenceError 又被 try/catch 吞掉：页面看着正常，
     快捷键、命令面板、主题按钮同步全都不工作。这三条就是那条回归的哨兵。 */
  var themeBtnEl = document.getElementById('themeToggle');
  check('加载即同步主题按钮',
    String(themeBtnEl.title).indexOf('Theme') >= 0 && String(themeBtnEl.title).length > 4,
    String(themeBtnEl.title));
  check('加载即落地 data-theme',
    document.documentElement.getAttribute('data-theme') === 'light',
    String(document.documentElement.getAttribute('data-theme')));
  var keyEvt = function (key, mod) {
    return { type: 'keydown', key: key, ctrlKey: !!mod, metaKey: false, altKey: false,
      target: document.body, preventDefault: function () {} };
  };
  var paletteEl = document.getElementById('palette');
  var helpEl0 = document.getElementById('shortcuts');
  document.dispatchEvent(keyEvt('k', true));
  check('Ctrl+K 能打开命令面板', paletteEl && paletteEl.hidden === false, String(paletteEl && paletteEl.hidden));
  document.dispatchEvent(keyEvt('Escape'));
  check('Esc 能关闭命令面板', paletteEl && paletteEl.hidden === true, String(paletteEl && paletteEl.hidden));
  document.dispatchEvent(keyEvt('?'));
  check('问号键能打开帮助浮层', helpEl0 && helpEl0.hidden === false, String(helpEl0 && helpEl0.hidden));
  document.dispatchEvent(keyEvt('Escape'));
  check('Esc 能关闭帮助浮层', helpEl0 && helpEl0.hidden === true, String(helpEl0 && helpEl0.hidden));
  var grid = document.getElementById('metricsGrid');

  function payload(over) {
    return Object.assign({ year: 2024, years: [2023, 2024], dimension_options: [], category_options: [] }, over);
  }

  async function render(over, lang, opts) {
    window.CUR_LANG = lang;
    globalThis.__overview = payload(over);
    globalThis.__fetchFails = !!(opts && opts.fail);
    grid.innerHTML = '';
    await loadOverview();
    globalThis.__fetchFails = false;
    return grid.innerHTML;
  }

  var CJK = /[\\u4e00-\\u9fff]/;

  /* 场景 1：旧分享链接指向无数据维度，STATE 里存的是本地化标签（跨语言不可靠的那一步） */
  STATE.dimension = 'China';
  var en = await render({ cards: [], dimension: 'China', dimension_key: '中国' }, 'en');
  check('空看板给出英文兜底文案', en.indexOf('No data for this economy yet') >= 0, en.slice(0, 200));
  check('兜底带切回亚太的出口', en.indexOf("syncDimension('亚太')") >= 0 && en.indexOf('View Asia-Pacific') >= 0, en.slice(0, 300));
  check('可见文案不残留中文原词', en.indexOf('该维度暂无数据') < 0, en.slice(0, 200));
  check('按 dimension_key 判重，STATE 仍是展示标签', STATE.dimension === 'China', STATE.dimension);

  /* 场景 2：已经是亚太口径 -> 不能再给「切回亚太」的自我死循环 */
  var atHome = await render({ cards: [], dimension: 'Asia-Pacific', dimension_key: '亚太' }, 'en');
  check('亚太口径空态不再给出口按钮', atHome.indexOf('syncDimension(') < 0, atHome.slice(0, 200));
  check('亚太口径空态仍有说明', atHome.indexOf('No data for this economy yet') >= 0, atHome.slice(0, 200));

  /* 场景 3：中文界面同一分支回到中文原文（tr 只在英文模式下替换） */
  var zh = await render({ cards: [], dimension: '中国', dimension_key: '中国' }, 'zh');
  check('中文界面兜底为中文', zh.indexOf('该维度暂无数据') >= 0 && zh.indexOf('切换到亚太') >= 0, zh.slice(0, 200));

  /* 场景 4：有数据时不得出现兜底块 */
  var filled = await render({
    cards: [{ label: 'GDP (current US$)', value: '35.7', unit: 'USD trillion', dimension: 'China', dimension_key: '中国', note: 'Source: World Bank Open Data (NY.GDP.MKTP.CD, EAS)' }],
    dimension: 'China', dimension_key: '中国',
  }, 'en');
  check('有数据渲染指标卡', filled.indexOf('metric-label') >= 0, filled.slice(0, 200));
  check('有数据时不出现空态兜底', filled.indexOf('No data for this economy yet') < 0, filled.slice(0, 200));

  /* 场景 5：取数失败也必须留下可见状态，而不是停在骨架屏 */
  var failed = await render({ cards: [] }, 'en', { fail: true });
  check('取数失败渲染失败态', failed.indexOf('Load failed') >= 0 || CJK.test(failed) === false, failed.slice(0, 200));
  check('取数失败不留骨架屏', failed.indexOf('metric-skeleton') < 0, failed.slice(0, 200));

  /* ── Tab 键盘导航 ── */
  /* init() 已挂好 keydown handler；这里用合成事件验证 WAI-ARIA tablist 行为。 */
  var tabs = document.querySelectorAll('[role="tab"]');

  function fireKey(target, key) {
    var ev = { type: "keydown", key: key, target: target, preventDefault: function () {} };
    document.querySelector('[role="tablist"]').dispatchEvent(ev);
  }

  /* 场景 6：ArrowRight 从第一个 tab 移到第二个 */
  fireKey(tabs[0], "ArrowRight");
  check('ArrowRight 激活下一个 tab', tabs[1].getAttribute("aria-selected") === "true",
    "tab1 aria-selected=" + tabs[1].getAttribute("aria-selected"));
  check('ArrowRight 取消前一个 tab', tabs[0].getAttribute("aria-selected") === "false",
    "tab0 aria-selected=" + tabs[0].getAttribute("aria-selected"));

  /* 场景 7：ArrowLeft 回退 */
  fireKey(tabs[1], "ArrowLeft");
  check('ArrowLeft 回到前一个 tab', tabs[0].getAttribute("aria-selected") === "true",
    "tab0 aria-selected=" + tabs[0].getAttribute("aria-selected"));

  /* 场景 8：End 跳到最后一个 */
  fireKey(tabs[0], "End");
  check('End 跳到最后一个 tab', tabs[tabs.length - 1].getAttribute("aria-selected") === "true",
    "last tab aria-selected=" + tabs[tabs.length - 1].getAttribute("aria-selected"));

  /* 场景 9：Home 跳回第一个 */
  fireKey(tabs[tabs.length - 1], "Home");
  check('Home 跳回第一个 tab', tabs[0].getAttribute("aria-selected") === "true",
    "tab0 aria-selected=" + tabs[0].getAttribute("aria-selected"));

  /* 场景 10：ArrowRight 在末尾循环到第一个 */
  fireKey(tabs[tabs.length - 1], "ArrowRight");
  check('ArrowRight 末尾循环到首', tabs[0].getAttribute("aria-selected") === "true",
    "tab0 aria-selected=" + tabs[0].getAttribute("aria-selected"));

  /* 场景 11：roving tabindex — active tab 为 0，其余为 -1 */
  var rovingOk = tabs.every(function (t, i) {
    return t.getAttribute("tabindex") === (i === 0 ? "0" : "-1");
  });
  check('roving tabindex 正确', rovingOk,
    tabs.map(function (t) { return t.getAttribute("tabindex"); }).join(","));

  /* ── 主题三态 ── */
  localStorage.removeItem('qu_theme_v1');
  globalThis.__darkSystem = false;
  var t0 = themeMode();
  themeApply(t0);
  check('默认主题为 auto', t0 === 'auto', t0);
  check('系统浅色时解析为 light', document.documentElement.getAttribute('data-theme') === 'light',
    document.documentElement.getAttribute('data-theme'));

  globalThis.__darkSystem = true;
  themeApply('auto');
  check('系统深色时 auto 解析为 dark', document.documentElement.getAttribute('data-theme') === 'dark',
    document.documentElement.getAttribute('data-theme'));
  themeApply('light');
  check('手动浅色优先于系统深色', document.documentElement.getAttribute('data-theme') === 'light',
    document.documentElement.getAttribute('data-theme'));

  localStorage.setItem('qu_theme_v1', 'auto');
  cycleTheme();
  var m1 = themeMode();
  cycleTheme();
  var m2 = themeMode();
  cycleTheme();
  var m3 = themeMode();
  check('主题循环顺序 auto/light/dark', m1 === 'light' && m2 === 'dark' && m3 === 'auto',
    m1 + ',' + m2 + ',' + m3);
  check('主题选择已持久化', localStorage.getItem('qu_theme_v1') === 'auto',
    localStorage.getItem('qu_theme_v1'));

  /* ── 命令面板 ── */
  window._years = [2022, 2023, 2024];
  window._dimOptions = [{ label: 'China', key: '中国', slug: 'china' },
                         { label: 'Japan', key: '日本', slug: 'japan' }];
  openPalette();
  var palEl = document.getElementById('palette');
  var listEl = document.getElementById('paletteList');
  check('命令面板打开后可见', palEl.hidden === false && PAL.open === true, String(palEl.hidden));
  check('命令列表渲染 option', listEl.innerHTML.indexOf('role="option"') >= 0,
    listEl.innerHTML.slice(0, 120));
  check('命令含年份项', listEl.innerHTML.indexOf('2024') >= 0, '');
  check('命令含经济体项', listEl.innerHTML.indexOf('China') >= 0, '');

  paletteRender('2024');
  var allMatchQ = PAL.view.length > 0 && PAL.view.every(function (c) {
    return paletteScore(c.label + ' ' + (c.keywords || ''), '2024') >= 0;
  });
  check('按年份过滤只留命中项', PAL.view.length > 0 && allMatchQ, String(PAL.view.length));
  paletteRender('zzzzzz');
  check('无命中给出空态', PAL.view.length === 0
    && listEl.innerHTML.indexOf('palette-empty') >= 0, listEl.innerHTML.slice(0, 80));

  paletteRender('');
  var chartIdx = -1;
  PAL.view.forEach(function (c, i) { if (c.label === tr('图表')) chartIdx = i; });
  PAL.idx = chartIdx;
  paletteMove(1);
  PAL.idx = chartIdx;
  paletteRun(chartIdx);
  var chartsTab = document.querySelectorAll('[role="tab"]').filter(function (t) {
    return t.dataset.tab === 'charts';
  })[0];
  check('面板命令切到图表视图', chartsTab.getAttribute('aria-selected') === 'true',
    chartsTab.getAttribute('aria-selected'));
  check('执行命令后面板关闭', palEl.hidden === true && PAL.open === false, String(palEl.hidden));

  /* ── 快捷键 ── */
  check('输入类控件被识别为打字目标',
    isTypingTarget({ tagName: 'INPUT' }) && isTypingTarget({ tagName: 'TEXTAREA' })
    && isTypingTarget({ tagName: 'SELECT' }) && isTypingTarget({ tagName: 'DIV', isContentEditable: true })
    && !isTypingTarget({ tagName: 'BUTTON' }), 'tag guard');
  openShortcuts();
  var helpEl = document.getElementById('shortcuts');
  var helpBody = document.getElementById('helpBody');
  check('帮助浮层可打开', helpEl.hidden === false, String(helpEl.hidden));
  check('帮助渲染键帽与说明', helpBody.innerHTML.indexOf('class="kbd"') >= 0
    && helpBody.innerHTML.indexOf('help-row') >= 0, helpBody.innerHTML.slice(0, 120));
  closeShortcuts();
  check('帮助浮层可关闭', helpEl.hidden === true, String(helpEl.hidden));

  /* ── 指标卡迷你趋势 ── */
  globalThis.__indicators = [
    { year: 2022, indicator_key: 'GDP', value: '30' },
    { year: 2023, indicator_key: 'GDP', value: '33' },
    { year: 2024, indicator_key: 'GDP', value: '36' }
  ];
  var sparkBox = document.createElement('span');
  grid.__qa = function (sel) { return sel === '.metric-spark' ? [sparkBox] : []; };
  var sparkHtml = await render({
    cards: [{ label: 'GDP', value: '36', unit: 'US$', dimension: 'China',
              dimension_key: '中国', label_key: 'GDP', note: 'note' }],
    dimension: 'China', dimension_key: '中国'
  }, 'en');
  check('卡片含趋势容器', sparkHtml.indexOf('metric-spark') >= 0, sparkHtml.slice(0, 160));
  await new Promise(function (r) { setTimeout(r, 30); });
  check('有跨年序列时画出折线', sparkBox.innerHTML.indexOf('<svg') >= 0
    && sparkBox.innerHTML.indexOf('<path') >= 0, sparkBox.innerHTML.slice(0, 120));
  check('折线悬浮给出起止值', String(sparkBox.title).indexOf('2022') >= 0
    && String(sparkBox.title).indexOf('2024') >= 0, String(sparkBox.title));

  /* 单点序列不画折线（趋势至少需要两个点） */
  globalThis.__indicators = [{ year: 2024, indicator_key: 'GDP', value: '36' }];
  sparkBox.innerHTML = '';
  await render({
    cards: [{ label: 'GDP', value: '36', unit: 'US$', dimension: 'China',
              dimension_key: '中国', label_key: 'GDP', note: 'note' }],
    dimension: 'China', dimension_key: '中国'
  }, 'en');
  await new Promise(function (r) { setTimeout(r, 30); });
  check('单点序列不画折线', sparkBox.innerHTML === '', sparkBox.innerHTML.slice(0, 80));

  /* ── 数据洞察 ── */
  globalThis.__insights = {
    year: 2024, prev_year: 2023,
    movers: [
      { indicator: 'Inflation (CPI)', indicator_key: '通货膨胀率(CPI)', unit: '%', change_pct: -46.5 },
      { indicator: 'GDP growth', indicator_key: 'GDP增长率', unit: '%', change_pct: -8.5 }
    ],
    rank_indicator: 'GDP growth',
    rank_shifts: [
      { dimension: 'Singapore', dimension_key: '新加坡', rank_prev: 11, rank_now: 4, delta: 7 }
    ],
    coverage: { rows: 10, economies: 1, indicators: 10, comparable: 10 }
  };
  var grid2 = document.getElementById('insightsGrid');
  grid2.__qa = function (sel) {
    return sel === '.insight-card' ? [document.createElement('div')] : [];
  };
  await loadInsights();
  var insHtml = grid2.innerHTML;
  check('洞察渲染三张卡', (insHtml.split('insight-card').length - 1) === 3, String(insHtml.slice(0, 80)));
  check('洞察含同比榜单', insHtml.indexOf('Inflation (CPI)') >= 0
    && insHtml.indexOf('46.5%') >= 0 && insHtml.indexOf('down') >= 0, insHtml.slice(0, 120));
  check('洞察含名次变动', insHtml.indexOf('Singapore') >= 0
    && insHtml.indexOf('11 → 4') >= 0, insHtml.slice(0, 120));
  check('洞察含覆盖计数', insHtml.indexOf('insight-chip') >= 0
    && insHtml.indexOf('<b>10</b>') >= 0, insHtml.slice(0, 120));

  globalThis.__insights = { year: 2024, prev_year: 2023, movers: [],
    rank_shifts: [], rank_indicator: '', coverage: {} };
  await loadInsights();
  check('无洞察给空态', grid2.innerHTML.indexOf('empty-state') >= 0
    && grid2.innerHTML.indexOf('No insights available yet') >= 0, grid2.innerHTML.slice(0, 120));

  globalThis.__results = results;
  globalThis.__done = true;
})().catch(function (e) {
  globalThis.__fatal = (e && e.stack) || String(e);
  globalThis.__done = true;
});
`;

vm.runInContext(read(I18N_JS) + "\n;\n"
  + read(APP_JS) + "\n;\n" + DRIVER, context, { filename: "public+bundled-driver.js" });

/* 等驱动跑完（loadOverview 是 async，桩 fetch 用真实 Promise） */
const deadline = Date.now() + 10000;
while (!sandbox.__done && Date.now() < deadline) {
  await new Promise((resolve) => setTimeout(resolve, 5));
}

if (sandbox.__fatal) {
  console.error("FATAL: " + sandbox.__fatal);
  process.exit(1);
}
if (!sandbox.__done) {
  console.error("FATAL: 驱动未在 10s 内完成（前端逻辑可能挂起）");
  process.exit(1);
}

let failed = 0;
for (const r of sandbox.__results) {
  if (!r.ok) failed += 1;
  console.log(`[${r.ok ? "PASS" : "FAIL"}] ${r.name}${r.ok ? "" : " -> " + r.detail}`);
}
console.log(`\n结果：${sandbox.__results.length} 项检查，${failed} 项未通过`);
process.exit(failed ? 1 : 0);
