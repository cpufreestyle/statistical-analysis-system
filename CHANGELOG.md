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

- **AI 解读结果缓存（新增 `src/ai_cache.py`）。** 同一问题 + 同一份事实数据 ->
  直接复用上一次解读，不再重复打云端。缓存键覆盖**提示词全文 + 全部事实文件内容 +
  语言 + 模型身份**：事实文件里带的就是送入模型的那些数字，数据一变键就变，绝不会
  把旧数据的解读配给新数据（守住「AI 不得编造数字」的底线）。只缓存成功结果，
  失败与空文本一律不写缓存。两级：进程内 LRU + TTL（`QU_STAT_AI_CACHE_MAX` 默认
  128 条、`QU_STAT_AI_CACHE_TTL` 默认 3600 秒），以及可选的 Upstash Redis（跨冷启动、
  跨实例，仅当 KV 已配置；Redis 抖动只降级为「未命中」，绝不影响主链路）。
  总开关 `QU_STAT_AI_CACHE=0`。
- **新增只读端点 `GET /api/ai-cache`。** 返回命中 / 未命中计数、L1 容量与 Redis
  是否可用——用来证明「重复提问真的没有重复打云端」。已同步登记
  `src/api_docs.py::ENDPOINTS` 与 `scripts/check_i18n.py`（双语契约门禁）。
- **看板「最近提问」。** `localStorage`（`qu_recent_q_v1`）记住本机最近 6 个问题，
  点一下直接重跑；与命令面板互补——面板适合「想到什么搜什么」，这里适合「刚才那个
  再问一遍」。隐私模式下存取抛错时整体静默降级，不影响主链路。

- **新增可观测性三件套：`GET /healthz` 探活 + 慢查询告警 + 慢请求告警。**
  `/healthz` 始终返回 200，用响应体的 `status`（`ok` / `degraded`）表达健康程度：
  扁平 JSON、字段集合恒定，与 `/api/stats` 同风格。**永不触发播种、永不鉴权**，
  库不可达时 `status` 退化为 `degraded`、两个行数给 0（键仍在），监控端不必判
  「这个键这次有没有」。附带 `version`（读自 `pyproject.toml`——手写常量会与发布版本
  漂移，`importlib.metadata` 在非 editable 安装下拿到的是打包时的旧号，两者都会在排查时
  指错版本）与 `uptime_s`。
  - **慢查询**：`before_cursor_execute` / `after_cursor_execute` 配对计时，超过
    `QU_STAT_SLOW_QUERY_MS`（默认 200ms）打 `src.db` WARNING，语句压成单行并按 200 字
    截断；`handle_error` 里同步出栈，失败语句不会让长连接上的时间栈无限增长。`<=0` 关闭。
  - **慢请求**：`before_request` / `after_request` 计时，超过 `QU_STAT_SLOW_REQUEST_MS`
    （默认 1000ms）打 `src.web` WARNING，输出 `method=… path=… status=… ms=…` 平铺字段。
    与慢查询告警配对：前者说「这条请求慢」，后者说「慢在哪一句 SQL」。
  - 观测代码一律不得影响主流程：阈值解析失败静默回落默认值，探针 try/except 兜底。
  - 新增 `tests/test_obslog.py` 14 条；`/healthz` 已登记 `src/api_docs.py::ENDPOINTS`
    （新增 `ops` 分组）与 `scripts/check_i18n.py`。
- **知识库语义召回：`search_knowledge()` 支持中英跨语言检索，并补齐 34 条测试。**
  `search_knowledge()` 是 `/api/ask`、统计公报与 `/api/knowledge` 的共同上游，也是
  「AI 不得编造数字」链条的第一环，此前**零测试覆盖**且只做纯字面匹配：
  用 35 条真实提问实测 **17 条完全召回不到**（英文提问召回不到中文条目、
  中文提问召回不到英文条目），top-1 只有 18/35。
  - **中英概念映射**：新增 15 组同义 / 别名概念表（GDP / 增长 / 工业 / 零售 / 投资 /
    人口 / 收入 / 人均 / 来源 / 修订 / 比较 / 贡献 / 货币 / 亚太），命上任一成员即整组
    加权，跨语言召回因此成立。成员刻意只收「领域实体 / 关系」，不收「口径 / 定义 /
    是什么」这类元词——后者几乎每条正文都有，收进来只会全员加分、稀释排序。
  - **字段权重**：标题 / 标签命中 `_CONCEPT_TITLE_WEIGHT`（6），正文 / 出处命中
    `_CONCEPT_BODY_WEIGHT`（3），同一概念每多命中一个不同成员再加
    `_CONCEPT_EXTRA_MEMBER`（1）。早期不分字段（固定 3 分）实测 top-1 只有 19/35：长正文里
    偶然提到 `exchange rate` 的条目会压过标题即命中 `YoY` 的正解。
  - **`source` 字段进入匹配文本**：早先只拼 `title + tags + content`，漏了出处——
    而「工业统计报表制度」「World Bank Open Data」正是强相关信号。
  - 改后同机同条件实测：召回漏检 **17 → 0**，top-1 **18/35 → 31/35**；剩余 4 条都是
    「两条都高度相关、只是先后偏好」，均已落在 top-2 内，不为调这 4 条而过拟合。
  - 新增 `tests/test_knowledge.py` 34 条：跨语言召回 11 例、top-1 排序 11 例、成员密度
    压过「顺带一提」、`source` 参与匹配、概念表不含元词，以及 `lang` 语种过滤 / `limit` /
    无缓存 / 空与垃圾查询安全等既有契约。
  - 多词成员支持「紧凑形态」匹配：成员与查询双边去空白后再比对，因此
    `gross domestic\nproduct` 这类被拼行 / 多余空格拆开的提问仍能召回。
  - `search_knowledge` 仍是「全量取出 + Python 侧打分」；真要接向量检索时换掉这一个
    函数即可，调用方无感。
- **新增 3 条只读静态路由：`GET /i18n-dict.js`、`GET /i18n-dict-landing.js`、`GET /landing.css`。**
  i18n 字典/运行时拆分与落地页样式外置的载体；均由 `src/web.py` 的 `_ASSET_FILES` 统一登记，
  版本号与 `/theme.css`、`/style.css` 等走同一套「按资产算 sha256」逻辑。
  Vercel serverless 读不到仓库里的 `public/`，这些文件同步内嵌进 `src/pages.py`
  （`scripts/embed_pages.py`，入口仍是 `public/app.html`）。
- **新增 `tests/test_i18n_split.py` 9 条字典漂移守卫。** 落地页子集字典是派生产物，
  测试钉死：键集合与 `index.html` 逐字一致、取值与全量字典逐字一致（别把 `"…"` 写丢）、
  运行时文件不被塞回字典（绕过「纯运行时」断言也没用，体积不变量会抓到）。
- **新增 `test_pages_module_is_in_sync_with_public_sources` 嵌入同步守卫。** 改过 `public/` 却忘了
  重跑 `scripts/embed_pages.py` 时直接红（此前只能靠人工记得）。

- **新增 `tests/test_code_split.py` 6 条分割结构守卫。** 拆文件真正会悄悄坏掉的只有两件事：
  同名声明跨文件重复定义（后者静默覆盖前者，行为随加载顺序漂移），以及 core 在分块加载
  完成前引用分块专属声明（ReferenceError，或被 try/catch 吞掉后整块功能静默失效）。
  行为由 `tests/frontend_behavior.mjs` 的 6 条哨兵把守，这里钉住结构：声明不重复、
  两个分块互不引用、core 只在 `openTab()` 的 `.then` 回调里、或被 `typeof X === 'function'`
  探测过的位置引用分块专属名字。

### Changed

- **批量指标写入从逐行 execute 改为单条 executemany（约 23 倍）。** `upsert_indicators()`
  原先为每一行单独 `execute`，每行都要重走一遍 SQLAlchemy 的语句编译；729 行种子数据
  实测 **206.6ms**，冷启动播种与 `POST /api/reseed` 都走这条路。改为构建**一条**
  `INSERT ... ON CONFLICT DO UPDATE` 后 `executemany(list_of_rows)`（一次编译、N 次绑定），
  实测降到 **8.9ms**；`/api/reseed` 端到端约 10ms。
  语义完全不变，由 `tests/test_import.py` 逐条钉住：写入条数、重复写入幂等、
  同 (year, category, indicator, dimension) 自然键**更新而非新增**、以及唯一索引缺失时
  的「逐行删除+插入」回退路径同样幂等。失败时整批回退并改走逐行路径
  （原实现是逐行 try/except，粒度更细但最终结果一致）。
- **`load_file()` 补齐导入校验，与种子数据共用同一套规则。** 原先它把 DataFrame 的记录
  **直接 cast** 成 `IndicatorRow`：用户传错文件时会在数据库层炸出原始 `KeyError`，
  或者更糟——静默写入垃圾。现在抽出 `_coerce_row()`，种子 CSV 与用户 CSV/Excel 共用；
  必需列缺失 / 年份或数值不可解析 / 数值非有限（`inf`、`nan`）的行会被跳过并在日志里
  报数，**整份文件都不可用时抛 `ValueError`** 而不是返回 0——用户传错文件时必须立刻
  看到失败，而不是收到一句「已导入 0 条」还以为成功了。
  顺带修掉两个隐蔽问题：pandas 的缺失单元格是 `float('nan')`，原先会写成字面量
  `"nan"` 字符串；`inf` 这类非有限值原先能直接落库。
- **冷启动瘦身：3 个可选重依赖改为函数内延迟导入。** `import src.web` 是 Vercel 每个冷容器
  的固定开销（实测约 330ms CPU）。三处只在特定分支才用得到的依赖原先都写在模块顶层：
  ① `src/kv_store.py` 的 `import requests`（连同 urllib3 / email / http 整棵树）——只在
  `_request()` 里用得到，而所有 KV 公开函数都先查 `kv_available()`；
  ② `src/stats/custom.py` 的 `import yaml`——只在读写 `custom_analysis.yaml` 时用得到；
  ③ `src/db.py` 的 `import yaml`——Vercel 分支（`QU_STAT_DB_DIR` 已设）直接以
  `CONFIG = {}` 兜底，根本不解析 `config.yaml`。
  改为函数内导入后，KV 未配置时 `import src.web` 只加载 `flask` + `sqlalchemy`。
  A/B 实测（同机同条件、清 `__pycache__`、11 次取中位数）：`import src.web` 的进程内 CPU
  由 **390.6ms 降至 328.1ms（−16%）**；`-X importtime` 累计 424.5ms → 约 390ms。
  写法参照既有先例 `src/stats/sql_engine.py`。
  新增 `tests/test_cold_start.py` 4 条门禁：在**子进程的全新解释器**里断言导入图
  （pytest 自身与 `tests/test_analyzer.py` 已加载过 requests / PyYAML，进程内查
  `sys.modules` 查不出问题），并带一条反向兜底——删掉 `db.py` 的惰性 `import yaml` 会让
  本地分支抛 `NameError`，此时测试必须转红（已实测）。
- **顺带纠正一项技术债判断：拆分 `src/pages.py` 并不能加速冷启动。** 实测 `compile()`
  解析这 274KB（21 行 / 9 个字面量）仅 **2.6ms**，`import src.pages` 在 `import src.web`
  全程里只占约 3.6ms；瓶颈完全在 flask / sqlalchemy。因此「拆分 pages.py 降冷启动」
  不再列为待办——为 1% 的收益去承担 embed 漂移门禁的验证成本并不划算。

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

- **`/api/ask` 与统计公报接入解读缓存。** 命中时在响应里透出 `cached: true`、
  公报里透出 `ai_cached: true`，前端在 AI 解读卡片上打出「⚡ 来自缓存」徽标并显示
  本次耗时；未命中时不加任何字段，对外形状向后兼容。CLI 不接（一次性进程，
  退出即失效，没有复用窗口）。
- **新增语义令牌 `--ok-fg` / `--ok-bg` / `--ok-bd`。** 「来自缓存」徽标用的正向
  强调色：浅色深字浅底（`#166534` on `#ECFDF5`，对比度 6.1:1）、深色亮字深底
  （`#4ADE80` on `#0E2A1F`，8.6:1），都达 WCAG AA。四个入口（浅色 + 两个深色）
  同步定义，`theme.css` 仍是唯一事实来源。
- **前端接线顺带补上顺序护栏。** 「最近提问」的 `const` 声明放在 `init()` **之前**，
  并在注释里写明原因——本文件历史上的回归正是增强能力的 `const` 声明晚于 `init()`，
  一执行就踩暂时死区、异常又被 `try/catch` 吞掉，页面毫无异常但能力全失效。
- **SQLite 连接池改为复用连接，Vercel 形态同样受益（约 4–7 倍）。** `src/db.py` 早先在
  Vercel / Serverless 形态（`QU_STAT_DB_DIR` 已设）下用 `NullPool`，理由是
  「避免跨请求句柄残留」——但那是**远程库**的经验（连接可能被服务端回
  收）。本项目的 SQLite 库文件就在**同一个实例自己的 /tmp** 里，不存在服务端回收；
  万一实例被冻结再解冻导致连接失效，也由既有的 `pool_pre_ping=True` 兜住。
  NullPool 的真实代价是**每次查询都新建一条 SQLite 连接**：同库、同查询 A/B
  实测 **1.57ms → 0.17ms**；按端点算（同一基准脚本、只切 poolclass）
  `/api/insights` 4.77→0.99ms、`/api/overview` 3.79→0.80ms、
  `/api/stats` 3.60→0.98ms、`POST /api/knowledge` 4.49→0.60ms。
  并发安全由既有 PRAGMA 兜底（`journal_mode=WAL` 读不阻塞写 +
  `busy_timeout=30000`）；12 线程（8 读 + 4 写）压测 23 万行读取 + 80 次并发写 **0 错误**。
  保留应急开关 `QU_STAT_DB_POOL=null` 可退回 NullPool（线上免改代码）。
  新增 `tests/test_db_pool.py` 9 条，其中用 `connect` 事件数**真实 DBAPI 连接**的新建次
  数，把「连接被复用」钉成行为级守卫（改回 NullPool 时精确报「25 次查询新建
  25 条连接」）。
- **`/api/infini_skill` 从 56ms 降到 0.26ms（约 217 倍）。** 该端点每次请求要把 `agent_infini` CLI
  路径解出 **3 遍**（`resolve_cli_path()` 被 web 层、`preflight`、`run_skill_cli`
  各调一次），而每次都要 `shutil.which()` 逐个 stat PATH 里的目录——本机 PATH
  有 51 项，单次实测 17.3ms，合计约 52ms。改为：PATH 扫描结果进程内缓存
  （`functools.cache`；PATH 与环境变量在运行期不变，而 `AGENT_INFINI_CLI` 的优先级判断
  仍在 `resolve_cli_path()` 里逐次求值、不进缓存），并让 `run_skill_cli()` 接受调用方
  已解析好的 `cli`，消掉 `preflight` 里的重复解析。
- **i18n 字典与运行时拆成三个文件（落地页首访 gzip −16.3%）。** 原 `public/i18n.js` 把**全量 332 条**
  `ZH2EN` 字典与 `tr()`/`trData()` 运行时打成一个文件，而落地页实际只用到其中 **69 条（20.8%）**。
  现在拆为 `public/i18n-dict.js`（全量，看板用——`trData()` 要遍历 DOM，需要全量词条兜底）、
  `public/i18n-dict-landing.js`（落地页子集，派生产物）、`public/i18n.js`（只剩运行时，
  首行 `var ZH2EN = window.ZH2EN || {}`）。两个页面都遵循「先灌字典、再灌运行时」的顺序。
  实测（gzip，HTML + 全部依赖资产）：落地页首访 **22,417 → 18,753 B（−16.3%）**；
  重复访问（资产已缓存，只剩 HTML）**9,281 → 6,518 B（−29.8%）**。
  **同时诚实记录一处回退**：看板首访 **54,012 → 54,578 B（+1.05%）**——它本来就要全量字典，
  拆文件只多出两份文件各自的头部注释。没有粉饰，已在交接文档写明。
- **落地页 622 行内联 `<style>` 外置为 `public/landing.css`。** 落地页 HTML 是
  `no-store, must-revalidate`，内联样式等于**每次访问都重下这份 CSS**；抽出为独立文件后走
  `public, max-age=31536000, immutable`，二次起只剩 HTML。
- **静态资源版本号由「全站一个」改为「按资产各自算」（`_ASSET_FILES` → `_ASSET_VERS`）。**
  原先单一 `__ASSET_VER__` 占位符：任何资产变动都会让**所有**资产 URL 一起变、连带打穿全部缓存。
  现以 `src/web.py` 的 `_ASSET_FILES`（文件名 → 常量名，单一事实来源）为每个资产单独算
  `sha256[:12]`，页面占位符形如 `__STYLE_CSS_VER__`——只改落地页不再换掉看板的资产 URL。
- **`/favicon.ico` 由 404 改为 301 跳 `/favicon.svg`。** 浏览器与部分爬虫仍会按惯例请求
  `/favicon.ico`，此前必然 404：既浪费一次往返，也在控制台留噪声。

- **看板 JS 代码分割：`app.js` → core + 两个按需分块。** 首屏只留必需部分，图表与命令
  面板拆到 `public/app.charts.js` / `public/app.palette.js`，首次用到时由 `loadChunk()`
  动态注入 `<script>` 拉取——经典脚本共享全局词法环境，分块可以直接读写 core 里的 `const`，
  不需要打包器。`CHART` / `CHART_COLORS`、`fmtNum` / `compactNum` / `emptyState` 必须留在
  core：首屏指标卡与 sparkline 要用，`updateShareUrl()` / `exportChartCsv()` 也要读
  `CHART.currentKey`。实测（gzip，HTML + 全部依赖资产）看板首访 **54,578 → 48,210 B
  （−11.7%）**，其中 `app.js` **24,131 → 17,669 B（−26.7%）**；落地页首访
  **18,753 → 18,753 B（零回归）**。分块各 **6,637 B / 4,104 B（懒）**，只有图表用户、
  打开命令面板的用户才付。
  **同时诚实记录懒加载的代价**：用户打开图表 tab 后总字节会略高于拆分前（多两个 HTTP 请求
  分块各自的头部注释），这是按需加载的固有成本。
- **`refreshLang()` 改为守卫式调用 `initCharts()`。** `switchTab()` 是**同步**给
  `.wb-panel` 打上 `active` 的，而分块是异步拉的——一旦 `loadChunk('charts')` 失败，
  `#panel-charts` 会停在 active 但 `initCharts` 还是 undefined，此时切换语言会让
  `refreshLang()` 抛 ReferenceError，**后半段全部不执行**：`updateShareUrl()`、
  `themeApply()`、帮助浮层重渲染一起静默失效。改为与已有的 `renderHelp()` 守卫同款写法
  `typeof initCharts === 'function'`，并由 `tests/test_code_split.py` 钉住这类引用的安全位置。
- **`loadChunk()` 对没有分块的 tab 直接兑现（修掉本批引入的回归）。** `openTab('indicators')`
  会走 `loadChunk('indicators')`，但指标表的实现（`loadIndicators()`）本来就在 core 里、
  从没有对应分块文件。原实现照旧造一个 `<script>`：浏览器对该 URL 404 → `onerror` →
  reject，`openTab` 的 catch 随即弹「加载失败」，而 `loadIndicators()` 永远不跑——
  **指标面板静默失效**。改为 `if (!CHUNK_SRC[name]) return Promise.resolve();`。
  同时把 harness 的 `<script>` 桩改成复刻浏览器语义：未登记的 src 一律走 `onerror`，
  不再静默什么都不做（否则该 Promise 永远悬着，这类 bug 会被伪装成「还在加载中」），
  并补 1 条哨兵。6 条代码分割哨兵此前只被「0 项未通过」间接兜住、未登记进
  `SCENARIOS`——删掉任意一条 `test_frontend.py` 不会红，现已全部补登。

- **服务端取数三层优化（`/api/stats`、`/api/overview`、`/api/indicators?q=`）。**
  同机配对实测：新旧两棵树交替跑、各 3 轮取中位数（后台有远程桌面负载，故绝对值为
  负载下的水位，前后两棵树同窗口测量，差值可信）。
  ① `/api/stats` 消除两次全表扫描——`src/db.py` 新增 `distinct_values(column)`
  （白名单 `year` / `category` / `dimension`，`SELECT DISTINCT` 走覆盖索引；
  `EXPLAIN` 已确认）与 `query_indicator_pairs(year, pairs)`（一条
  `OR (专业=? AND 指标=?)` 取回多组合的全部维度行）；`src/stats/indicators.py` 的
  `available_dimensions` / `available_years` / `all_categories` 与 `src/web.py`
  KV 恢复路径的两处「先查全表再 set 去重」同步改调。**9.2ms → 1.6ms（约 5.8×）**。
  ② `/api/overview` 消除 N+1——`_find()` 新增可选 `rows` 形参：一次不限维度查询 +
  内存按回退顺序挑首条（唯一索引保证同组合不重复，「每个维度取首条」与逐维度点查
  结果一致）；`dimension_cards()` 用 `query_indicator_pairs()` 一条 SQL 预取上一年数据
  （同组合查过但无数据必须与未预取区分，否则会退化成逐组合点查）。
  中国口径 **18.6–19.0ms → 2.8ms（25 条 SQL → 6 条）**，亚太口径
  **14.4–14.9ms → 2.7ms（9 条 → 5 条）**。
  ③ `/api/indicators?q=` 本地化开销减半——profile 显示 729 行里 `normalize_lang`
  每行被调 5 次、`label` / `slug` 各 4 次，而四者都是只读标签包的纯函数：
  `normalize_lang` / `label` / `slug` / `localize_note` 加 `@lru_cache`，
  `reload()` 同步清理全部缓存（漏清任何一个 = 改完 `labels.csv` 后接口继续返回
  上一版文案，是正确性问题而非性能问题）。`q` 过滤的两处重复实现抽成
  `web._filter_by_query()`，语义不变（仍是「拼成一整串再整串 `in`」，
  跨字段查询词同样算命中；逐字段预过滤的等价写法已微基准排除，反而更慢）。
  `localize_indicators(en)` **5.8ms → 2.5ms**，端点 **15.1ms → 11.6ms（不带 q）/
  16.3ms → 12.4ms（q=popul）**。如实记录剩余去向：`query_indicators` 3.9ms、
  `q` 过滤 2.1ms、`jsonify` 1.4ms 仍在原地。
- **配套 5 条测试。** `tests/test_labels.py` 加「reload 必须失效全部纯函数缓存」
  （换两张假词条表验证缓存跟着走）与「四个热点函数必须带 lru_cache」结构哨兵
  （红绿已验证：摘掉装饰器即变红）；`tests/test_web.py` 加 `q` 过滤三条行为测试
  （命中本地化英文值、命中中文规范键、空 q 与不带 q 逐行一致）。
  全量 **265 项**测试全绿，`scripts/check_i18n.py` 全部通过。
- **「美观 / 实用性」视觉精修第一批（范式取自开源项目：shadcn/ui globals.css、
  Tailwind Preflight、Observable Plot 图表约定）。** 每项都有出处与结构哨兵（红绿已验证：
  删声明即变红），全部落在令牌与样式层，不动数据与接口。
  ① **选中态主题化**：`::selection` 跟随主题令牌，浅色 / 手动深色 / 跟随系统三个入口同步
  （此前是浏览器默认蓝底白字，深色界面上刺眼；shadcn 把 selection 做成令牌的同款思路）。
  ② **锚点跳转让出导航高度**：看板导航 sticky 52px、落地页导航 fixed 64px，`skip-link`
  的 `#main` 与 `#features` 等锚点跳转的落点此前被导航整块盖住——键盘用户碰到的第一个
  障碍。加 `scroll-padding-top`（shadcn 同款修法）。
  ③ **移动端两条基线**（Tailwind Preflight 同款）：锁定 iOS 横竖屏切换时的正文自动放大、
  去掉点击瞬间的蓝色高亮块，点击反馈交回 `:active` / `:focus-visible`。
  ④ **数字等宽全覆盖**：`tabular-nums` 从表格 `.num` 扩展到指标卡数值、洞察卡数值与排名、
  图表坐标轴刻度与排名条数值（SVG `<text>` 新增共享类 `.svg-num`；Observable Plot 等
  图表库对刻度数字的默认做法），切年切维度时数字列不再抖。
  新增 7 条结构哨兵，全量 **272 项**测试全绿；改 `public/` 后已重跑
  `scripts/embed_pages.py` 同步 `src/pages.py`。

- **视觉精修第三批：emoji 图标整体换成内联 SVG，空态文案分层。**
- **新增 `scripts/check_contrast.py`：WCAG 2.1 AA 对比度抽检（并接入 pytest 门禁）。**
  配对不是手写清单，而是**从样式表里扫出来**的：凡同一条规则里同时出现
  `color: var(--x)` 与 `background(-color): var(--y)` 就构成一对候选，新增组件自动
  纳入；三个主题入口（浅色 / 手动深色 / 跟随系统）各算一遍，`var()` 逐层解引用，
  半透明色按 alpha 与背景合成。阈值按字号分流：普通文本 4.5:1、大文本（≥24px 或
  ≥18.66px 粗体）3:1。首轮跑出 **67 个配对、3 个不达标**，全部是同一个真实缺陷：
  空态图标描边用 `--gray-400` 压在 `--gray-100` 圆底上只有 2.31:1（浅色），灰到几乎
  看不出形状——改为 `--gray-600`（6.87:1 / 8.51:1）后清零。
  新增 2 条测试：门禁本身 + 反向红绿（把 `.empty-icon` 改回 `--gray-400` 必须变红）。
  已知边界：跨规则继承的配色（如 `.data-table tr:hover td` 只设背景、颜色来自父规则）
  扫不到，报告里如实标注。

  emoji 的字形与配色由操作系统决定（Windows / macOS / Android 三套设计语言），在空态圆底、
  落地页特性卡这种大面积居中的位置差异最刺眼，也无法跟随主题令牌取色。参照
  heroicons / lucide / Bootstrap Icons 的共同做法，在 `public/app.js` 建 `ICONS` 白名单
  （24×24 网格、`currentColor` 描边、`fill:none`），配 `icon(name)` 取图函数（未命中退回
  `search`，永不渲染空白）；`emptyState()` 的入参从「字符」改成「图标名」。
  替换范围覆盖看板全部图标位：空态、洞察卡标题、AI 卡头（含公报）、「来自缓存」徽标、
  命令面板全部命令、侧栏卡片标题，以及 `app.html` 里的静态位（含主题三态按钮）。
  落地页 `index.html` 是自包含页面（不引 app.js），特性 / 流程 / 架构卡的 SVG 直接写在
  HTML 里，主题三态用内联脚本里一份最小的 `LANDING_ICONS`。
  同批补两件配套：**空态文案分层**——原先「暂无洞察 / 加载失败 / 无可展示数据」只有一行
  标题，现在都带上「下一步能做什么」的说明（9 条新 i18n 词条）；`.data-table` 表格区
  底色统一由 `.workbench` 提供后，表头实底会让边缘阴影只剩半截，故表头改透明并加注释锁死。
  新增 3 条结构哨兵（前端不得再出现 emoji、`.icon-svg` 基类两个样式表都要有且必须
  `inline-block`、`icon()` 必须有白名单兜底），全量 **281 项**测试全绿；红绿逐条验证过。
  实测冒烟：起真实服务 `GET /` 返回 16 个 `<svg>`、`GET /app` 10 个，全站 emoji 归零。

- **视觉精修第二批：宽表横向滚动的「还能滑」暗示 + 主题令牌补齐第三个入口。**
  `.data-table-wrap` 用四层 `background` 拼出边缘阴影：两条 `radial-gradient` 是阴影本体，
  `background-attachment: scroll` 钉在容器视口上，只在真有溢出时可见；两条同色
  `linear-gradient` 是遮挡层，`attachment: local` 随内容滚走，把已滚过处的阴影擦掉。
  这样**纯 CSS** 就能判断「是否溢出」，不需要 JS 监听 scroll（Radix / shadcn 的
  `ScrollArea` 反而是 JS 驱动，这里不需要那么重）。同时补
  `-webkit-overflow-scrolling: touch` 保住 iOS 惯性；`.data-table` 加 `min-width: 760px`——
  七列（单选钮 / 指标 / 专业 / 维度 / 数值 / 单位 / 来源）在窄屏原先被压成竖排碎片，
  现在整表横向滚动；`.insight-chip b` 的数值也接上 `tabular-nums`（第一批漏了它）。
  新增令牌 `--scroll-shadow`（浅色 `rgba(15,23,42,.16)`、深色 `rgba(0,0,0,.55)`），
  需要在浅色 / 手动深色 / 跟随系统**三个入口**同步——第三个入口一开始漏了，被既有门禁
  `tests/test_web.py::test_theme_css_is_the_single_source_of_tokens` 当场抓住
  （它逐名比对手动深色与跟随系统两块令牌集合）。
- 配套修正 `.data-table th` 不再铺底色（原 `--gray-25`）。纯 CSS 边缘阴影画在滚动容器的
  背景层上、位于表格**下方**，任何实底单元格都会把它挡住，左侧只剩半截阴影——这是该手法的
  前提（内容必须透背景）。`--gray-25` 与 `--surface` 在浅色下只差 1%，表头靠 2px 下边框 +
  大写 + 字重区分已足够；新增哨兵把「表头必须透明」钉住，防止加回底色而**静默**破坏
  横向滚动的可感知性。新增 5 条结构哨兵，全量 **277 项**测试全绿；改 `public/` 后已重跑
  `scripts/embed_pages.py`。

- **图表读数补齐触屏与键盘两条等价通道（`public/app.charts.js`）。** 自绘 SVG 的数值不在
  DOM 文本里，读数原先只有桌面 hover 一条路：触屏点一下抬手就没（浮层可能有多行数值），
  键盘用户更是完全摸不到。参照 WAI-ARIA 与 Observable Plot / Vega-Lite 的做法重写
  `attachLineTip` / `attachRankTip`，三种输入共用同一份渲染逻辑，差别只在出现与消失的时机：
  - 鼠标 hover：跟随指针，移出即消；
  - 触屏 tap：读数**钉住**不消失，点图内别处移动、点图外或按 Esc 收起
    （document 级 `touchstart` 监听只注册一次、按盒子去重，防切片重绘后监听泄漏）；
  - 键盘：SVG `tabindex="0"` 可聚焦，`←`/`→`（折线）、`↑`/`↓`（排名）逐点移动，
    `Home`/`End` 跳两端，`Esc` 收起，`focus` 即读出、`blur` 收起。
  读数同时写进 `.chart-live`（`position:absolute` + 1px + `clip-path: inset(50%)` 的视觉隐藏；
  **不用 `display:none`**——那会把它从无障碍树里摘掉，播报等于白修）。浮层自身仍是
  `aria-hidden`：它重复 SVG `<desc>` 的信息，屏幕阅读器走 live 区那条通道。
  「?」帮助浮层同步新增「图表快捷键」4 条与英文词条。
  新增 20 条行为断言（`tests/frontend_behavior.mjs`：63 → 83 项，含一条「浮层要落在当前行
  附近」）——排名图键盘定位原先写成 `(28/760) * 高度`，缩放分母用错，浮层会贴在 SVG 顶部，
  这条断言把它钉住（红绿已验证）+ 2 条红绿哨兵
  （摘掉 Esc 分支、把 `aria-live` 改成 `off` 都必须变红）+ 2 条结构哨兵
  （`.chart-live` 视觉隐藏写法完整、帮助浮层必须列出图表快捷键且说明词条齐全）。
  全量 **283 → 287 项**测试全绿；改 `public/` 后已重跑 `scripts/embed_pages.py`。
  如实记录代价：读数逻辑由约 40 行涨到约 180 行，且键盘定位需要把 `yFor` / `padTop`
  从 `renderLine` 透传进 `attachLineTip` 的 ctx——这是本次唯一的跨作用域耦合。

- **看板 JS 代码分割第二轮：`app.js` → core 加五个按需分块。** 指标总表 / 自定义分析 / 统计公报
  三个 tab 拆到 `public/app.indicators.js` / `public/app.custom.js` / `public/app.bulletin.js`，
  与图表 / 命令面板分块同一套约定（core 不引用分块声明；入口只有 `openTab()` 回调和
  `onLangRefresh()` 语言钩子）。实测（gzip，HTML 加全部依赖资产、LF 归一化）看板首访
  **48,055 → 46,746 B（−2.7%）**，其中 `app.js` **17,814 → 16,384 B（−8.0%）**；三个新分块各
  **2,345 / 2,860 / 1,859 B（懒）**。如实记录代价：五个 tab 全部打开过的重度用户总字节
  **+6,031 B** 且多 3 个 HTTP 请求，这是按需加载的固有成本。
- **修掉拆分引入的三个真实回归（结构测试抓不到、只有行为测试能抓的那类）。**
  ① `init()` 裸调已挪进自定义分析分块的 `loadCustomList()`，首屏即 ReferenceError、
  整页初始化中断——改为不在首访预取，首次打开该 tab 时 `initCustom()` 自会填充下拉。
  ② `syncYear()` / `syncDimension()` / 采集完成回调裸调 `loadIndicators()`，用户没打开过该 tab 时
  ReferenceError，把 toast、分享链接一起炸掉——改为 `refreshIndicatorsIfLoaded()` 的 `typeof` 守卫。
  ③ `tabAction()` 按引用传函数名：内联 onclick 在点击瞬间求值，头部命令面板按钮（palette 分块的
  唯一入口，快捷键绑定也在分块里）首访必炸 ReferenceError，**命令面板彻底打不开**——改为按**名字**
  在分块到位后解析（`tabAction('palette', 'openPalette')`），`app.html` 16 处调用点全部改传字符串。
- **修掉 palette 分块对另两个分块的交叉引用。** 「导出指标 CSV」「生成统计公报」两条命令直接引用
  `exportIndicatorsCsv` / `loadBulletin`：前者在 `paletteCommands()` 执行时就地求值，
  **命令面板自己先打不开**；后者运行命令时才炸。改为 `tabAction` 按名字延迟执行；
  `test_chunks_do_not_reference_each_other` 从 charts 与 palette 两两推广到全部分块对
  （注释与名字字符串不算引用，裸标识符才算）。
- **前端行为 harness 登记全部五个分块并新增 6 条哨兵**（首屏不预加载新分块、三个分块按需加载、
  面板按钮按名字解析、切年份不炸未加载分块），配套 2 条红绿哨兵（破坏 `tabAction` 名字解析、
  去掉 `typeof` 守卫都必须变红）与 1 条结构断言（`tabAction` 必须传名字字符串）。
  全量 **260 项测试**全绿。

### Docs

- 新增根目录 **`INFINISYNAPSE_INTEGRATION.md`**（人读）与 **`AGENT_CHANGES.json`**（机读）变更记录。
- 新增根目录 **`HANDOFF-2026-09-23.md`** 项目交接（自包含）。

### Fixed

- **修复 `/docs` 英文页唯一一处真实漏译：curl 示例里的中文 shell 注释。**
  `/api/indicators` 的 `example` 是单字符串（含 `# 或按关键词搜索（中英均可）`），渲染器
  `_endpoint_html()` 原先直接 `str(ep["example"])` 输出，英文页因此跟着显示中文注释。
  修复：渲染器改为兼容「单串 / `(zh, en)` 二元组」两种形态（与既有 `body` 字段同构），
  该 `example` 拆成中英二元组，英文注释改为
  `# or search by keyword (either language works)`。
  说明：示例载荷里的中文（`["国民经济", …]`、`"category": "通用"`、`"GDP 口径"`）
  是调用方必须原样使用的数据规范键，按设计不翻译。
  新增回归测试 `test_docs_english_page_has_no_chinese_comments`：遍历 `/docs` 英文页所有
  `<pre class="doc-pre">` 代码块，注释行（`#` / `//`）出现中文即失败（已验证「修复前红」）。

- **修掉 3 处英文界面裸显中文的漏译。** ① / ② 自定义分析的两个英文输入框占位符
  （`public/app.html` 的 `data-i18n-ph="英文名称（可选…）"` / `"英文说明（可选）"`）；
  ③ 命令面板的分组标签 `tr('示例问题')`（`public/app.js`）。三者的共同根因：
  `i18n.js` 的 `data-i18n` / `-html` / `-ph` 三个处理器都只做**精确字典查表**、没有
  `trData()` 兜底，所以「字典里没有」就等于「不翻译」。而 `scripts/check_i18n.py`
  只审 API 响应，看不到 DOM 与前端拼装串，这类泄漏因此一直漏网。
  修复：字典补 3 条（ZH2EN 332 → 335 条键），并新增 2 条覆盖测试把
  `data-i18n*` 属性值与 `tr()` / `trData()` 字面量参数钉在字典上。
- **修复 InfiniSynapse SSE 中文乱码（既有隐患，正确性问题）。** `analyzer._iter_events()`
  原先用 `iter_lines(decode_unicode=True)`，而服务端的 `text/event-stream` 并不声明
  `charset`，requests 便按 ISO-8859-1 解码，把中文解读搅成乱码（已用假云端实测复现：
  不开 charset 时结果与原文不等）。现改为读原始字节后显式
  `decode("utf-8", errors="replace")`——SSE 规范规定该类型恒为 UTF-8，且行分隔符
  `0x0A` 不会落在多字节序列中，逐行解码安全。`tests/test_analyzer.py` 新增 2 条回归
  （其中一条用按 requests 真实语义伪造的 latin-1 假响应，确保修的不是假问题）。
- **清掉 basedpyright 既有 9 个类型错。** `insights.py` 两处 `float()`/`int()` 入参、
  `report.py` 的 `list[dict[str, str]]` 实参、`sql_engine.py` 两处无效
  `cast("object", …)`、`web.py` 三处 `shift[...]` 索引（根源是 `dict[str, object]`）。
  改为精确 `cast` + 显式注解，并删掉随之失效的 2 条 `# type: ignore`。本地 basedpyright
  锁定 1.39.9（与 CI 同版本）后为 **0 errors / 0 warnings**。
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
- **修复 i18n 字典中一处重复键（死代码）。** `"AI 云端解读"` 在原字典里出现两次，
  两处取值完全相同（`"AI interpretation"`）；JS 对象字面量后者覆盖前者，先出现的那条永远读不到。
  现已去重，行为等价。生成侧同时加了断言：重复键**取值不一致**时拒绝自动去重，
  避免悄悄吞掉真实的翻译分歧。

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
