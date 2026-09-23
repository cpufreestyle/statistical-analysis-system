# Changelog

All notable changes are recorded here.

Versioning follows semver: `pyproject.toml` carries the latest released version and every
independent batch gets its **own tag + release** (batches are never merged into one release).
Older entries keep their original date + batch grouping.

Format follows [Keep a Changelog](https://keepachangelog.com/); tags are `Added`, `Changed`,
`Fixed`, `Security` and `Docs`.

## [Unreleased]

### Added

- **InfiniSynapse 集成强化：AI 基于真实数据解读。** `src/analyzer.py` 的 `new_task()`/`analyze()`
  新增 `files`/`images` 入参，并新增 `build_facts_files()`、`render_files_as_text()`、`with_facts()`；
  `src/cli.py` / `src/web.py` / `src/report.py` 把本地检索到的真实统计作为「事实文件」随任务送入，
  AI 只依据这些数字解读（延续「不编造数字」原则）。
- **新增 `src/stats/sql_engine.py`（SQL 计算引擎）。** 用一条 SQL 的 `MAX(CASE WHEN …)` 绑定全部变量，
  把含 K 个变量的自定义分析从 2K 次点查降为 1 次；输出与原 Python 引擎逐位一致。
  可用 `QU_STAT_CUSTOM_ENGINE=sql` / `--engine sql` / `?engine=sql` 切换，默认仍为 `python`。
- **新增 `src/infini_skill.py`（按 agent_infini Skill 规范）。** 统一凭证链（`~/.agent_infini/config.txt`）、
  资源预检（`task context`）、审计链接（`console_url`）、稳定 `taskId`，并新增只读端点 `GET /api/infini_skill`。

- **新增 `src/insights.py`（数据洞察计算层）与只读端点 `GET /api/insights`。**
  纯计算、无本地化：`movers()` 取同维度内同比变化最大的指标（上一年缺失或为 0 则剔除）、
  `rank_shifts()` 选覆盖经济体最多的指标并计算名次变动、`coverage()`；`src/web.py` 用
  `labels.label`/`slug` 一处本地化并附带 `*_key`/`*_slug`，结果可由 `/api/indicators` 复算。
  已登记 `src/api_docs.py::ENDPOINTS` 与 `scripts/check_i18n.py`（双语契约门禁）。
- **看板命令面板（`Ctrl`/`⌘ + K`）。** 模糊匹配、`↑`/`↓`/`Home`/`End`/`Enter`/`Esc` 键盘导航、
  combobox ARIA；命令项按当前真实状态（`window._years`/`window._dimOptions`/`.suggestion-chip`）动态生成。
- **全局快捷键 + 帮助浮层。** `1`–`5` 切换视图、`/` 聚焦查询框、`?` 打开帮助、`Esc` 关闭浮层；
  输入类控件聚焦时自动让位（`isTypingTarget`）。
- **主题三态切换 + 防闪白。** `qu_theme_v1` 持久化 `auto`/`light`/`dark`（`THEME_ORDER`），
  `<head>` 内联防闪白脚本先落 `data-theme`；暗色令牌改为 `:root[data-theme="dark"]` 与
  `@media (prefers-color-scheme:dark)` 双入口、同一份令牌。
- **指标卡迷你趋势 sparkline。** 一次 `/api/indicators?dimension=KEY` 取跨年序列并按 `indicator_key`
  分组绘制；纯装饰（`aria-hidden`），取数失败静默降级。
- **新增 `public/theme.css`（全站主题令牌的唯一事实来源）与只读路由 `GET /theme.css`。**
  把原先分散在两处的令牌收敛到一份文件：`public/style.css` 的 `:root` 与 `public/index.html`
  内联 `:root` 各自定义了一整套灰阶/蓝色，取值还不一样（`#F9FAFB`/`#E5E7EB` vs
  `#F8FAFC`/`#E2E8F0`），同一站点两个页面灰度不一致。现在 `/` 与 `/app` 都在自己的样式
  之前引入它；深色保留「手动 + 跟随系统」两个入口、同一份值，并新增 `--nav-bg` / `--band-bg`
  语义令牌让落地页组件随主题翻转。
- **落地页接入三态主题。** 补上与 `/app` 一致的 `<head>` 防闪白预置脚本、导航栏主题切换按钮
  与三态循环逻辑，沿用同一个 `qu_theme_v1` 存储键——此前落地页只跟随系统偏好，在看板切到
  深色后回到首页仍是一片白。

### Changed

- **数据库索引与写入优化（`src/db.py`）。** 新增自然键复合唯一索引 `ux_indicators_key` 与
  `ix_indicators_dimension`；`upsert_indicators` 改用 `INSERT … ON CONFLICT DO UPDATE`；
  连接级 PRAGMA（WAL / synchronous=NORMAL / 大缓存 / busy_timeout 等）。实测精确查找 **12.1×**、
  批量 upsert **14.4×**、零全表扫描。
- **初始化与连接池。** `init_db()` 改为进程内只跑一次（新增 `force` 形参）；显式连接池
  （本地 `QueuePool(5+10)`、Vercel `NullPool`、`pool_pre_ping`、`check_same_thread=False`）。
  实测热请求下 `init_db()` 由 3.5ms 降至 **0.001ms**。
- **消除重复取数（`src/stats/indicators.py`）。** 新增 `_val_unit()`，把指标函数里「取值 + 取单位」
  两次点查合并为一次，数值与单位完全一致。
- **HTTP 缓存与压缩（`src/web.py`）。** 统一加 ETag + 条件请求（命中返回 **304**）；对文本响应启用
  **gzip**（≥500B）。实测 `/api/indicators` 由 9916B 压至 1658B（**-83%**）。
- **AI 调用超时对齐（`src/analyzer.py`）。** 连接/读取超时分离（连接 5s）；SSE 等待上限默认由 110s
  调整为 **45s**（`INFINI_MAX_WAIT` 可覆盖），避免 Serverless 请求挂死。
- **UI 体验批次（看板三轮迭代）。** 自绘折线/排名图新增悬浮读数（最近年份吸附、竖直参考线、
  触屏支持；排名图补全被截断的经济体名与单位）；指标总表二次查询加骨架屏与 `aria-busy`，
  图表取数显示顶部进度条并保留旧图直至新数据到达；图表维度多选写入分享链接并可还原；
  指标卡大数字改紧凑记数（zh 万/亿、en K/M/B/T，精确值进 `title`，表格/CSV 仍全精度）；
  智能查询/自定义分析/公报结果区与 toast 补 `aria-live`；同消息 toast 去重；
  统一空态组件（图标+标题+说明）；≤640px 顶栏控件分组换行；清理 `.header-search` 等
  死代码与未使用的 `--radius-xl` 令牌。
- **看板「数据洞察」区块。** 三张骨架卡分别呈现同比变动最大指标、名次跃升/滑坡、口径覆盖，
  随年份、维度、语言联动刷新（挂接 `init` / `syncYear` / `syncDimension` / `refreshLang`）。
- **看板 UI 细节收尾。** `.wb-tabs` 吸顶（`position:sticky; top:var(--header-h)`）；
  `public/i18n.js` 的 `ZH2EN` 补齐命令面板 / 快捷键 / 主题 / 洞察约 40 个键；
  删除 `.mini-chart` / `.mini-bar` 死代码，新增 `.insight-*` / `.section-desc` 样式。
- **主题令牌统一下沉。** `style.css` 不再自带 `:root` 深色覆写（删掉 105 行重复定义），
  只留页面级布局令牌；`index.html` 删掉自己的灰度/蓝色定义与半套深色规则，圆角两页取值
  本就不同（看板 8/12、落地页 10/16），仍留在各自页面。原 `--radius-xl` 确认无人引用后删除。
- **落地页深色带与导航改走语义令牌。** `.tech-stack` / `.footer` 原先写死 `var(--gray-900)`，
  深色模式下灰阶反相会让它们翻成白底白字而整块消失；`.nav` 的半透明底同理。

### Docs

- 新增根目录 **`INFINISYNAPSE_INTEGRATION.md`**（人读）与 **`AGENT_CHANGES.json`**（机读）变更记录。
- 新增根目录 **`HANDOFF-2026-09-23.md`** 项目交接（自包含）。

### Fixed

- **回归修复（本轮自查发现）。** ① ETag / 条件请求此前对所有 200 响应启用，会把 HTML 的
  `Cache-Control: no-store` 改成 `no-cache`，违反「页面永不缓存」契约——现**仅对 JSON 接口**启用；
  ② 新增路由 `/api/infini_skill` 未登记进 `src/api_docs.py::ENDPOINTS`，触发文档一致性门禁——已补齐。
  全量 `pytest`（125 项）恢复全绿。
- **修复看板「增强能力」加载即失效的回归（真实浏览器验证时发现）。** `app.js` 里
  `try { initTheme(); initShortcuts(); initPalette(); }` 写在 `init()` 内、位于 `THEME_KEY` /
  `THEME_ORDER` / `THEME_META` 等 `const` 声明之前，一执行就踩暂时死区抛 `ReferenceError`，
  又被 `try/catch` 静默吞掉——页面看着毫无异常，但 `Ctrl`/`⌘`+`K`、`?`、`1`–`5`、`/` 全部失效，
  主题按钮的图标与文案也不同步。现已移到文件末尾执行，且失败要 `console.error` 留痕；
  `tests/frontend_behavior.mjs` 新增 6 条「加载即初始化」哨兵场景守住这个顺序。
- **小号文字对比度不达 WCAG AA。** 29 处 10–12px 灰字由 `--gray-400` 升至 `--gray-500`
  （白底 2.54:1 → 4.83:1，深色底 4.0:1 → 5.9:1），`.metric-tag` 底色同步改浅；
  另修 `compactNum()` 对空值返回「0」而非「—」的边界缺陷。

## v1.5.2 — 2026-09-22 — UI quality pass (`3b00c03`…`d07cf55`)

### Changed

- **指标卡左对齐、单位不折行。** `.metric-card` 由居中改为左对齐（统计机构惯例）；
  `.metric-unit` 加 `white-space:nowrap`，消除 "100 million USD" 折成两行的视觉脱节。
  grid 最小列宽由 220px 降至 180px，5 卡不再出现 4+1 孤行。
- **英文单位文案规范化。** `USD 100M / CNY 100M / 100M people` →
  `100 million USD / 100 million CNY / 100 million people`，
  `data/labels.csv` 与 `public/i18n.js` 两侧同步（逐字一致门禁把守）。
- **去除界面 emoji 图标。** 11 条 ZH2EN 键值对摘除 emoji；5 条与纯中文键重复的条目
  合并（避免 conflicting-duplicate-key 门禁变红）；`app.html` 的 `data-i18n` 属性与
  可见文本同步更新。侧栏装饰性 emoji（📚🗄️）保留在 `<span class="icon">` 内，不参与翻译。
- **头部链接样式收敛。** 首页 / API 文档两个 chip link 的内联 `style` + `onmouseover` /
  `onmouseout` 提为 `.chip-link` CSS 类，补 `:focus-visible` 状态。
- **遗留键修正。** `data-i18n="全国统计分析"` → `"亚太统计分析"`（区级遗留）。

### Added

- **SSE 解析行为测试**（`tests/test_analyzer.py`，3 项）。按 `str` 与 `bytes` 两种行形态喂
  `_iter_events`，锁住 v1.5.1 那处「显式解码」修复：去掉解码后 `bytes` 用例即以
  `TypeError: startswith first arg must be bytes or a tuple of bytes, not str` 变红。
  类型门禁只在带 `py.typed` 的 `requests` 版本下报警，行为门禁则与依赖版本无关。
- **Tab 键盘导航（WAI-ARIA）。** `role="tablist"` 容器支持 ArrowLeft / ArrowRight / Home / End，
  roving tabindex；`tests/frontend_behavior.mjs` 新增 7 项行为场景（总计 18 项）。
- **CSS 回归断言。** `test_metric_unit_nowrap_in_css` 对 `public/style.css` 断言
  `.metric-unit` 含 `white-space:nowrap`，防止未来误删。
- **section-link 可访问。** "查看全部指标 →" 补 `href="#panel-indicators"`，Tab 键可达。

## v1.5.1 — 2026-09-21 — Quality gates wired (`c8853bf`…`e3f648d`)

### Added

- **内嵌资产漂移门禁。** CI 重跑 `scripts/embed_pages.py` 后逐字节比对已提交的 `src/pages.py`
  与 `src/seed_data.py`，差异即红——Vercel 无构建步骤、直接服务仓库里的内嵌页，
  「改了 `public/` 忘跑 embed」过去只能靠人工发现，漏提交会直接把过期前端推上线。
- **前端关键行为可执行检查**（`tests/frontend_behavior.mjs` + `tests/test_frontend.py`）。
  用 node 的 `vm` 直接执行仓库里的 `public/app.js` / `i18n.js`（零依赖、无 `package.json`、
  无构建），覆盖空看板兜底文案、切回亚太出口、中文原词泄漏、`dimension_key` 判重、
  有数据渲染、取数失败态等 11 项；并含反向用例（破坏兜底判据后检查必须变红）。
- **冷启动自愈链路测试**（`tests/test_web.py`）。在隔离的临时 SQLite 上跑真实副作用，
  验证「恢复旧快照 → 清表 → 重播种 → 清 KV」按序发生、健康链路不产生告警，
  并区分「KV 恢复失败」与「KV 清理失败」两条日志。
- **`public/i18n.js` ↔ `data/labels.csv` 逐字一致校验**（`tests/test_labels.py`）。
  解析前端字典并与标签包逐条比对，重合词条数下限防「解析失效导致空跑」，
  另检查字典内无自相矛盾的重复键——「两处逐字一致」从书面约定变成机器门禁。
- **类型门禁接入 CI**（新增 `types` 作业，`basedpyright==1.39.9` 跑 `src/`，失败即红）。
  此前 `[tool.basedpyright]` 只在 `pyproject.toml` 里声明、从未被执行。

### Fixed

- 类型门禁接入时暴露并修掉的 **10 处类型缺陷**：`db_info()` 由 `dict[str, object]` 改为精确的
  `DbInfo` TypedDict、`CONFIG` 值类型、`kv_store` 的 Redis 端点/Token 缺失时不再对 `None`
  调 `rstrip`（此前会拼出 `Bearer None` 请求头）、`key_of` 返回类型收敛为 `str`、
  `localize_indicators` 形参改用协变的 `Sequence`（`list[IndicatorRow]` 传 `list` 才不报错）。
- CI 显式声明 Node 运行时（`actions/setup-node`），前端行为检查不再依赖环境里恰好有 node。
- **SSE 行解析改为显式解码**（`src/analyzer.py`）。`requests` 2.34 起自带 `py.typed`，把
  `iter_lines()` 的元素标注成 `bytes`，与 `decode_unicode=True` 的实际返回（`str`）不符，
  新类型门禁据此在 CI 报 2 处 `startswith` 参数错误、本地（`requests` 2.33 无标注）却是 0。
  改为 `bytes` 才解码、否则原样使用，两种 `requests` 版本下行为与类型都成立。

### Changed

- **CI 运行时对齐当前 LTS**：三个作业的 `actions/checkout` / `setup-python` / `setup-node` 升到 `v7`、
  node 固定 `24`（与本地一致）。此前 CI 注解报「Node.js 20 已弃用，被强制跑在 Node.js 24」，
  警告会淹没真实问题。
- **`runs-on` 由 `ubuntu-latest` 改为 `ubuntu-24.04`。** `ubuntu-latest` 将于 2026-10-19 自动切到
  Ubuntu 26——那会让一个没改代码的提交凭空变红；镜像升级改为显式动作。

### Docs

- `HANDOFF.md`：线上部署与 KV 自愈状态改为已验证、补充自愈失败分支的日志去向
  （`app.logger` → stderr → Vercel Observability / `vercel logs`）、测试规模对齐至 **121 项**。
- `CONTRIBUTING.md`：本地检查清单加入 `basedpyright`，并说明类型门禁为阻塞项、只覆盖 `src/`。
- `CITATION.cff`：`version` 从长期未维护的 `0.1.0` 对齐到 `1.5.1`、`date-released` 更新，
  使引用元数据与实际发布版本一致。

## v1.5.0 — 2026-09-20 — Overseas launch fixes (`bf444ab`)

### Fixed

- **旧快照防线改为特征判别。** 冷启动丢弃旧 KV 快照的判据从「行数 < 30」改为「缺『亚太』聚合维度」——
  51 行的区级 demo 快照不再漏网；线上部署新代码后首次冷启动自动清 KV 重灌真实亚太数据。
- **`data/labels.csv` 补登记「全国 / 全区」**，英文接口与界面不再直漏中文（`National` / `Entire region`）。
- **空看板不再是死路**：所选维度无数据时提供「View Asia-Pacific / 切换到亚太」按钮回退聚合口径。

### Changed

- **英文文案通改为国际统计机构口径**（sentence case、IMF/World Bank 术语）：`Overview`、`Ask the AI`、
  `Run analysis`、`GDP by industry`、`National Bureau of Statistics of China`、指标名对齐官方英译等，
  覆盖 `public/i18n.js` 全量字典与 `data/labels.csv`（两处逐字一致）。
- 侧栏「知识库与数据源」排序改为 世界银行 Open Data 优先（亚太产品的主数据源）。

## v1.4.0 — 2026-09-18 — UI polish (`a9d2c37`)

### Changed

- 指标卡与 Quick Start 网格从固定 4 列改为 `repeat(auto-fit, minmax(220px/200px, 1fr))`，
  解决 3 张或 5 张卡时右侧/下方出现空列的问题；响应式断点不再显式覆盖网格列数。
- 顶栏品牌隐藏重复的英文副标题，标题更干净。
- 工作台标签 active 状态加蓝色背景与 3px 下划线，标签图标放大，状态更醒目。
- 图表容器升级为白底卡片 + 阴影 + 更大圆角/内边距；
  折线图增大画布、左外边距与字号，新增 Y 轴线，网格线改用深色也可见的 `--gray-200`；
  排名条图标签区与条形略放大、圆角加大。
- 区块徽章由灰阶改为蓝色系，提高识别度。

## v1.3.0 — 2026-09-18 — Open-source readiness (`130e793`, `c70ce1b`)

### Added

- **`LICENSE` (MIT).** The READMEs claimed MIT while the repository contained no licence file,
  which legally means “all rights reserved”. Fixed, and `pyproject.toml` now declares it.
- `CONTRIBUTING.md` + `CONTRIBUTING.zh-CN.md` — the six hard rules, the “changing an endpoint
  means touching four places” checklist, and the test/PR conventions.
- `SECURITY.md` — private reporting channel, in/out of scope, admin-token and `/tmp` SQLite
  notes, and an explicit “no third-party audit yet”.
- `CHANGELOG.md` (this file) and `CITATION.cff` (CFF 1.2.0, points at the GitHub mirror).
- `.github/PULL_REQUEST_TEMPLATE.md` and bug-report / feature-request issue templates.
- `GET /privacy` — bilingual privacy & data statement rendered server-side (`src/privacy_page.py`,
  reuses `api_docs.SHARED_CSS`). It answers the three questions people actually ask: what is
  stored (the `qu_lang_v2` key in `localStorage`), under which licence the data is used
  (World Bank CC BY 4.0), and whether AI is on (off by default). Linked from the landing-page
  footer, `/docs` and the error pages; listed in `sitemap.xml`.
- New tests for the privacy page (placeholder substitution, both languages, the three
  answers, reachability, sitemap). Suite grows 106 → 111.

### Changed

- `.markdownlint-cli2.jsonc` now owns the ignore list (`data/`, `node_modules/`, `.venv/`,
  assistant memory directories). Running `markdownlint-cli2 "**/*.md"` locally used to report
  3083 issues, all of them outside the project; the CI job now reuses the same config.

### Docs

- Both READMEs: CI / licence / Python badges, the `## License` section now separates code
  (MIT) from data terms, and a navigation table for CONTRIBUTING / SECURITY / CHANGELOG /
  CITATION / privacy / docs.
- `HANDOFF.md` §0, §5, §6.7 and §9 refreshed.

## v1.2.0 — 2026-09-18 — Usability & quality (`202f428`)

### Added

- `GET /docs` — bilingual API reference rendered server-side (no JavaScript): 22 endpoint
  cards covering all 23 routes, parameter tables, `curl` examples and the shared conventions
  (`src/api_docs.py`). Entry points on both pages and in `sitemap.xml`.
- Branded bilingual error pages for 404 / 405 / 500 (`src/error_pages.py`); `/api/*` paths
  still answer with JSON.
- `hreflang` alternates (`en`, `zh-CN`, `x-default`) on `/`, `/app` and `/docs`, each pointing
  at its own URL.
- Chart accessibility: chart SVGs carry `role="img"` + `aria-label` + a `<desc>` data summary,
  the legend is `aria-hidden`, containers are `aria-live="polite"`.
- `tests/test_stats_core.py` — 17 tests for `yoy` / `share` / `rank_items` / `fmt_pct`
  boundaries and for `report.build_bulletin_data()`. Suite grows 74 → 106.
- A test that compares `app.url_map` against `src/api_docs.py`'s `ENDPOINTS` in both
  directions, so a new route cannot ship without documentation.

### Fixed

- **Admin-endpoint regression**: the landing page and dashboard sidebar were reading
  `/api/db`, which returns 403 in production — the counters silently showed “—”. Added the
  public read-only `GET /api/stats` and pointed both pages at it.
- `/api/collect` returning 403 on the hosted build now shows an explanatory message instead of
  failing silently.

### Changed

- Chart series colours moved from hard-coded hex values to `--ch-1…--ch-14` tokens, with a
  brighter palette in dark mode (the old values fell below 3:1 contrast on white).
- `config.yaml`: `infinisynapse.prefer_language` `zh_CN` → `en_US` (matches the product
  default). `.gitignore` now covers `.python-version`.

### Docs

- Both READMEs updated (API reference link, `/api/stats`, admin-endpoint 403 behaviour,
  `QU_STAT_BASE_URL` / `QU_STAT_ADMIN_TOKEN`, new modules in the architecture map) and
  corrected where they had drifted: the data-source table still listed Australia and the
  United States, and the panel count and ranking size were stale.
- `HANDOFF.md` refreshed end to end; the rule set grows from five to six.

## 2026-09-18 — Performance, hardening, UX & SEO batch (`7d3faab`)

### Added

- Security response headers (`nosniff`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`, CSP locked to `'self'`; HSTS over HTTPS).
- Admin-endpoint token auth (`QU_STAT_ADMIN_TOKEN` → `X-Admin-Token` or `?token=`); 403 in
  production when unset, open in local development.
- Content-hash long caching for static assets (`?v=<sha256[:12]>`), `no-store` for HTML and
  APIs; dark mode via `prefers-color-scheme`; skip links, `:focus-visible`,
  `prefers-reduced-motion`; JSON-LD structured data on both pages.

### Changed

- Removed the Google Fonts dependency — the UI uses a system font stack, so the project now
  has **zero external CDN dependencies**.
- Share card switched from SVG to a 1200×630 PNG generated by `scripts/make_og_image.py` and
  embedded as base64.

## 2026-09-17 — Asia-Pacific caliber (`d8915f2`, `40e3784`)

### Fixed

- Dropped the United States and Australia dimensions: they are not Asia-Pacific economies.
  `ap_macro.csv` goes from 837 rows / 14 dimensions to 720 rows / 12; the label pack and the
  collector's default indicator list were cleaned up too so they cannot come back.

## 2026-09-17 — Tests and CI baseline (`7f2d4f2`)

### Added

- `tests/` with 66 unit tests (label contract, analyzer dispatch, web routes, embed
  regression) and a `conftest` that isolates the test database. `.github/workflows/ci.yml`
  runs pytest, boots the server for `check_i18n.py`, then an optional markdownlint pass.

## 2026-09-17 — Pluggable AI provider (`458cc56`)

### Added

- `src/analyzer.py` supports `infinisynapse` (default, auditable SSE) and `openai_compat`
  (any OpenAI-compatible `/chat/completions`: OpenAI / OpenRouter / Groq / DeepSeek / local
  Ollama · vLLM). Selected with `AI_PROVIDER`; without a key the app degrades to local
  statistics instead of erroring.

## 2026-09-17 — SEO baseline (`b25f754`)

### Added

- `robots.txt`, `sitemap.xml`, `og:image`, and `<html lang>` that follows `?lang=` /
  `Accept-Language` instead of being hard-coded.

## 2026-09-16 — Export, share links and charts (`fc269b4`, `ea6f615`)

### Added

- `GET /api/export.csv` plus “export” buttons in the indicator and chart panels, and a share
  link that preserves the current filter state through `history.replaceState`.
- Hand-drawn SVG line and ranking charts (no chart library), fulfilling the visualisation P0.

## 2026-09-16 — Server-side identifier localization (`f0d63b1`)

### Changed

- Data identifiers are localized server-side from `data/labels.csv`, so the REST API is
  bilingual rather than only the dashboard. Every record exposes the display value plus
  `*_key` (canonical Chinese key) and `*_slug` (stable ASCII key).

## 2026-09-16 — Public data, English-first, bilingual READMEs (`3895850`)

### Changed

- The dataset moved to real public sources (World Bank Open Data, China NBS, China Customs);
  all synthetic sample data was removed. English became the default language and both READMEs
  were published.

## 2026-09-07 → 2026-09-13 — Bilingual UI

### Added

- Chinese / English toggle persisted in `localStorage`, English copies for static UI strings,
  and a fix for the “switched back to Chinese but still English” bug.

## 2026-07-27 → 2026-07-31 — Early batches

### Added

- Web dashboard and CLI, user-defined custom analyses over `custom_analysis.yaml`, collection
  from World Bank Open Data, Vercel deployment with optional KV snapshot restore, direct
  InfiniSynapse Server API integration replacing the `agent_infini` binary.

### Changed

- Data layer consolidated on SQLAlchemy Core; all internal-organization wording removed so
  the project reads as a neutral public tool.
