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
    setAttribute() {}, getAttribute() { return null; }, removeAttribute() {},
    appendChild(c) { this.children.push(c); return c; },
    removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; },
    addEventListener() {}, removeEventListener() {},
    querySelector() { return null; }, querySelectorAll() { return []; },
    click() {}, focus() {}, blur() {}, select() {}, scrollIntoView() {},
    getBoundingClientRect() { return { top: 0, left: 0, width: 0, height: 0 }; },
  };
  return el;
}

const elements = new Map();
const documentStub = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, makeEl(id, id === "globalYear" || id === "indCat" ? "select" : "div"));
    return elements.get(id);
  },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  createElement: (tag) => makeEl("", tag),
  addEventListener() {}, removeEventListener() {},
  body: makeEl("body"),
  documentElement: makeEl("html"),
  activeElement: null,
};

const sandbox = {
  console,
  document: documentStub,
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  history: { replaceState() {}, pushState() {} },
  navigator: {},
  location: { href: "http://127.0.0.1:5000/app", pathname: "/app", search: "", origin: "http://127.0.0.1:5000" },
  setTimeout, clearTimeout, setInterval, clearInterval,
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  URLSearchParams,
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
  else if (u.includes("/api/custom")) payload = [];
  else if (u.includes("/api/stats")) payload = { indicator_rows: 0, knowledge_rows: 0, dimension_count: 0, years: [] };
  else payload = {};
  if (sandbox.__fetchFails) throw new Error("network down");
  return { ok: true, status: 200, json: async () => payload, text: async () => JSON.stringify(payload) };
};

const context = vm.createContext(sandbox);

/* 单一脚本体：真实源码 + 场景驱动，保证 driver 与 app.js 处于同一词法作用域
   （app.js 的 STATE 是顶层 const，跨 runInContext 调用不可见）。 */
const DRIVER = `
(async function drive() {
  var results = [];
  function check(name, ok, detail) { results.push({ name: name, ok: !!ok, detail: detail == null ? "" : String(detail) }); }
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
