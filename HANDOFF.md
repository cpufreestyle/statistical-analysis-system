# 项目交接 · 亚太统计分析系统

> 交接对象：接手本仓库的开发/维护者
> 交接时间：2026-09-17
> 交接时 HEAD：以 `git log --oneline -1` 为准（本节不写死哈希，避免提交后即过期）
> 本文件已纳入版本控制

---

## 0. 一分钟速览

| 项 | 内容 |
| --- | --- |
| 对外名称 | Asia-Pacific Statistical Analysis System |
| 一句话定位 | 用**公开真实数据**做的亚太宏观经济统计与 AI 解读看板 |
| 数据来源 | 世界银行 Open Data · 中国国家统计局 · 海关总署（全部公开、无需鉴权） |
| 技术栈 | Python 3.12 + Flask + SQLAlchemy Core + SQLite；前端原生 HTML/CSS/JS，**零构建** |
| 仓库 | Gitee `cpufreestyle/statistical-analysis-system`（origin）· GitHub 同名（github） |
| 分支 / 版本 | `master`；已发版至 `v1.5.0`（6 个 tag 全部推送 Gitee `origin` + GitHub `github`，详见 §1） |
| 线上 | Vercel 项目 `qu-stat-system`，生产别名 `https://qu-stat-system.vercel.app`（**本次未探活，见 §5**） |
| 测试 / CI | ✅ `tests/` **113 项**单元测试 + `.github/workflows/ci.yml`（pytest + 起服务跑 `check_i18n.py` + 可选 markdownlint）——见 §6.1 |
| 许可证 | MIT（见 `LICENSE`；`data/` 沿用来源方条款：World Bank Open Data CC BY 4.0） |
| 开源配套 | `LICENSE` · `CONTRIBUTING.md`（+ 中文版）· `SECURITY.md` · `CHANGELOG.md` · `CITATION.cff` · `.github/` 的 PR 与 issue 模板 · `.markdownlint-cli2.jsonc` |

**唯一护城河**：AI 解读 + 每行数据可溯源到 `note` + 明确禁止编造数字。
对标 Our World in Data 没有 AI 层，而海外用户对 AI 幻觉极敏感——这是对外主卖点。

---

## 1. 当前状态

- 工作区**干净**，无未提交改动（`HANDOFF.md` 本身除外）。
- 最近几批工作（时间倒序，均已推送 Gitee `origin` + GitHub `github` 双远程）：
  1. `a9d2c37` —— **外观优化**：指标卡/Quick Start 自动填充网格、工作台标签高亮、
     图表容器与坐标轴升级（白底卡片/阴影/Y 轴线/字号）、顶栏品牌去重、徽章蓝色系
  2. `130e793` —— **开源项目配套 + 隐私声明页**：补 `LICENSE`(MIT，此前只在文档里声称 MIT
     却没有该文件)、`CONTRIBUTING`(中英双版)、`CHANGELOG`、`SECURITY`、`CITATION.cff`、
     PR/issue 模板、`.markdownlint-cli2.jsonc`；新增应用内 `/privacy` 双语声明页
  3. `202f428` —— **可用性与质量**：`/docs` API 参考页、图表可访问性、
     自定义错误页、hreflang、`/api/stats` 公开统计端点（修线上 403 导致的数字缺失）
  4. `7d3faab` 终极优化：性能加载 · 生产加固 · 体验可访问性 · SEO 结构化数据
  5. `40e3784` 更新交接文档 —— 收口亚太分类口径与数据规模
  6. `d8915f2` 移除美国与澳大利亚维度，收口亚太分类口径
- 本地服务可跑（`/` `/app` `/docs` `/privacy` 均 200）。
- **已发版（2026-09-18）**：`v1.1.0`=`7d3faab`（性能·加固·体验·SEO）、
  `v1.2.0`=`202f428`（可用性与质量）、`v1.3.0`=`130e793`+`c70ce1b`（开源配套+隐私页）、
  `v1.4.0`=`a9d2c37`（外观优化）、`v1.5.0`=`bf444ab`（出海收尾：文案机构口径+旧快照特征判别+空看板兜底）；
  `pyproject.toml` version 对齐为 `1.5.0`，
  CHANGELOG 批次已折入版本标题。

---

## 2. 上手：跑起来

```bash
# 依赖（Windows 下用仓库内 venv）
.venv/Scripts/python.exe -m pip install -r requirements.txt

# 起服务（默认绑定 0.0.0.0:5000）
.venv/Scripts/python.exe -m src.cli web --port 5000
```

打开 `http://127.0.0.1:5000/`（落地页）与 `/app`（看板）。

**冷启动会自动播种**：库为空时载入 `data/ap_macro.csv` + `data/nbs_cn.csv` 与知识库种子，
幂等、不覆盖已有数据。

自检：

```bash
# 双语契约检查（需服务在跑）——英文接口残留中文即失败
python scripts/check_i18n.py

# CLI 冒烟
python -m src.cli ask "2024 GDP" --lang en
python -m src.cli report --year 2024 --dimension 中国 --lang zh
python -m src.cli db info
```

> ⚠️ 沙箱/代理环境下测本机 HTTP 必须绕代理，否则连接被劫持会误判成服务没起来：
> curl 加 `--noproxy '*'`；Python 用 `build_opener(ProxyHandler({}))`。

---

## 3. 代码地图

| 路径 | 职责 | 注意 |
| --- | --- | --- |
| `public/` | 前端源码（`index.html` / `app.html` / `app.js` / `i18n.js` / `style.css`）+ SEO（`robots.txt` / `sitemap.xml` / `og-image.png` / `favicon`） | **改完必须跑内嵌脚本**；字体走系统栈，无外部 CDN；图表序列色板为 `--ch-1…14` 令牌（深色模式自动换亮色） |
| `data/ap_macro.csv` | 世界银行真实种子：720 行 / 12 维度 / 2019–2024 / 10 指标 | 脚本生成，已提交 |
| `data/nbs_cn.csv` | 中国国内明细：9 行（仅 2024） | 带 BOM，读取处已处理 |
| `data/labels.csv` | **标识符标签包**（`kind,key,slug,en`）：专业 7 / 指标 26 / 维度 12 / 单位 8 | i18n 唯一事实来源，加词条不用改代码 |
| `data/qu_stats.db` | 运行时 SQLite | 已被 gitignore |
| `scripts/fetch_wb_data.py` | 从世界银行抓数 | `--from 2019 --to 2024` |
| `scripts/embed_pages.py` | 内嵌 `public/` → `src/pages.py`、`data/` → `src/seed_data.py` | 见 §4 约定 1；二进制按 base64 |
| `scripts/make_og_image.py` | 纯 Pillow 生成 `public/og-image.png`（1200×630 分享卡片） | 改完重跑并提交产物 |
| `scripts/check_i18n.py` | 双语 API 契约检查 | 新增端点后建议同步加进 CHECKS |
| `src/web.py` | Flask 应用：页面、REST API、错误页、冷启动播种 | 23 条路由，见 §7 |
| `src/api_docs.py` | `/docs` API 参考页（服务端渲染双语，端点清单是唯一事实来源） | 改路由必须同步 `ENDPOINTS`，测试会校验一致性 |
| `src/error_pages.py` | 品牌一致的 404 / 405 / 500 页（双语，复用 style.css 令牌） | 接口路径仍返回 JSON |
| `src/privacy_page.py` | `/privacy` 隐私与数据声明页（双语、零 JS，复用 `api_docs.SHARED_CSS`） | 回答对外三问：收集什么 / 数据从哪来 / AI 是否外发 |
| `api/index.py` | Vercel Serverless 入口 | 见 §6 的部署注意 |
| `LICENSE` | MIT（仅覆盖代码）；`data/` 沿用来源方条款 | 2026-09 前**一直缺失**，只在文档里声称 MIT |
| `CONTRIBUTING.md` + `CONTRIBUTING.zh-CN.md` | 贡献指南：六条硬约定、改端点要同步四处、测试与 PR 规范 | 中英双版，与 README 双版一致 |
| `CHANGELOG.md` | 按「日期 + 批次」记录（版本号尚未与提交对齐，见 §6.2） | 发版时再归并为版本小节 |
| `SECURITY.md` | 漏洞报告渠道 + 在/不在范围内的说明 | 写明「未做第三方安全审计」 |
| `CITATION.cff` | 引用元数据（CFF 1.2.0） | 作者用 GitHub 用户名，不含邮箱 |
| `.github/` | `PULL_REQUEST_TEMPLATE.md` + `ISSUE_TEMPLATE/{bug_report,feature_request}.md` | 模板带项目专属检查项（内嵌 / 测试 / i18n / 文档） |
| `.markdownlint-cli2.jsonc` | lint 忽略项（含助手工作目录） | 否则本地跑 lint 会被几百条无关记录淹没 |
| `src/labels.py` | 标识符本地化：`label` / `slug` / `key_of` / `localize_payload` | i18n 核心 |
| `src/cli.py` | 命令行入口（11 个子命令） | 多数支持 `--lang` |
| `src/db.py` | SQLAlchemy Core over SQLite（指标宽表 + 知识库表） | |
| `src/loader.py` | 种子载入 + 用户 CSV/Excel 导入 | |
| `src/collect.py` | 采集流水线（可插拔数据源、限速） | |
| `src/stats/indicators.py` | 各统计专业指标函数（维度锚定） | 单位取自数据行，勿写死 |
| `src/stats/query.py` | 双语自然语言查询引擎（本地规则） | |
| `src/stats/custom.py` | 自定义分析引擎（表达式沙箱） | |
| `src/report.py` | 统计公报（结构化数据 + 文本渲染） | |
| `src/analyzer.py` | InfiniSynapse Server API 客户端（SSE） | 云端可选，失败自动回退本地 |
| `src/knowledge.py` | 双语知识库 + 关键词召回（轻量 RAG） | |
| `src/kv_store.py` / `src/kv_sync.py` | 可选 KV 持久化与恢复 | |
| `src/pages.py` / `src/seed_data.py` | **生成物**，勿手改 | 由内嵌脚本产出，但需提交 |
| `api/index.py` | Vercel Serverless 入口 | 见 §6 的部署注意 |
| `.workbuddy/memory/` | 助手工作记忆（**本地，不随仓库分发**） | 见 §8 |

---

## 4. 六条不可违反的约定

1. **改完 `public/` 任何文件、或重新抓数后，必须跑 `scripts/embed_pages.py` 再重启服务。**
   Serverless 部署包读不到 `public/` 与 `data/`，运行期靠 `src/pages.py` / `src/seed_data.py`
   的内嵌副本。漏跑 → 你看到的是旧前端资源，会浪费大量时间排查"改了没生效"。
   文本资源按 UTF-8 内嵌；二进制资源（`og-image.png`）按 **base64** 内嵌（常量名带 `_B64`，
   运行期 `base64.b64decode` 后以 `image/png` 提供）——见 `scripts/embed_pages.py` 的 `BINARY_FILES`。

2. **数据标识符以中文规范键入库；对外本地化只在 `data/labels.csv` + `src/labels.py` 一处发生。**
   入库用中文（数据文件可读、与官方口径逐字对齐），出接口前按语言本地化。
   每个标识符给三层：`{field}` 本地化值 + `{field}_key` 中文规范键 + `{field}_slug` ASCII 稳定键。
   前端**不再翻译数据**（`public/i18n.js` 只负责静态 UI 文案与结构键展示名）。

3. **未登记词条原样返回，绝不抛异常。**
   于是新增指标不会打断既有调用。反向解析同理：`?dimension=Atlantis` 原样透传后查不到数据，
   而不是静默替换成默认值——静默改写比报错更难排查。
   （`?dimension=China` / `china` / `中国` 三者等价。）

4. **API Key 一律走环境变量**，禁止写进被跟踪的 `config.yaml`。

5. **发布约定：每个独立变更批次单独一个 tag + release，不合并。**

6. **前端展示用的数据一律走公开端点，绝不依赖管理端点。**
   `/api/db` `/api/reseed` `/api/kv-status` `/api/collect` 部署到 Vercel 后一律 403。
   线上真实踩过：落地页与看板侧栏原本读 `/api/db` 填数字，上线后整块显示「—」，
   **且不报错**（静默功能缺失，比崩溃更难发现）。需要对外公开的聚合计数请用
   `GET /api/stats`（不含库路径等环境细节）。

---

## 5. 已验证 vs 未验证

明确区分，避免接手后误信。

| 项 | 状态 | 依据 |
| --- | --- | --- |
| 双语 API 契约（17 项端点） | ✅ 已验证 | `scripts/check_i18n.py` 全部通过 |
| 中英界面切换（下拉框/卡片/表格/公报/自定义分析） | ✅ 已验证 | Chrome 实测，无 console 报错 |
| CLI 双语（`ask` / `report` / `custom`） | ✅ 已验证 | 命令行实测 |
| 本地服务 `/` `/app` 与全部 API | ✅ 已验证 | 交接时 200 |
| README markdownlint | ✅ 已验证 | `markdownlint-cli2` 0 issues |
| 亚太分类口径（移除美国/澳大利亚） | ✅ 已本地验证 | pytest 全绿；`available_dimensions()` 无 United States/Australia |
| 静态资源缓存（内容哈希长缓存 + HTML no-store） | ✅ 已验证 | 页面 URL 带 `?v=<sha256前12位>`；`/style.css` 等返回 `max-age=31536000, immutable`；pytest 覆盖 |
| 安全响应头（nosniff / X-Frame-Options / Referrer-Policy / CSP / Permissions-Policy；HTTPS 下 HSTS） | ✅ 已验证 | curl 实测 + pytest |
| 管理端点鉴权（`/api/db` `/api/reseed` `/api/kv-status` `/api/collect`） | ✅ 已验证 | 本地放行；Vercel 无 token → 403；配 `QU_STAT_ADMIN_TOKEN` 后校验；pytest 三态覆盖 |
| 深色模式（`prefers-color-scheme`） | ✅ 已验证 | Chrome 实测：dashboard 明/暗均亮度 246 / 22，落地页暗色 computed style 断言通过，无 console 报错 |
| 无外部 CDN 依赖（字体走系统字体栈） | ✅ 已验证 | `grep -r fonts.googleapis public/` = 0；JSON-LD 与 og PNG 均本地生成 |
| API 参考页 `/docs`（双语、服务端渲染、零 JS） | ✅ 已验证 | curl `/docs?lang=en` 与 `zh` 双语内容正确、占位符已替换；pytest 校验「路由表 ↔ 文档」双向一致（新增路由漏登记即失败） |
| 图表可访问性（`role=img` + 数据摘要 `<desc>` + 主题色板） | ✅ 已验证 | Chrome 实测：`aria-label="Trend over Years: GDP Growth (2019–2024)"`、`<desc>` 含逐经济体「首年值 → 末年值」、图例 `aria-hidden`、容器 `aria-live=polite` |
| 自定义错误页（404 / 405 / 500，双语） | ✅ 已验证 | `/no-such-page` 返回品牌页（含返回落地页 / 看板 / 文档入口）；`/api/*` 的 404 仍回 JSON |
| `/api/stats` 公开统计端点（生产可用） | ✅ 已验证 | 本地与 `VERCEL` 模拟下均 200，且不含 `url` / `path` / `engine` 等环境细节；pytest 覆盖 |
| hreflang 语言标注（en / zh-CN / x-default，逐页） | ✅ 已验证 | 三页各 3 条 alternate；pytest 校验各页指向自身 URL（不互串） |
| `/privacy` 隐私与数据声明页（双语、零 JS） | ✅ 已验证 | curl 双语内容正确、占位符已替换；落地页页脚 / `/docs` 导航 / 错误页**三处入口**均在；pytest 覆盖 |
| 开源配套文件齐全 | ✅ 已验证 | `LICENSE`(MIT) / `CONTRIBUTING`(中英) / `SECURITY` / `CHANGELOG` / `CITATION.cff` / PR 与 issue 模板；`markdownlint-cli2` 全量 **0 issues** |
| **线上 Vercel 部署** | ❓ **未验证** | 本次环境无法出外网。域名来自 7–8 月部署日志，**可能已变更或项目已删**，请自行探活 |
| **Vercel KV 持久化** | ❓ 未验证 | 依赖 `KV_REST_API_URL` / `KV_REST_API_TOKEN`。✅ v1.5.0 起冷启动按**特征判别**（缺「亚太」聚合维度即判为区级旧快照）自动清 KV 重灌真实数据；若线上分类仍异常，可手动清 KV key `qu_stat_ap:indicators` 或带 `X-Admin-Token` 调 `/api/reseed` |
| **云端 AI 解读** | ❓ 未验证 | 需 `INFINISYNAPSE_API_KEY`；未配时自动降级为仅本地统计（不会报错） |
| **Windows 之外的平台** | ✅ 已配 CI（ubuntu-latest） | `.github/workflows/ci.yml` 在 push/PR 时跑 pytest + 起服务 i18n 冒烟；本地 Windows 亦 113 项单测全绿 |

---

## 6. 已知风险与技术债

按影响排序。

1. ~~**零自动化测试、无 CI。**~~ ✅ **已补质量底线**：`tests/` 下 5 个模块共 **113 项**单测
   （`test_labels` i18n 契约、`test_analyzer` provider 派发与解析、`test_web` 路由冒烟
   「html lang / CSV 导出 BOM 与列 / SEO 三件套 / 静态缓存与安全头 / 资源版本号 / 管理端点鉴权 /
   `/docs` 与路由表一致性 / 错误页 / hreflang」、`test_embed` embed 单遍合并回归、
   `test_stats_core` 纯统计函数边界与公报结构、`conftest` 测试库隔离到临时目录）。
   `.github/workflows/ci.yml` 在 push/PR 时：
   `pytest` → 起本地服务跑 `scripts/check_i18n.py` → 可选 `markdownlint-cli2`（不阻塞）。
   纯函数补齐已完成（`src/stats/core.py` 的 `yoy`/`share`/`rank_items`/`fmt_pct`，
   以及 `report.build_bulletin_data()` 的结构与边界），仍**不追覆盖率**。

2. ~~**版本号未维护。**~~ ✅ **已对齐（2026-09-20）**：`pyproject.toml` version = `1.5.0`，
   tag `v1.0.0`→`v1.5.0` 共六个全部推送双远程，GitHub 已建 5 个 release（v1.1.0–v1.5.0）。
   后续发版维持约定：**一个变更批次一个 tag，不合并**（见 §4 约定 5）。

3. **线上部署状态未知。** 见 §5。`vercel.json` 已由旧版 `routes` 迁到 `rewrites`
   （语义等价，消除 `Due to builds existing in your configuration file...` 警告），
   **但本沙箱出不了外网，未实测部署**——首次部署后请确认路由仍全部转发到 `api/index.py`
   （`/` `/app` `/api/*` `/robots.txt` `/sitemap.xml` `/og-image.png` 均应正常）。
   另可到 Vercel 控制台清理可能残留的旧 `builds` 配置。

4. **`config.yaml` 的 `infinisynapse.enabled: true` 但未配 key。**
   当前行为是"云端分析未启用 → 自动回退本地统计"（有提示，不报错），可用但语义绕。
   （`prefer_language` 已由 `zh_CN` 改为 `en_US`，与产品默认语言一致。）

5. **根目录有残留日志文件**（`server.log` / `server_err.log` / `server_out.log` /
   `.vercel_deploy2.txt` / `.vercel_result.txt`）。均已被 gitignore，不进仓库，
   但会干扰排查（旧日志容易被误当成本次输出）。本次未删除（保留供核对线上域名），
   确认无用后可自行清理：`rm -f server*.log .vercel_deploy*.txt .vercel_result*.txt`。

6. ~~**`.python-version` 未纳入 gitignore。**~~ ✅ 已加入 `.gitignore`（同批还补了
   `venv/` / `.ruff_cache/` / `.mypy_cache/`）。

7. **出海（开源国际化）缺口——这是当前主要方向，但离"能被人用起来"还差入场券：**

   | 优先级 | 缺口 | 说明 |
   | --- | --- | --- |
   | ✅ P0 | **图表（已实现）** | 自绘 SVG 折线图（跨年趋势，多经济体叠加）+ 分经济体排名条形图，零图表库依赖；新增「📈 图表」Tab（`public/app.js` 的 `renderLine` / `renderRank`） |
   | ✅ P0 | **导出 + 分享链接（已实现）** | 后端 `GET /api/export.csv`（复用 `query_indicators` + `labels.localize_indicators`，utf-8-sig + `attachment` 下载头；`year`/`dimension` 缺省 = 全部，`indicator` 导出单指标跨年全序列）；前端指标面板「⬇ 导出 CSV」+ 图表面板「⬇ 导出当前指标」+ 顶栏「🔗 分享」；筛选状态经 `history.replaceState` 同步进地址栏，分享链接打开即还原同一视图（含图表指标） |
   | P1 | **时序只有 6 年** | 2019–2024，做不了趋势与周期分析。世界银行免费可取 1960 起 |
   | ✅ P1 | **单一 LLM provider（已改为可插拔）** | `src/analyzer.py` 现支持两个 provider：`infinisynapse`（默认，比赛要求的 SSE 可审计链路）+ `openai_compat`（任意 OpenAI 兼容 `/chat/completions`：OpenAI / OpenRouter / Groq / DeepSeek / 本地 Ollama·vLLM）。用 `AI_PROVIDER` 选择，密钥走 `OPENAI_API_KEY` 等环境变量；两者 `analyze()` 返回同构 `{task_id, done, result}`，`/api/ask` 与公报无需改动。无 key 时仍降级本地统计 |
   | ✅ P1 | **SEO（已实现）** | `public/robots.txt` / `sitemap.xml`（含 `lastmod`）/ `og-image.png`（1200×630，由 `scripts/make_og_image.py` 纯 Pillow 生成；PNG 以 base64 内嵌进 `src/pages.py`），由 `/robots.txt` `/sitemap.xml` `/og-image.png` 提供（`scripts/embed_pages.py` 的 `SEO_FILES`）；两页补 `og:image`（含 `width`/`height`）+ `twitter:image` + **JSON-LD**（WebSite/WebApplication + Dataset，含 `distribution` 指向 CSV/JSON 接口）；`<html lang>` 由占位符 `__HTML_LANG__` 按 `?lang=` / `Accept-Language` 输出 |
   | ✅ P1 | **API 文档页（已实现）** | `GET /docs` 服务端渲染双语参考（22 个端点分组卡片 + 参数表 + curl 示例 + 通用约定），零 JS 依赖、无外部 CDN；`src/api_docs.py` 的 `ENDPOINTS` 是与路由表互为镜像的唯一事实来源，pytest 双向校验一致性 |
   | ✅ P2 | **隐私与数据声明页（已实现）** | `GET /privacy` 双语、零 JS，固定回答对外三问（收集什么 / 数据从哪来 / AI 是否外发）；落地页页脚、`/docs` 导航、错误页三处入口，sitemap 已收录 |
   | ✅ P2 | **开源配套（已补齐）** | 此前**没有 LICENSE 文件**（README 与本文档都写 MIT，法律上却等于保留全部权利）→ 已补 MIT；另加 `CONTRIBUTING`(中英双版)、`SECURITY`、`CHANGELOG`、`CITATION.cff`、PR/issue 模板 |
   | P2 | 表格无分页；移动端仅 3 个断点 | 合规与协作文件已齐，剩余是交互细节 |

   （数据层 i18n 这条 P0 已于 `f0d63b1` 完成，不再是缺口。）

---

## 7. 数据口径与接口

**数据规模**：`ap_macro.csv` 720 行 / 12 维度（2 聚合 + 10 经济体）/ 2019–2024 / 10 指标；
`nbs_cn.csv` 9 行中国国内明细（仅 2024）。

**口径注意**（已在 README 的 Limitations 说明）：

- 「亚太」是世界银行区域合计：**人口加权**，混合了体量差异极大的经济体 →
  **比增长率，不要比水平**。
- 部分国家统计局明细为年度发布，数据集中只有单一年份 → 无上年行时同比显示 `—`。
- 某区域不存在的序列（如亚太合计的社会消费品零售总额）报"不可用"，**不做估算**。
- 单位取自数据行本身（世界银行`亿美元`/`亿人`/`美元`/`岁`，NBS`亿元`/`万人`/`元`），
  **不要写死单位**——同一指标名在不同来源口径的单位不同。

**API**（23 条路由；`/docs` 把它们按 22 张卡片呈现，同组静态资源已合并）：

| 端点 | 说明 |
| --- | --- |
| `GET /` `/app` `/docs` | 落地页 / 看板 / API 参考（服务端渲染双语，零 JS） |
| `GET /style.css` `/app.js` `/i18n.js` | 前端资源（URL 带内容哈希，1 年 immutable 缓存） |
| `GET /favicon.svg` `/og-image.png` | 图标 / 1200×630 分享卡片 |
| `GET /robots.txt` `/sitemap.xml` | SEO 资源（缓存 1 小时） |
| `GET /api/stats` | **公开**的数据规模统计（记录数 / 知识条目 / 覆盖范围），前端展示层专用 |
| `GET /api/overview` | 首页卡片（含 `dimension_options` / `category_options`） |
| `GET /api/indicators` | 指标宽表（支持 `q` 搜索、`category` / `dimension` 过滤） |
| `GET /api/indicator_keys` | 可绑定指标键（供新增自定义分析） |
| `GET /api/export.csv` | 导出指标宽表为 CSV（按 `lang` 本地化；`year`/`dimension` 缺省 = 全部；`indicator` 导出单指标跨年全序列） |
| `GET /api/ask` | 自然语言查询（`cloud=1` 走云端解读） |
| `GET /api/report` | 统计公报（`format=json` 出结构化数据） |
| `GET/POST /api/custom` | 自定义分析：列表 / 运行 / 新增 |
| `GET/POST/DELETE /api/knowledge` | 知识库 |
| `POST /api/collect` 🔒 | 触发公开数据采集（管理端点） |
| `GET /api/db` 🔒 / `GET /api/kv-status` 🔒 | 库状态 / KV 状态（含环境细节，管理端点） |
| `POST /api/reseed` 🔒 | 重新播种（**会覆盖库内数据，谨慎**；管理端点） |

🔒 = 管理端点：配 `QU_STAT_ADMIN_TOKEN` 后校验 `X-Admin-Token` 头或 `?token=`；
未配置时本地开发放行、Vercel 上一律 403。

**错误响应**：页面路径返回品牌一致的 404 / 405 / 500 双语 HTML（`src/error_pages.py`）；
`/api/*` 路径返回 `{"ok": false, "error": "..."}` JSON。

**语言契约**：`?lang=` → `Accept-Language` 头 → 默认 `en`。详见 README「API language contract」。

---

## 8. 密钥与凭据在哪（本文不记录任何明文）

| 名称 | 用途 | 放置位置 |
| --- | --- | --- |
| `INFINISYNAPSE_API_KEY` | 云端 AI 解读 | 环境变量优先；`config.yaml` 的 `api_key` 仅作本地兜底（**该文件被跟踪，勿填真实 key**） |
| `INFINISYNAPSE_SERVER` | 服务地址覆盖（可选） | 环境变量 |
| `AI_PROVIDER` | 选择 AI provider：`infinisynapse`（默认）/ `openai_compat` | 环境变量（或 config.yaml 的 `ai.provider`） |
| `OPENAI_API_KEY` | `openai_compat` 的密钥 | 环境变量（**勿写进被跟踪的 config.yaml**） |
| `OPENAI_BASE_URL` / `OPENAI_MODEL` | OpenAI 兼容端点地址 / 模型名（接 OpenRouter · Groq · 本地 Ollama 即改这两项） | 环境变量（config 的 `ai.openai_compat.*` 为备选） |
| `KV_REST_API_URL` / `KV_REST_API_TOKEN` | Vercel KV 持久化 | Vercel 项目环境变量 |
| `UPSTASH_REDIS_REST_URL` / `_TOKEN` | 同上（Upstash 直连别名） | 环境变量 |
| `QU_STAT_DB_DIR` | SQLite 目录覆盖 | `api/index.py` 在 Vercel 上设为 `/tmp/data` |
| `QU_STAT_ADMIN_TOKEN` | 管理端点令牌（请求头 `X-Admin-Token` 或 `?token=`）；**不配置时本地放行、Vercel 上一律 403**（安全默认） | 环境变量 |
| `QU_STAT_BASE_URL` | 对外站点基址，写进 canonical / hreflang / `/docs` 示例 | 环境变量（**换自定义域名时必设**，否则索引仍指向 vercel.app） |

**助手的本地记忆**（跨会话用，**不随仓库分发**）：
`.workbuddy/memory/MEMORY.md`（权威长期记忆）+ `YYYY-MM-DD.md`（日常流水）。
该目录已被 `.gitignore` 忽略 → **如果交接的是仓库而非整台工作区，这两份文件不会跟着走**，
需要单独拷贝或把要点并入本文件。

---

## 9. 下一步建议（按优先级）

1. **探活线上并核对 Vercel 项目设置**（见 §5、§6.3），清理 `builds` 残留警告。
   这是**唯一仍然未知**的关键项——本地全部能力已实测，线上只有本沙箱出不去网时才无法验证。
1.5. **Gitee 侧只推了 tag、未建 release**（GitHub 已建 v1.1.0–v1.5.0 五个 release）。
   若需在 Gitee 镜像仓库也建 release，需 Gitee 私有 token，走 Gitee OpenAPI 或网页后台手动建。
2. ~~**发布一次正式 release**~~ **已完成（2026-09-18）**：v1.1.0–v1.3.0 三个 tag 已打齐并推双远程。
   此后维持约定：一个变更批次一个 tag，不合并；发版时同步 `pyproject.toml` 与 CHANGELOG 版本标题。
3. **换自定义域名时必设 `QU_STAT_BASE_URL`**（否则 canonical / hreflang / `/docs` 示例
   仍指向 vercel.app）；线上若需重播种或抓数，配 `QU_STAT_ADMIN_TOKEN` 后用
   `X-Admin-Token` 调管理端点。
4. **时序扩到 1960+**（P1）。改 `fetch_wb_data.py` 的参数范围即可，世界银行免费无鉴权。
   注意：扩容后 `data/ap_macro.csv` 会显著变大 → 内嵌进 `src/seed_data.py` 的体积同步增长，
   必要时改为按需加载而不是全量内嵌。
5. **隐私政策 / 条款页**（对外开源分发前的合规项）；移动端断点可再细化（现仅 3 个）、
   指标总表数据量大后需要分页。

已完成、不再列为待办：测试与 CI、图表、导出与分享链接、SEO 与分享卡片、
服务端 i18n、`/docs` API 参考页、图表可访问性、自定义错误页、hreflang、
静态资源长缓存与安全响应头、管理端点鉴权。

---

## 10. 交接清单

- [ ] 在本地跑通：`web` 起服务 → `/app` 打开 → `scripts/check_i18n.py` 全绿
- [ ] 确认双远程可推送（注意 Gitee 与 GitHub 可能需要**不同代理**，见 §4 与本机记忆）
- [ ] 探活线上 `https://qu-stat-system.vercel.app`，核对 Vercel 项目与 KV 配置
- [ ] 确认 `INFINISYNAPSE_API_KEY` 是否有有效值（没有则云端功能自动降级，属预期）
- [ ] 拷贝 `.workbuddy/memory/`（若不接管整台工作区）
- [ ] 读一遍 `README.md` 与 `README.zh-CN.md`（对外口径的权威表述）
- [ ] 打开 `/docs` 速查全部接口与 curl 示例（比翻 `web.py` 快）
- [ ] 记住约定 1：**改 `public/` 后必须跑 `scripts/embed_pages.py`**
- [ ] 记住约定 2：**改路由后必须同步 `src/api_docs.py` 的 `ENDPOINTS`**
      —— pytest 会做「路由表 ↔ 文档」双向校验，漏改即失败
- [ ] 记住约定 6：**前端展示数据只用公开端点**（管理端点线上 403，用户端静默变成「—」）
