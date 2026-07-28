# 全国统计系统

参考 `agent_infini`（InfiniSynapse CLI）的「数据源管理 + 多轮分析」思路，用 Python **本地化实现**的统计分析系统。覆盖全国口径主要专业，并支持**从公开开放数据源（如世界银行 Open Data）全网采集**宏观指标。

## 重要说明
- 本项目**不自动执行** `irm https://infinisynapse.cn/cli-install/install.ps1 | iex`。
  该命令会下载二进制并修改系统 PATH，需你自行在可信环境下决定是否运行。
- 默认**本地离线运行**，内置全国量级示例数据；可通过 `collect` 子命令/Web 按钮联网采集真实数据。
- 数据采集**仅抓取公开、无需鉴权的开放数据**，尊重速率限制与站点条款，不抓取需登录/付费内容。

## 业务覆盖
综合核算(GDP/增加值)、工业、贸易、服务业、固定资产投资、农业、人口与就业；支持全国口径与全球主要经济体对比。

## 安装与运行（使用项目 .venv）
```powershell
cd "d:/ai sheare/repo/区统计系统"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
python -m src.cli init
python -m src.cli ask "2024年全国GDP"
python -m src.cli report
python -m src.cli web      # 浏览器打开 http://127.0.0.1:5000
```

## 从 Gitee 克隆
```powershell
git clone https://gitee.com/cpufreestyle/qu-stat-system.git
cd qu-stat-system
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
python -m src.cli init      # 生成示例数据并建库
python -m src.cli web       # 打开 http://127.0.0.1:5000
```

## 可选：接入云端 AI 解读
`config.yaml` 的 `infinisynapse` 填入 `server` / `api_key` 并设 `enabled: true` 后，
可用 `ask --cloud`、`cloud`、`report --cloud` 调用 `agent_infini` 做多轮分析
（需联网，走系统 HTTP(S)_PROXY）。云端解读会**自动召回本地知识库**作为上下文，
让 AI 结论紧扣全国统计口径（RAG 轻量版，无需外部向量库）。

## 数据库 & 知识库

系统与 `agent_infini` 的「数据源管理」一致，采用本地 SQLite 统一存储：

- **数据库**：指标宽表 `indicators` 与知识库表 `knowledge` 共用同一 SQLite 文件
  （`config.yaml` 的 `database.url`，默认 `data/qu_stats.db`）。
  查看状态：`python -m src.cli db info`；灌入种子知识：`python -m src.cli db seed`。
- **知识库**：存放指标口径、统计制度方法与政策说明等结构化文档，离线可用。
  支持关键词召回（标题 / 标签 / 正文），作为查询与 AI 解读的上下文。

命令行：
```powershell
python -m src.cli db info                       # 查看数据库路径/大小/各表行数
python -m src.cli db seed                       # 灌入 5 条种子知识（已存在不重复）
python -m src.cli knowledge list                # 列出全部知识
python -m src.cli knowledge search "GDP 口径"    # 关键词搜索
python -m src.cli knowledge add --title "研发支出口径" --content "..." --tags "研发,GDP" --source "统计制度"
python -m src.cli knowledge delete --id 3       # 按 id 删除
```
Web 看板「知识库 & 数据库」区块可浏览 / 搜索 / 在线新增 / 删除知识，
首页 `ask` 结果末尾也会附带「知识库参考」。

## 全网数据采集（公开开放数据源）

把公开、无需鉴权的宏观统计数据抓回本地 `indicators` 表，实现「在线数据 + 本地分析」。

- 默认源 **worldbank**：世界银行 Open Data API，按国家/指标/年份查询（如全国 GDP、人口、人均 GDP、CPI、进出口等），结果带 `来源：世界银行OpenData(...)` 标注。
- **global** 源：一次性抓取多个经济体（CHN/USA/JPN/…），以各国为 `dimension` 便于全球对比。
- 通过系统 HTTP(S)_PROXY 联网；每次请求间隔可在 `config.yaml` 的 `collection.rate_limit_sleep` 调整。

命令行：
```powershell
python -m src.cli collect                                  # 采集全国默认指标（取 config 年份）
python -m src.cli collect --year 2023 --indicators gdp,population,cpi
python -m src.cli collect --source global --indicators gdp,population
python -m src.cli collect --source worldbank --country USA --indicators gdp
```
Web 看板「数据收集（全网开放数据）」区块可选数据源/年份/指标，一键从网络采集，
采集完成后自动刷新看板与指标表。

## 自定义分析（无需改代码）
在 `custom_analysis.yaml` 中声明分析项，用**已有指标**做任意公式计算。每项含：
- `name` 分析名称、`unit` 单位、`description` 说明
- `variables`：变量名 -> `[专业, 指标, 维度(可省略，默认"全国")]`
- `expr`：表达式，可用变量名及 `min/max/abs/round/sum`
- `compare`：是否计算同比(true/false)

引擎在**受限命名空间**内安全求值（仅放行少量数学内置，杜绝任意代码执行）：
```yaml
- name: 工业占GDP比重
  unit: "%"
  variables:
    industry: [工业, 规模以上工业总产值, 全国]
    gdp: [综合, 地区生产总值, 全国]
  expr: "industry / gdp * 100"
  compare: true
```

使用方式：
```powershell
python -m src.cli custom list                 # 列出全部自定义分析
python -m src.cli custom run "工业占GDP比重"     # 运行指定分析
```
Web 看板「自定义分析」区块支持下拉运行，并可在线「新增」分析（自动写入 `custom_analysis.yaml`）。

## 目录结构
```
src/db.py            本地 SQLite（指标宽表 indicators + 知识库表 knowledge + 状态查询）
src/loader.py        CSV/Excel 导入 + 全国量级示例数据
src/knowledge.py     知识库引擎（增/查/删/搜/种子/上下文召回）
src/collect.py       全网数据采集（世界银行开放数据，可插拔源，速率限制 + 来源标注）
src/stats/core.py    同比/占比/排名/汇总
src/stats/indicators.py  各统计专业指标计算
src/stats/query.py   自然语言式查询（本地规则，含自定义分析与知识库路由）
src/stats/custom.py   自定义分析引擎（读取 custom_analysis.yaml）
src/report.py        公报/报表生成（云端解读召回知识库）
src/web.py           Web 看板（含知识库、数据库与数据收集区块）
src/cli.py           命令行入口（含 db / knowledge / custom / collect 子命令）
custom_analysis.yaml  自定义分析配置（用户可自由增删）
```
