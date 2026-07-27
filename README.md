# 区统计系统（宝山区统计局业务）

参考 `agent_infini`（InfiniSynapse CLI）的「数据源管理 + 多轮分析」思路，用 Python **本地化实现**的统计分析系统，覆盖宝山区统计局主要专业口径。

## 重要说明
- 本项目**不自动执行** `irm https://infinisynapse.cn/cli-install/install.ps1 | iex`。
  该命令会下载二进制并修改系统 PATH，需你自行在可信环境下决定是否运行。
- 默认**本地离线运行**，无需云端 API Key。`config.yaml` 中可开启 `infinisynapse` 接入。

## 业务覆盖
综合核算(GDP/增加值)、工业、贸易、服务业、固定资产投资、农业、人口与就业、街镇园区。

## 安装与运行（使用项目 .venv）
```powershell
cd "d:/ai sheare/repo/区统计系统"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
python -m src.cli init
python -m src.cli ask "2024年宝山区GDP"
python -m src.cli report
python -m src.cli web      # 浏览器打开 http://127.0.0.1:5000
```

## 目录结构
```
src/db.py            本地 SQLite 指标宽表（替代 agent_infini 的 db 管理）
src/loader.py        CSV/Excel 导入 + 示例数据
src/stats/core.py    同比/占比/排名/汇总
src/stats/indicators.py  宝山区各专业指标计算
src/stats/query.py   自然语言式查询（本地规则）
src/report.py        公报/报表生成
src/web.py           Web 看板
src/cli.py           命令行入口
```
