# 项目交接 · 亚太统计分析系统

> 交接对象：接手本仓库的开发/维护者
> 交接时间：2026-09-16
> 交接时 HEAD：`f0d63b1`（Gitee 与 GitHub 均已同步）
> 本文件为**新增未提交文件**，尚未纳入版本控制

---

## 0. 一分钟速览

| 项 | 内容 |
| --- | --- |
| 对外名称 | Asia-Pacific Statistical Analysis System |
| 一句话定位 | 用**公开真实数据**做的亚太宏观经济统计与 AI 解读看板 |
| 数据来源 | 世界银行 Open Data · 中国国家统计局 · 海关总署（全部公开、无需鉴权） |
| 技术栈 | Python 3.12 + Flask + SQLAlchemy Core + SQLite；前端原生 HTML/CSS/JS，**零构建** |
| 仓库 | Gitee `cpufreestyle/statistical-analysis-system`（origin）· GitHub 同名（github） |
| 分支 / 版本 | `master`；tag 仅 `v1.0.0`（**落后 HEAD，见 §6**） |
| 线上 | Vercel 项目 `qu-stat-system`，生产别名 `https://qu-stat-system.vercel.app`（**本次未探活，见 §5**） |
| 测试 / CI | **无**（`tests/` 为空目录，无 workflow）——见 §6 |
| 许可证 | MIT |

**唯一护城河**：AI 解读 + 每行数据可溯源到 `note` + 明确禁止编造数字。
对标 Our World in Data 没有 AI 层，而海外用户对 AI 幻觉极敏感——这是对外主卖点。

---

## 1. 当前状态

- 工作区**干净**，无未提交改动（`HANDOFF.md` 本身除外）。
- 最近三批工作（时间倒序）：
  1. `f0d63b1` 数据标识符本地化下沉到服务端，REST API 真正双语
  2. `bb3cdc2` `.gitignore` 忽略助手工作目录
  3. `3895850` 数据源迁移至公开真实数据 + 英文优先双语 + README 中英双版
- 本地服务可跑（交接时 5000 端口在跑，`/` 与 `/app` 均 200）。

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
| `public/` | 前端源码（`index.html` / `app.html` / `app.js` / `i18n.js` / `style.css`） | **改完必须跑内嵌脚本** |
| `data/ap_macro.csv` | 世界银行真实种子：837 行 / 14 维度 / 2019–2024 / 10 指标 | 脚本生成，已提交 |
| `data/nbs_cn.csv` | 中国国内明细：9 行（仅 2024） | 带 BOM，读取处已处理 |
| `data/labels.csv` | **标识符标签包**（`kind,key,slug,en`）：专业 7 / 指标 26 / 维度 14 / 单位 8 | i18n 唯一事实来源，加词条不用改代码 |
| `data/qu_stats.db` | 运行时 SQLite | 已被 gitignore |
| `scripts/fetch_wb_data.py` | 从世界银行抓数 | `--from 2019 --to 2024` |
| `scripts/embed_pages.py` | 内嵌 `public/` → `src/pages.py`、`data/` → `src/seed_data.py` | 见 §4 约定 1 |
| `scripts/check_i18n.py` | 双语 API 契约检查 | 新增端点后建议同步加进 CHECKS |
| `src/web.py` | Flask 应用：页面、REST API、冷启动播种 | 18 条路由，见 §7 |
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

## 4. 五条不可违反的约定

1. **改完 `public/` 任何文件、或重新抓数后，必须跑 `scripts/embed_pages.py` 再重启服务。**
   Serverless 部署包读不到 `public/` 与 `data/`，运行期靠 `src/pages.py` / `src/seed_data.py`
   的内嵌副本。漏跑 → 你看到的是旧前端资源，会浪费大量时间排查"改了没生效"。

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
| **线上 Vercel 部署** | ❓ **未验证** | 本次环境无法出外网。域名来自 7–8 月部署日志，**可能已变更或项目已删**，请自行探活 |
| **Vercel KV 持久化** | ❓ 未验证 | 依赖 `KV_REST_API_URL` / `KV_REST_API_TOKEN` 是否仍配置 |
| **云端 AI 解读** | ❓ 未验证 | 需 `INFINISYNAPSE_API_KEY`；未配时自动降级为仅本地统计（不会报错） |
| **Windows 之外的平台** | ❓ 未验证 | 无 CI，仅在 Windows 上跑过 |

---

## 6. 已知风险与技术债

按影响排序。

1. **零自动化测试、无 CI。** 仓库有 `tests/` 目录但**没有任何被跟踪的测试文件**
   （历史上也从未提交过）。当前质量保障完全依赖 `scripts/check_i18n.py` 与手工验证。
   这是接手后最该补的一环——建议至少给 `labels.py`、`stats/core.py`、
   `report.build_bulletin_data()` 这些纯函数补单测，再挂 GitHub Actions。

2. **版本号未维护。** tag 只有 `v1.0.0`（8 个提交之前），`pyproject.toml` version 是 `0.1.0`。
   发版前先对齐这两处，并确认 release notes 与 `README` / `README.zh-CN.md` 一致。

3. **线上部署状态未知。** 见 §5。另外 `vercel.json` 用的是 `routes` 全量转发到
   `api/index.py`，而部署日志里有 `Due to builds existing in your configuration file,
   the Build and Development Settings defined in your Project Settings will not apply` 警告——
   说明 Vercel 项目设置里可能残留旧的 `builds` 配置，建议到控制台核对并清理。

4. **`config.yaml` 的 `infinisynapse.enabled: true` 但未配 key。**
   当前行为是"云端分析未启用 → 自动回退本地统计"（有提示，不报错），可用但语义绕。
   另 `prefer_language: "zh_CN"` 与产品默认英文不一致，建议改为 `en_US`。

5. **根目录有残留日志文件**（`server.log` / `server_err.log` / `server_out.log` /
   `.vercel_deploy2.txt` / `.vercel_result.txt`）。均已被 gitignore，不进仓库，
   但会干扰排查（旧日志容易被误当成本次输出）。可直接删除。

6. **`.python-version` 未纳入 gitignore。** Vercel 构建时会写这个文件，
   本地跑 `vercel` 部署后会多出一个未跟踪文件。建议加进 `.gitignore`。

7. **出海（开源国际化）缺口——这是当前主要方向，但离"能被人用起来"还差入场券：**

   | 优先级 | 缺口 | 说明 |
   | --- | --- | --- |
   | ✅ P0 | **图表（已实现）** | 自绘 SVG 折线图（跨年趋势，多经济体叠加）+ 分经济体排名条形图，零图表库依赖；新增「📈 图表」Tab（`public/app.js` 的 `renderLine` / `renderRank`） |
   | ✅ P0 | **导出 + 分享链接（已实现）** | 后端 `GET /api/export.csv`（复用 `query_indicators` + `labels.localize_indicators`，utf-8-sig + `attachment` 下载头；`year`/`dimension` 缺省 = 全部，`indicator` 导出单指标跨年全序列）；前端指标面板「⬇ 导出 CSV」+ 图表面板「⬇ 导出当前指标」+ 顶栏「🔗 分享」；筛选状态经 `history.replaceState` 同步进地址栏，分享链接打开即还原同一视图（含图表指标） |
   | P1 | **时序只有 6 年** | 2019–2024，做不了趋势与周期分析。世界银行免费可取 1960 起 |
   | ✅ P1 | **单一 LLM provider（已改为可插拔）** | `src/analyzer.py` 现支持两个 provider：`infinisynapse`（默认，比赛要求的 SSE 可审计链路）+ `openai_compat`（任意 OpenAI 兼容 `/chat/completions`：OpenAI / OpenRouter / Groq / DeepSeek / 本地 Ollama·vLLM）。用 `AI_PROVIDER` 选择，密钥走 `OPENAI_API_KEY` 等环境变量；两者 `analyze()` 返回同构 `{task_id, done, result}`，`/api/ask` 与公报无需改动。无 key 时仍降级本地统计 |
   | ✅ P1 | **SEO（已实现）** | 新增 `public/robots.txt` / `sitemap.xml` / `og-image.svg`，并内嵌进 `src/pages.py` 由 `/robots.txt` `/sitemap.xml` `/og-image.svg` 提供（`scripts/embed_pages.py` 的 `SEO_FILES`）；`index.html` 与 `app.html` 补 `og:image`，`<html lang>` 改为占位符 `__HTML_LANG__`，由 `_html_lang()` 按 `?lang=` / `Accept-Language` 输出——原先写死 `zh-CN` 与英文默认矛盾 |
   | P2 | 表格无分页；移动端仅 3 个断点 | 另缺 API 文档页、隐私政策 / 条款 |

   （数据层 i18n 这条 P0 已于 `f0d63b1` 完成，不再是缺口。）

---

## 7. 数据口径与接口

**数据规模**：`ap_macro.csv` 837 行 / 14 维度（2 聚合 + 12 经济体）/ 2019–2024 / 10 指标；
`nbs_cn.csv` 9 行中国国内明细（仅 2024）。

**口径注意**（已在 README 的 Limitations 说明）：

- 「亚太」是世界银行区域合计：**人口加权**，混合了体量差异极大的经济体 →
  **比增长率，不要比水平**。
- 部分国家统计局明细为年度发布，数据集中只有单一年份 → 无上年行时同比显示 `—`。
- 某区域不存在的序列（如亚太合计的社会消费品零售总额）报"不可用"，**不做估算**。
- 单位取自数据行本身（世界银行`亿美元`/`亿人`/`美元`/`岁`，NBS`亿元`/`万人`/`元`），
  **不要写死单位**——同一指标名在不同来源口径的单位不同。

**API**（18 条路由）：

| 端点 | 说明 |
| --- | --- |
| `GET /` `/app` | 落地页 / 看板 |
| `GET /api/overview` | 首页卡片（含 `dimension_options` / `category_options`） |
| `GET /api/indicators` | 指标宽表（支持 `q` 搜索、`category` / `dimension` 过滤） |
| `GET /api/indicator_keys` | 可绑定指标键（供新增自定义分析） |
| `GET /api/export.csv` | 导出指标宽表为 CSV（按 `lang` 本地化；`year`/`dimension` 缺省 = 全部；`indicator` 导出单指标跨年全序列） |
| `GET /api/ask` | 自然语言查询（`cloud=1` 走云端解读） |
| `GET /api/report` | 统计公报（`format=json` 出结构化数据） |
| `GET/POST /api/custom` | 自定义分析：列表 / 运行 / 新增 |
| `GET/POST/DELETE /api/knowledge` | 知识库 |
| `POST /api/collect` | 触发公开数据采集 |
| `GET /api/db` `/api/kv-status` | 库状态 / KV 状态 |
| `POST /api/reseed` | 重新播种（**会覆盖库内数据，谨慎**） |

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

**助手的本地记忆**（跨会话用，**不随仓库分发**）：
`.workbuddy/memory/MEMORY.md`（权威长期记忆）+ `YYYY-MM-DD.md`（日常流水）。
该目录已被 `.gitignore` 忽略 → **如果交接的是仓库而非整台工作区，这两份文件不会跟着走**，
需要单独拷贝或把要点并入本文件。

---

## 9. 下一步建议（按优先级）

1. **补最小测试集 + CI**（质量底线，见 §6.1）。优先覆盖纯函数，不追覆盖率。
2. **图表**（P0）。项目是零构建栈，引重量级图表库会破坏这一点且内嵌后会撑大
   `src/pages.py` → 建议**自绘轻量 SVG**（折线 + 排名条形）。
3. **导出 + 分享链接**（P0）。`/api/export.csv` 复用 CLI 的 `export` 逻辑 +
   前端下载按钮 + `history.replaceState` 同步筛选状态。
4. **探活线上并核对 Vercel 项目设置**（见 §5、§6.3），清理 `builds` 残留警告。
5. ~~**补 SEO 与分享卡片**（P1）~~ ✅ 已完成：`og:image` / `robots.txt` / `sitemap.xml`
   均已落地，`<html lang>` 随 `?lang=` / `Accept-Language` 走。
   遗留优化：`og-image.svg` 是 SVG，Facebook / X / LinkedIn 对 SVG 的 og:image 支持不稳，
   正式投放前换成 **1200×630 PNG/JPG**（改 `/og-image.svg` 路由与 og 标签 URL 即可）。
6. **时序扩到 1960+**（P1）。改 `fetch_wb_data.py` 的参数范围即可，世界银行免费无鉴权。
7. **发布一次正式 release**，对齐 tag 与 `pyproject.toml` 版本号（见 §6.2）。

---

## 10. 交接清单

- [ ] 在本地跑通：`web` 起服务 → `/app` 打开 → `scripts/check_i18n.py` 全绿
- [ ] 确认双远程可推送（注意 Gitee 与 GitHub 可能需要**不同代理**，见 §4 与本机记忆）
- [ ] 探活线上 `https://qu-stat-system.vercel.app`，核对 Vercel 项目与 KV 配置
- [ ] 确认 `INFINISYNAPSE_API_KEY` 是否有有效值（没有则云端功能自动降级，属预期）
- [ ] 拷贝 `.workbuddy/memory/`（若不接管整台工作区）
- [ ] 读一遍 `README.md` 与 `README.zh-CN.md`（对外口径的权威表述）
- [ ] 记住约定 1：**改 `public/` 后必须跑 `scripts/embed_pages.py`**
