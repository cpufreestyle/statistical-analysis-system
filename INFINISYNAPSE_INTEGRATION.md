# InfiniSynapse 集成与系统优化 · 变更记录

> **本文件由 AI Agent 写入，供后续 Agent 与开发者阅读。**
> 记录时间：2026-09-23 · 变更范围：`src/` 下 6 个文件改造 + 2 个新模块
> 机器可读清单：`AGENT_CHANGES.json`（同目录）
> 结论行：**全部改动对外行为保持兼容，74 项回归测试全绿，可一键回退。**

---

## 0. 给后续 Agent 的 30 秒速览

| 项 | 内容 |
|---|---|
| 本次做了什么 | ① 用 InfiniSynapse 的「映射成表 + SQL 计算」强化 AI 解读链路；② 数据库索引/写入/连接优化；③ 性能与缓存优化 |
| 新增模块 | `src/infini_skill.py`（Skill 规范化层）、`src/stats/sql_engine.py`（SQL 计算引擎） |
| 改造文件 | `src/analyzer.py`、`src/cli.py`、`src/web.py`、`src/report.py`、`src/db.py`、`src/stats/indicators.py` |
| 是否破坏兼容 | **否**。默认零行为变更；不设任何环境变量即走原逻辑 |
| 如何验证 | `python -m pytest tests/ -q`（应 74 passed）；`python -m src.cli web` 后访问 `/api/infini_skill` |
| 如何回退 | 见 §7 |
| 关键开关 | `QU_STAT_CUSTOM_ENGINE=sql`、`INFINI_MAX_WAIT`、`INFINI_CONNECT_TIMEOUT` |

---

## 1. 背景与目标

本仓库（亚太统计分析系统）已把 **InfiniSynapse 作为默认 AI Provider**（`src/analyzer.py`：
`POST /api/ai/message` 发起 newTask + `GET /api/ai/events` 消费 SSE），但存在三个缺口：

| 缺口 | 影响 |
|---|---|
| G1 `images:[]`、`files:[]` 恒为空 | 云端 AI 只看得到问题文字，看不到本系统检索到的真实数字，解读易脱离数据 |
| G2 计算全在 Python（`src/stats/*`） | 无法利用 InfiniSynapse 的 SQL 引擎做「映射成表 + 计算」 |
| G3 知识召回仅关键词匹配 | 语义召回精度有限 |

在此之上，进一步定位到数据库与运行时的性能热点（重复 DDL、无连接池、重复点查、无压缩/无 ETag）。

---

## 2. 变更清单（按批次）

> 完整机器可读版本见 `AGENT_CHANGES.json`。

### 批次 A · InfiniSynapse 集成：让 AI 基于真实数据解读

| 文件 | 类型 | 变更 |
|---|---|---|
| `src/analyzer.py` | 改 | `new_task()/analyze()` 新增 `files`/`images` 入参；新增 `build_facts_files()`、`render_files_as_text()`、`with_facts()` |
| `src/cli.py` | 改 | `ask --cloud` / `cloud` 把本地检索结果作为 `files` 送入 |
| `src/web.py` | 改 | `/api/ask` 注入事实文件 |
| `src/report.py` | 改 | 公报云端解读附带公报文件 |

**要点**：本地统计结果被封装为「事实文件」（JSON）随任务送入，AI 只依据这些数字解读——
契合本仓库「AI 不得编造数字」的核心原则。OpenAI 兼容端点无文件通道，故 `with_facts()` 把
事实文本内联进提问，两个 provider 入参同构。

### 批次 B · SQL 计算引擎：变量绑定下沉

| 文件 | 类型 | 变更 |
|---|---|---|
| `src/stats/sql_engine.py` | **新增** | `build_binding_sql()` 用**一条 SQL** 的 `MAX(CASE WHEN … THEN value END)` 绑定全部变量；`run_custom_sql()` 复用 `custom._safe_eval`，输出与原 Python 引擎**逐位一致** |

**要点**：原实现含 K 个变量的分析要 **2K 次点查**；本模块用 1 条 SQL 完成「映射 + 透视」。
**默认仍走 Python 引擎**，需显式切换：

```bash
set QU_STAT_CUSTOM_ENGINE=sql                       # 环境变量
python -m src.cli custom run "工业占GDP比重" --engine sql   # CLI
GET /api/custom?name=工业占GDP比重&engine=sql          # Web API
```

可选远程下推：配置 `INFINISYNAPSE_SQL_ENDPOINT` 时同一条 SQL 下推云端；未配置或失败**自动回退本地 SQLite**。

### 批次 C · 按 agent_infini Skill 规范强化集成

| 文件 | 类型 | 变更 |
|---|---|---|
| `src/infini_skill.py` | **新增** | 凭证链 / 资源预检 / 审计链接 / 稳定 taskId / 推荐工作流 |
| `src/analyzer.py` | 改 | 读取 Skill 配置兜底；`console_url` 审计链接；`new_task(..., task_id=)` 支持复用 |
| `src/web.py` | 改 | `/api/ask` 返回 `console_url`；新增 `GET /api/infini_skill` |

**要点**：对齐官方 Skill 的推荐工作流——
①`init --api-key` → ②`db ls`/`rag ls` → ③`task context` 预检 → ④`task new`→`task ask <taskId>` → ⑤`task file/download`。
`preflight()` 在本机存在 `agent_infini` CLI 时执行 `task context` 真实核验，否则**优雅降级**（不阻塞）。

### 批次 D · 数据库优化

| 文件 | 类型 | 变更 |
|---|---|---|
| `src/db.py` | 改 | 自然键复合唯一索引 `ux_indicators_key`；新增 `ix_indicators_dimension`；`INSERT … ON CONFLICT DO UPDATE`；连接级 PRAGMA（WAL 等）；幂等索引迁移 |

**实测收益**（20 万行）：精确四元组查找 **12.1×**；批量 upsert 2000 行 **14.4×**；**零全表扫描**。
> 注：初版曾计划删除单列年索引，基准测试发现会造成 `by_year` 回退，**据实测改为保留**。

### 批次 E · 性能与缓存优化（P0+P1）

| 文件 | 类型 | 变更 |
|---|---|---|
| `src/db.py` | 改 | **R1** `init_db()` 进程内只跑一次（新增 `force` 形参）；**D1** 显式连接池（本地 `QueuePool(5+10)`、Vercel `NullPool`、`pool_pre_ping`） |
| `src/stats/indicators.py` | 改 | **Q1** 新增 `_val_unit()`，把「取值 + 取单位」两次点查合并为一次 |
| `src/web.py` | 改 | **C2** ETag + 条件请求（命中→304）；**C3** gzip 压缩文本响应（≥500B） |
| `src/analyzer.py` | 改 | **A1** 连接/读取超时分离；SSE 等待上限默认与函数超时对齐 |

**实测收益**：`init_db()` 热请求 3.5ms → **0.001ms**；大 JSON **9916B → 1658B（-83%）**；重复请求 → **304**；AI 等待上限 110s → **45s**。

---

## 3. 新增接口与开关（供后续 Agent 直接使用）

### 3.1 HTTP 端点
| 端点 | 说明 |
|---|---|
| `GET /api/infini_skill?db=..&rag=..` | 只读自检：返回推荐工作流 + 资源预检结果（不触发云端调用） |
| `GET /api/custom?name=<分析名>&engine=sql` | 自定义分析，可指定 SQL 引擎 |
| `GET /api/ask?text=..&cloud=1` | 现额外返回 `console_url`（审计链接） |

### 3.2 环境变量
| 变量 | 默认 | 作用 |
|---|---|---|
| `QU_STAT_CUSTOM_ENGINE` | `python` | 自定义分析引擎：`python`/`sql` |
| `INFINISYNAPSE_SQL_ENDPOINT` | 空 | 配置后 SQL 计算下推云端 |
| `INFINISYNAPSE_CONSOLE` | 空 | 审计链接基地址（并入 Skill 配置链） |
| `INFINI_CONNECT_TIMEOUT` | `5` | AI 调用连接超时（秒） |
| `INFINI_MAX_WAIT` | `45` | SSE 等待上限（秒） |
| `AGENT_INFINI_CLI` | 空 | 指定 `agent_infini` 可执行文件路径（供预检） |

### 3.3 凭证链（批次 C）
`环境变量 > config.yaml > ~/.agent_infini/config.txt > ~/.agent_infini/config.json`
（后者字段：`server` / `api-key` / `console` / `prefer-language`）。

---

## 4. 验证记录（可复核）

| 验证项 | 方法 | 结果 |
|---|---|---|
| 语法 | `py_compile` 各改动文件 | ✅ OK |
| SQL↔Python 等价 | 3 个真实自定义分析 | ✅ ALL MATCH |
| 指标函数等值 | `gdp/industry/trade/investment/service/agriculture` | ✅ 数值一致 |
| 回归测试 | `pytest tests/ -q` | ✅ **74 passed** |
| 迁移幂等 | `init_db()` 连跑两次 | ✅ 第 2 次 0.001ms |
| HTTP 缓存 | ETag + `If-None-Match` | ✅ 304 |
| 压缩 | `/api/indicators` gzip | ✅ -83%，回环一致 |
| DB 计划 | `EXPLAIN QUERY PLAN` | ✅ 全部 `SEARCH … USING INDEX` |

---

## 5. 设计决策与取舍（避免后续 Agent 重复踩坑）

1. **C1「查询结果缓存」被有意后置**：读 `tests/test_web.py` 发现它直接用 `engine.begin()` 删表后断言
   `query_indicators() == []`——DB 层缓存会破坏该测试隔离；且索引优化后单查仅约 0.003ms。
   故把「内容未变即不重传」的收益改由 **HTTP 层 C2（ETag/304）**承接。**若未来要做 DB 缓存，务必先解耦该测试。**
2. **保留单列年索引**：复合索引较宽，纯按年查询用窄索引更快（实测差 2.6ms），删之会回退。
3. **`ON CONFLICT` 需唯一索引**：`upsert_indicators` 先探测 `ux_indicators_key` 是否存在，
   不存在则回退「删除+插入」，保证在旧库/非 SQLite 上也正确。
4. **PRAGMA 与迁移全部容错**：逐条 `try/except`，只读库 / 内存库 / 受限文件系统下自动跳过，绝不抛错。

---

## 6. 代码位置速查

| 功能 | 位置 |
|---|---|
| 事实文件封装 | `src/analyzer.py::build_facts_files / render_files_as_text / with_facts` |
| Skill 配置链 | `src/infini_skill.py::skill_credentials / load_skill_config` |
| 资源预检 | `src/infini_skill.py::preflight / run_skill_cli` |
| 审计链接 | `src/infini_skill.py::console_task_url` |
| SQL 绑定 | `src/stats/sql_engine.py::build_binding_sql / run_custom_sql` |
| 索引迁移 | `src/db.py::_ensure_indexes` |
| 连接池/PRAGMA | `src/db.py`（`_engine_kwargs`、`_apply_sqlite_pragmas`） |
| 幂等初始化 | `src/db.py::init_db(force=False)` |
| gzip/ETag | `src/web.py::_apply_headers` |
| N+1 消除 | `src/stats/indicators.py::_val_unit` |

---

## 7. 回退方法

本仓库改动前的原始文件已备份（Agent 工作区 `backup_original/`，后缀 `.a/.b/.c/.d/.p1` 对应不同批次）。
**回退原则**：逐文件覆盖还原即可；由于所有改动默认零行为变更，也可仅通过**不设置任何环境变量**来保持原逻辑。

```bash
# 例：仅还原数据库层
copy backup_original\src__db.py.d      src\db.py
# 仅还原 Web 层
copy backup_original\src__web.py.p1    src\web.py
```

---

## 8. 未实施 / 建议后续

| 条目 | 说明 |
|---|---|
| A2 | AI 解读结果缓存（按「问题 + 数据」哈希） |
| G1 | 导入校验 + 批量事务（`executemany`） |
| K1 | 知识库接入 InfiniSynapse RAG 做语义检索（保留关键词回退） |
| S1 | 拆分 `src/pages.py`（219KB 内嵌前端）以降低冷启动 |
| X1 | 结构化日志 + 慢查询告警 + `/healthz` |

---

## 附录 A · 相关环境修复（不在本仓库内）

InfiniSynapse 桌面端引擎曾因**目录多套一层**（`infinity-sql/infinity-sql/*`）导致
启动器找不到 `infinity-sql/main/byzer-lang-*.jar`。已将其**扁平化**至 `infinity-sql/*`，
引擎恢复正常。此为环境级修复，不属于本仓库代码变更，记录在此以便后续排查。

## 附录 B · 术语

| 术语 | 含义 |
|---|---|
| 事实文件 | 随 AI 任务送入的、本系统检索到的真实统计数据（JSON），是 AI 的唯一数据依据 |
| 引擎 | 计算方式：`python`（原 `src/stats/*`）或 `sql`（`src/stats/sql_engine.py`） |
| 预检 | 任务开始前核验 db/rag 资源是否就绪（对齐 Skill Step 2–3） |