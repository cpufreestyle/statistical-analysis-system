/* 落地页主题逻辑的行为检查（零依赖、零构建）。

   public/index.html 是自包含页面（不引 app.js），主题三态的实现在文件末尾的
   内联 <script> 里。本 harness 把那段脚本原样抽出来，在 Node vm 里跑，
   断言它与 /app 的 app.js 是同一套约定（同一个 localStorage 键、同一个三态顺序、
   同样在系统偏好变化时跟随）。

   由 tests/test_frontend.py 调起（`node tests/landing_theme_behavior.mjs`）。
   改坏 index.html 的主题分支，这里就会红。 */
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
/* 允许把被测页面换成临时副本（tests/test_frontend.py 用它验证本 harness 真会红），
   避免为了「破坏一下看看」去改写仓库里被跟踪的 public/index.html。 */
const INDEX_HTML = process.env.QU_STAT_INDEX_HTML || path.join(ROOT, "public", "index.html");

/* 取出页面末尾那段内联脚本（含主题逻辑）。只认「最后一个 <script>…</script>」，
   <script src=…> 没有闭合体，天然不会被匹配到。 */
function landingScript() {
  const html = fs.readFileSync(INDEX_HTML, "utf8");
  const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  if (!blocks.length) throw new Error("public/index.html 里没有内联 <script> 块");
  const tail = blocks[blocks.length - 1];
  if (!tail.includes("qu_theme_v1")) {
    throw new Error("末尾内联脚本里找不到主题逻辑（qu_theme_v1），抽取规则可能已失效");
  }
  return tail;
}

const results = [];
function check(name, ok, detail) { results.push({ name, ok, detail }); }

/* 每个场景都用一个全新的上下文执行脚本——这样才能模拟「重新打开页面」
   并验证 localStorage 里的选择真的被读回来了。 */
function runLanding({ saved = null, darkSystem = false } = {}) {
  const elements = new Map();
  const makeEl = (id) => ({
    id, tagName: "BUTTON", innerHTML: "", textContent: "", title: "", value: "",
    style: {}, children: [],
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    setAttribute(k, v) { this._a = this._a || {}; this._a[k] = String(v); if (k === "title") this.title = v; },
    getAttribute(k) { return (this._a || {})[k] ?? null; },
    appendChild(c) { this.children.push(c); return c; },
    addEventListener() {}, removeEventListener() {},
    dispatchEvent() { return true; }, click() {}, focus() {}, blur() {},
  });
  const store = new Map();
  if (saved !== null) store.set("qu_theme_v1", saved);
  const mqListeners = [];
  const sysPref = { dark: darkSystem };   /* 可变：测试里改它模拟系统切换 */
  const matchMedia = (q) => ({
    matches: /dark/.test(String(q)) ? sysPref.dark : false,
    media: String(q),
    addEventListener: (t, fn) => { if (t === "change") mqListeners.push(fn); },
    removeEventListener() {},
    addListener: (fn) => mqListeners.push(fn),
    removeListener() {},
  });
  const sandbox = {
    console,
    document: {
      getElementById: (id) => { if (!elements.has(id)) elements.set(id, makeEl(id)); return elements.get(id); },
      querySelector: () => null, querySelectorAll: () => [],
      createElement: (t) => makeEl(""),
      addEventListener() {}, removeEventListener() {},
      body: makeEl("body"),
      documentElement: makeEl("html"),
      activeElement: null,
    },
    localStorage: {
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, String(v)),
      removeItem: (k) => store.delete(k),
    },
    matchMedia,
    setTimeout, clearTimeout,
    /* 页面脚本还挂了滚动监听与 /api/stats 取数；桩里给空实现即可，本 harness 只验主题 */
    addEventListener() {}, removeEventListener() {},
    fetch: () => Promise.resolve({ json: () => Promise.resolve({}) }),
  };
  sandbox.window = sandbox;
  sandbox.window.matchMedia = matchMedia;
  vm.createContext(sandbox);
  vm.runInContext(landingScript(), sandbox, { filename: "index-inline-theme.js" });
  return { sandbox, store, btn: elements.get("themeToggle"), mqListeners, sysPref };
}

/* 1. 无存储值 → auto：跟随系统 */
let r = runLanding({ darkSystem: false });
check("落地页默认主题为 auto", r.sandbox.document.documentElement.getAttribute("data-theme") === "light",
  String(r.sandbox.document.documentElement.getAttribute("data-theme")));

r = runLanding({ darkSystem: true });
check("系统深色时 auto 解析为 dark", r.sandbox.document.documentElement.getAttribute("data-theme") === "dark",
  String(r.sandbox.document.documentElement.getAttribute("data-theme")));

/* 2. 手动选择优先于系统 */
r = runLanding({ saved: "light", darkSystem: true });
check("手动浅色优先于系统深色", r.sandbox.document.documentElement.getAttribute("data-theme") === "light",
  String(r.sandbox.document.documentElement.getAttribute("data-theme")));

r = runLanding({ saved: "dark", darkSystem: false });
check("手动深色优先于系统浅色", r.sandbox.document.documentElement.getAttribute("data-theme") === "dark",
  String(r.sandbox.document.documentElement.getAttribute("data-theme")));
check("主题按钮有可读标签",
  String(r.btn.getAttribute("aria-label")).includes("Dark")
  && String(r.btn.getAttribute("aria-label")).includes("深色"),
  String(r.btn.getAttribute("aria-label")));

/* 3. 循环顺序 auto → light → dark → auto（与 app.js 的 THEME_ORDER 一致） */
r = runLanding({ saved: "auto", darkSystem: false });
const root = r.sandbox.document.documentElement;
const seq = [root.getAttribute("data-theme")];
const stored = [];
for (let i = 0; i < 3; i++) {
  r.sandbox.cycleTheme();
  seq.push(root.getAttribute("data-theme"));
  stored.push(r.store.get("qu_theme_v1"));
}
check("落地页主题循环顺序 auto/light/dark", stored.join(",") === "light,dark,auto", stored.join(","));
check("深色档位落在 system 浅色下的 dark", seq.join(",") === "light,light,dark,light", seq.join(","));

/* 4. 重新打开页面读回手动选择 */
r = runLanding({ saved: "dark", darkSystem: false });
check("落地页主题选择已持久化", r.sandbox.document.documentElement.getAttribute("data-theme") === "dark",
  String(r.sandbox.document.documentElement.getAttribute("data-theme")));

/* 5. 系统偏好变化时 auto 跟随；非 auto 档位不跟随（与看板一致） */
r = runLanding({ saved: "auto", darkSystem: false });
check("落地页监听系统配色变化", r.mqListeners.length >= 1, String(r.mqListeners.length));
r.sysPref.dark = true;
r.mqListeners.forEach((fn) => fn());
check("系统变深后 auto 跟随到 dark", r.sandbox.document.documentElement.getAttribute("data-theme") === "dark",
  String(r.sandbox.document.documentElement.getAttribute("data-theme")));

r = runLanding({ saved: "light", darkSystem: false });
r.sysPref.dark = true;
r.mqListeners.forEach((fn) => fn());
check("手动档位不跟随系统变化", r.sandbox.document.documentElement.getAttribute("data-theme") === "light",
  String(r.sandbox.document.documentElement.getAttribute("data-theme")));

let failed = 0;
for (const r of results) {
  if (!r.ok) failed += 1;
  console.log(`[${r.ok ? "PASS" : "FAIL"}] ${r.name}${r.ok ? "" : " -> " + r.detail}`);
}
console.log(`\n结果：${results.length} 项检查，${failed} 项未通过`);
process.exit(failed ? 1 : 0);
