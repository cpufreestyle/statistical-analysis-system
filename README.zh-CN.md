# 亚太统计分析系统

面向亚太地区的开放经济统计工作台：**每一个数字都来自官方公开数据**，AI 只被允许解读这些数字——绝不允许凭空生成。

- **在线看板**：<https://qu-stat-system.vercel.app/app>
- **API 文档**：<https://qu-stat-system.vercel.app/docs>（双语、服务端渲染，22 张端点卡片含参数与 `curl` 示例）
- **数据来源**：世界银行 Open Data · 国家统计局（NBS）· 海关总署
- **AI 能力**：可插拔 provider —— InfiniSynapse Server API（`/api/ai/message` + `/api/ai/events` SSE，默认）**或**任意 OpenAI 兼容 `/chat/completions` 端点（OpenAI / OpenRouter / Groq / DeepSeek / 本地 Ollama · vLLM），Bearer Token 鉴权
- **English docs**: [README.md](README.md)

---

## 与常见「AI + 数据」演示的差别

大多数演示让模型去猜，本项目的设计方向恰好相反：

| 原则 | 落地方式 |
| --- | --- |
| 只用真实公开数据 | 种子数据集由 `scripts/fetch_wb_data.py` 从世界银行 Open Data 抓取，应用中不含任何合成或虚构数值 |
| 每个数字都可溯源 | 每行数据在其 `note` 字段记录来源（如 `World Bank Open Data (NY.GDP.MKTP.CD, EAS)`），看板在每张 KPI 卡片下都展示出来 |
| AI 无法编造数字 | 本地检索到的统计结果作为「唯一允许的事实」注入提示词（明确要求「不得编造未给出的数字」） |
| 不做跨口径运算 | 指标函数先锁定单一维度，再仅在该维度内取数——这修掉了一个真实 bug：同比曾混用两个维度，算出毫无意义的 `+326%` |
| 双语单一事实来源 | 标识符层由 `data/labels.csv` 在**服务端**本地化，因此 REST API 也是双语的，而不只是看板；`public/i18n.js` 现在只承载静态 UI 文案 |

## 功能界面

五个工作台页签：

1. **AI 查询** —— 中英文提问（"2024 GDP"、"社会消费品零售总额"、"日本人口"）。引擎解析
   维度 / 指标 / 年份，返回真实数值，并可选交给云端 AI 做解读。
2. **指标总表** —— 全部已存序列的可搜索表格，可按维度与专业筛选，一键带入自定义分析，
   也可直接导出 CSV。
3. **自定义分析** —— 任意绑定 专业 / 指标 / 维度 变量，使用 `占比` / `差值` / `倍数` / `合计`
   预设，并计算同比。表达式在受限命名空间内求值（杜绝任意代码执行）。
4. **统计公报** —— 用真实数据生成所选年份与维度的统计公报，可附加 AI 解读段落。
5. **图表** —— 自绘 SVG（零图表库依赖）：多经济体跨年趋势折线图 + 分经济体排名条形图；
   两者都带 `role="img"` 与一份数据文字摘要，供屏幕阅读器使用。可一键导出当前指标 CSV。

接口本身在应用内 `/docs` 有完整文档（双语、服务端渲染、不依赖 JavaScript）。
跨经济体排名会把 10 个经济体按工业增加值排序（排除 2 个聚合维度，取前 10 展示）。

## 数据来源与口径

| 维度 | 来源 | 说明 |
| --- | --- | --- |
| 亚太（`EAS`） | 世界银行 Open Data | 东亚与太平洋地区，全部收入水平 |
| 亚太发展中（`EAP`） | 世界银行 Open Data | 东亚与太平洋地区，不含高收入经济体 |
| 中国、日本、韩国、印度、印度尼西亚、泰国、越南、马来西亚、菲律宾、新加坡 | 世界银行 Open Data | 每个经济体一个维度，便于横向对比（共 10 个经济体） |
| 中国国内明细 | 国家统计局 / 海关总署（2024） | 地区生产总值与工业增加值、社会消费品零售总额、固定资产投资、货物贸易、常住人口、居民人均可支配收入 |

每个经济体覆盖的序列（世界银行代码）：
`NY.GDP.MKTP.CD`、`NY.GDP.MKTP.KD.ZG`、`NY.GDP.PCAP.CD`、`FP.CPI.TOTL.ZG`、
`NV.IND.TOTL.CD`、`NE.EXP.GNFS.CD`、`NE.IMP.GNFS.CD`、`SP.POP.TOTL`、`SP.DYN.LE00.IN`、
`SL.UEM.TOTL.ZS` —— 共 2019–2024 六年。

**单位。** 世界银行货币类总量换算为 `亿美元`，人口换算为 `亿人`；人均类保留 `美元`，
预期寿命为 `岁`，比率类为 `%`。国家统计局序列保持其发布单位（`亿元`、`万人`、`元`）。
单位始终与数值一同展示，绝不静默换算。

**数据声明。** 仅使用公开数据，不包含任何内部、涉密或未公开数据。初步核算数后续可能修订，
如与官方最终发布数存在差异，以官方发布为准。

## 快速开始

```bash
git clone https://github.com/cpufreestyle/statistical-analysis-system.git
cd statistical-analysis-system
python -m venv .venv
.venv/Scripts/Activate.ps1          # Windows；macOS/Linux 用 source .venv/bin/activate
pip install -e .
python -m src.cli web --port 5000   # 打开 http://127.0.0.1:5000
```

首次启动会把内置种子文件里的真实公开数据集载入 SQLite（`data/qu_stats.db`），
因此看板可完全离线运行。

### 从数据源刷新数据集

```bash
.venv/Scripts/python.exe scripts/fetch_wb_data.py --from 2019 --to 2024
.venv/Scripts/python.exe scripts/embed_pages.py   # 内嵌前端资源 + 种子 CSV，供 Serverless 使用
```

## 命令行

```bash
python -m src.cli ask "2024 GDP"                    # 本地查询，默认英文输出
python -m src.cli ask "2024 年 GDP" --lang zh        # 同一查询，中文标识符
python -m src.cli ask "工业增加值" --cloud           # 追加 InfiniSynapse 云端解读
python -m src.cli report --year 2024                # 统计公报（文本）
python -m src.cli report --year 2024 --dimension 中国 --lang zh
python -m src.cli report --year 2024 --cloud        # 公报 + AI 解读
python -m src.cli custom list --lang en             # 列出已声明的自定义分析
python -m src.cli custom run "Trade Openness"       # 英文名同样可命中
python -m src.cli collect --country EAS --indicators gdp,population
python -m src.cli collect --source global --indicators gdp --countries CHN,USA,JPN
python -m src.cli knowledge search --query "GDP 口径"
python -m src.cli db info
```

`--lang`（默认 `en`）控制数据标识符与知识库召回的语言；凡是需要填写维度 / 专业的地方，
中英文名与 slug 都接受。

## 配置

`config.yaml` 保存维度默认值、数据库 URL 与采集器设置。

InfiniSynapse API Key 优先从环境变量读取：

```bash
export INFINISYNAPSE_API_KEY="sk-..."     # 推荐，尤其在 Vercel 上
export INFINISYNAPSE_SERVER="https://app.infinisynapse.cn"   # 可选覆盖
```

`config.yaml` 已被 git 跟踪，**切勿把真实 key 提交进去**——密钥放进环境变量，
让 `infinisynapse.api_key` 保持注释状态。

### 切换 AI provider

用 `AI_PROVIDER` 选择后端：`infinisynapse`（默认）或 `openai_compat`：

```bash
# 任意 OpenAI 兼容端点：OpenAI / OpenRouter / Groq / DeepSeek / 本地 Ollama · vLLM
export AI_PROVIDER="openai_compat"
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"   # 接本地 Ollama 则填 http://127.0.0.1:11434/v1
export OPENAI_MODEL="gpt-4o-mini"
```

两个 provider 返回相同的 `{task_id, done, result}` 结构，因此 `/api/ask?cloud=1` 与统计公报
无需改动即可继续工作。未配置密钥时看板自动回退本地统计并给出说明，**不会报错**。

前端会把当前语言作为 `lang` 参数发出，后端转成 API 的 `x-lang` 头
（`en_US` / `zh_CN`），因此 AI 会以用户正在阅读的语言作答。

## API 语言契约

指标行以**中文规范键**入库（`category` / `indicator` 等），这样数据文件可读、
且与官方统计口径逐字对齐。但直接把中文键交给非中文消费方，接口里就会冒出
`综合` / `GDP增长率` / `亿美元`。因此本地化只在**一处**发生：`data/labels.csv` + `src/labels.py`。

所有含数据的响应，每个标识符都给三层：

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `category` / `indicator` / `dimension` / `unit` | 请求语言下的展示值 | `National Accounts` / `GDP Growth` |
| `*_key` | 中文规范键——跨语言稳定，适合做连接键 | `综合` / `GDP增长率` |
| `*_slug` | 供程序消费的稳定 ASCII 标识符 | `national_accounts` / `gdp_growth` |

语言解析顺序：`?lang=` → `Accept-Language` 头 → `en`。

```bash
curl -s "http://127.0.0.1:5000/api/indicators?year=2024&dimension=China&lang=en"
curl -s "http://127.0.0.1:5000/api/report?format=json&year=2024&dimension=%E4%BA%9A%E5%A4%AA&lang=zh"
curl -s "http://127.0.0.1:5000/api/stats"        # 公开的数据规模计数
curl -s "http://127.0.0.1:5000/docs?lang=zh"     # 完整接口文档
```

管理端点（`/api/db`、`/api/reseed`、`/api/kv-status`、`/api/collect`）会暴露环境细节或改动
数据，因此在配置了 `QU_STAT_ADMIN_TOKEN` 时需带 `X-Admin-Token`（或 `?token=`）；
未配置时线上**一律返回 403**。访客页面所需的一切都走公开端点——`/api/stats` 正是为此存在，
避免看板依赖管理路由。

入参接受全部三层，因此 `?dimension=China`、`?dimension=china`、`?dimension=中国` 三者等价。
未登记的词条原样返回——既不猜测翻译，也不抛异常——因此新增指标不会打断既有调用。

对着运行中的服务跑契约检查：

```bash
python scripts/check_i18n.py
```

它会用两种语言遍历全部数据端点：英文模式下任何展示字段残留中文即判失败，
中文模式下丢失中文同样判失败。

## 架构

```text
public/                   前端源码（index.html, app.html, app.js, i18n.js, style.css）
data/ap_macro.csv         世界银行 Open Data 真实种子（脚本生成，已提交）
data/nbs_cn.csv           国家统计局 / 海关总署中国国内明细真实种子
data/labels.csv           标识符标签包：kind,key,slug,en（i18n 的唯一事实来源）
scripts/fetch_wb_data.py  抓取世界银行数据集
scripts/embed_pages.py    将 public/ 内嵌进 src/pages.py、data/ 内嵌进 src/seed_data.py
scripts/check_i18n.py     契约检查：英文接口不得残留中文
src/web.py                Flask 应用：页面、REST API、错误页、冷启动播种
src/cli.py                命令行入口（ask / report / collect / custom / knowledge / db / web）
src/api_docs.py           /docs 接口文档（服务端渲染、双语；端点清单是唯一事实来源）
src/error_pages.py        品牌一致的 404 / 405 / 500 页（双语；/api/* 仍回 JSON）
src/loader.py             种子载入 + 用户 CSV/Excel 导入
src/collect.py            采集流水线（可插拔数据源、限速）
src/db.py                 基于 SQLAlchemy Core 的 SQLite（指标宽表 + 知识库表）
src/labels.py             标识符本地化：label / slug / key_of / localize_payload
src/stats/indicators.py   各统计专业指标函数（维度锚定）
src/stats/core.py         基础算子：同比 / 占比 / 排名 / 汇总
src/stats/query.py        双语自然语言查询引擎（本地规则）
src/stats/custom.py       基于 custom_analysis.yaml 的自定义分析引擎
src/knowledge.py          双语知识库 + 关键词召回（轻量 RAG）
src/report.py             公报构建器（结构化数据 + 文本渲染）
src/analyzer.py           可插拔 AI provider：InfiniSynapse（SSE）+ OpenAI 兼容端点
src/kv_store.py           可选的 Redis 兼容 KV 客户端（Upstash / Vercel KV）
src/kv_sync.py            通过该 KV 存储持久化与恢复 SQLite 快照
src/pages.py              生成物：为 Serverless 内嵌的前端文件
src/seed_data.py          生成物：为 Serverless 内嵌的种子 CSV
api/index.py              Vercel Serverless 入口
```

### 为什么要把资源内嵌

Vercel Serverless 函数无法从部署包中读取 `public/` 或 `data/`，因此
`scripts/embed_pages.py` 会把前端文件内联进 `src/pages.py`、把种子 CSV 内联进
`src/seed_data.py`。**改动 `public/` 下任何文件，或重新抓取数据集之后，
必须重新运行该脚本并重启服务**——否则你看到的仍是旧资源。

## 部署到 Vercel

1. 推送到生产分支，Vercel 项目（`qu-stat-system`）会自动重新部署。
2. 在项目环境变量中设置 `INFINISYNAPSE_API_KEY`。
3. `vercel.json` 把所有请求路由到 `api/index.py`；SQLite 数据库落在 `/tmp`，
   冷启动时重建，若存在 `KV_REST_API_URL` / `KV_REST_API_TOKEN` 变量则从
   Redis 兼容的 KV 存储恢复。
4. 可选：用 `QU_STAT_BASE_URL` 指定自定义域名（影响 `canonical`、`hreflang` 与 `/docs`
   示例）；若需要在线上调用管理端点（重播种 / 抓数），再配置 `QU_STAT_ADMIN_TOKEN`。

## Windows / 编码坑

这些坑实实在在踩过，所以记录下来：

- Windows 控制台是 GBK：诊断脚本里直接打印中文可能抛 `UnicodeEncodeError`。
  改为把结果写入 UTF-8 文件再读回来，而不是 print。
- 通过 PowerShell 向 GitHub API 发送中文载荷会被破坏成 `?`
  （命令被写入临时 `.ps1` 并按 ANSI 解析）。改用 Python 脚本配合
  `json.dumps(..., ensure_ascii=False).encode("utf-8")`，并通过读取响应文件校验。
- `Get-Content` 会把 UTF-8 中文显示为乱码——那只是显示问题，文件本身没问题。

## 已知限制

- 亚太聚合值为世界银行区域合计：按人口加权，混合了体量差异极大的经济体，
  因此请比较增速而非绝对水平。
- 部分国家统计局明细序列仅按年发布，在数据集中只存在单一年份；
  无上年同口径行时，同比显示为 `—`。
- 某维度不存在的序列（例如亚太聚合口径下的社会消费品零售总额）
  一律报为「不可用」，而不是估算。

## 许可

MIT
