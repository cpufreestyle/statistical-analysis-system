"""命令行入口，模仿 agent_infini 的子命令风格。

用法：
  python -m src.cli init                     # 初始化数据库 + 示例数据
  python -m src.cli load <file.csv>          # 导入数据
  python -m src.cli ask "2024年全国GDP"       # 本地自然语言查询
  python -m src.cli ask "..." --cloud        # 走 InfiniSynapse 云端 AI 分析
  python -m src.cli cloud "分析全国工业结构"   # 云端多轮分析(需配置开启)
  python -m src.cli report [--year 2024]     # 生成统计公报
  python -m src.cli export [--year 2024]     # 导出 CSV
  python -m src.cli web                       # 启动 Web 看板
"""
from __future__ import annotations

import argparse
import json
from src import loader
from src.stats import query as nlq
from src.stats import custom as cust
from src import report
from src import knowledge as kb
from src import collect as collector
from src.db import db_info, init_db


def _do_ask(text: str, use_cloud: bool):
    if use_cloud:
        from src.analyzer import get_analyzer, AgentInfiniError
        try:
            az = get_analyzer()
            if az is None:
                print("云端分析未启用（config.yaml 中 infinisynapse.enabled=false），"
                      "改用本地统计：")
                print(json.dumps(nlq.ask(text), ensure_ascii=False, indent=2))
                return
            out = az.analyze(text)
            print(json.dumps(out, ensure_ascii=False, indent=2))
        except AgentInfiniError as e:
            print(f"[云端分析失败] {e}\n已回退到本地统计：")
            print(json.dumps(nlq.ask(text), ensure_ascii=False, indent=2))
        return
    print(json.dumps(nlq.ask(text), ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(prog="qu-stat", description="统计分析系统")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("init", help="初始化数据库并生成示例数据")
    sp_load = sub.add_parser("load", help="导入 CSV/Excel")
    sp_load.add_argument("file")
    sp_ask = sub.add_parser("ask", help="自然语言查询")
    sp_ask.add_argument("text")
    sp_ask.add_argument("--cloud", action="store_true",
                        help="走 InfiniSynapse 云端 AI 分析")
    sp_cloud = sub.add_parser("cloud", help="云端多轮 AI 分析(需配置开启)")
    sp_cloud.add_argument("text")
    sp_report = sub.add_parser("report", help="生成统计公报")
    sp_report.add_argument("--year", type=int, default=2024)
    sp_report.add_argument("--cloud", action="store_true",
                           help="追加 InfiniSynapse 云端 AI 解读")
    sp_export = sub.add_parser("export", help="导出 CSV")
    sp_export.add_argument("--year", type=int, default=2024)
    sp_custom = sub.add_parser("custom", help="自定义分析（list / run <名称>）")
    sp_custom.add_argument("action", nargs="?", default="list",
                           choices=["list", "run"])
    sp_custom.add_argument("name", nargs="?", default=None)
    sp_custom.add_argument("--year", type=int, default=2024)
    sp_web = sub.add_parser("web", help="启动 Web 看板")
    sp_web.add_argument("--host", default="0.0.0.0", help="绑定地址（默认 0.0.0.0 便于云端/容器外部访问）")
    sp_web.add_argument("--port", type=int, default=5000, help="监听端口（默认 5000）")

    # 数据库管理
    sp_db = sub.add_parser("db", help="数据库状态 / 初始化知识库")
    sp_db.add_argument("action", nargs="?", default="info",
                       choices=["info", "seed"])
    # 知识库管理
    sp_kb = sub.add_parser("knowledge",
                           help="知识库（list / search / add / delete）")
    sp_kb.add_argument("action", nargs="?", default="list",
                       choices=["list", "search", "add", "delete"])
    sp_kb.add_argument("--query", default="")
    sp_kb.add_argument("--category", default=None)
    sp_kb.add_argument("--id", type=int, default=None)
    sp_kb.add_argument("--title", default="")
    sp_kb.add_argument("--tags", default="")
    sp_kb.add_argument("--content", default="")
    sp_kb.add_argument("--source", default="")

    # 全网数据采集
    sp_collect = sub.add_parser("collect", help="从公开开放数据源采集全国/全球数据")
    sp_collect.add_argument("--source", default="worldbank",
                            choices=["worldbank", "global"])
    sp_collect.add_argument("--year", type=int, default=None,
                            help="数据年份（默认取 config.yaml 的 collection.year）")
    sp_collect.add_argument("--country", default=None,
                            help="worldbank 源：ISO 国家码，如 CHN/USA")
    sp_collect.add_argument("--indicators", default=None,
                            help="逗号分隔的别名或 code，如 gdp,population,cpi")
    sp_collect.add_argument("--countries", default=None,
                            help="global 源：逗号分隔 ISO 码，如 CHN,USA,JPN")

    args = p.parse_args()

    if args.cmd == "init":
        n = loader.generate_sample_data()
        k = kb.seed_default_knowledge()
        print(f"已初始化，写入 {n} 条示例指标，知识库灌入 {k} 条种子知识。")
    elif args.cmd == "db":
        init_db()
        if args.action == "seed":
            added = kb.seed_default_knowledge()
            print(f"知识库种子：新增 {added} 条"
                  f"（已有时不再重复）。")
        else:
            print(json.dumps(db_info(), ensure_ascii=False, indent=2))
    elif args.cmd == "knowledge":
        init_db()
        if args.action == "list":
            rows = kb.list_knowledge(args.category)
            if not rows:
                print("知识库为空，可执行 `python -m src.cli db seed` 灌入种子。")
            for r in rows:
                src = f"（{r['source']}）" if r["source"] else ""
                print(f"[{r['id']}] {r['category']} · {r['title']}{src}")
        elif args.action == "search":
            rows = kb.search_knowledge(args.query)
            if not rows:
                print(f"未找到与「{args.query}」相关的知识。")
            for r in rows:
                print(f"[{r['id']}] {r['category']} · {r['title']}")
                print(f"    {r['content']}")
        elif args.action == "add":
            if not args.title or not args.content:
                print("add 需提供 --title 与 --content。")
            else:
                kid = kb.add_knowledge(args.title, args.category or "通用",
                                       args.tags, args.content, args.source)
                print(f"已新增知识 [{kid}]：{args.title}")
        elif args.action == "delete":
            if args.id is None:
                print("delete 需提供 --id。")
            else:
                ok = kb.delete_knowledge(args.id)
                print("已删除" if ok else "未找到该 id")
    elif args.cmd == "load":
        n = loader.load_file(args.file)
        print(f"已导入 {n} 条指标。")
    elif args.cmd == "ask":
        _do_ask(args.text, use_cloud=args.cloud)
    elif args.cmd == "cloud":
        _do_ask(args.text, use_cloud=True)
    elif args.cmd == "report":
        print(report.generate_report(args.year, use_cloud=args.cloud))
    elif args.cmd == "export":
        path = f"data/indicators_{args.year}.csv"
        report.export_csv(args.year, path)
        print(f"已导出到 {path}")
    elif args.cmd == "custom":
        if args.action == "list":
            items = cust.load_custom()
            if not items:
                print("暂无自定义分析，可在 custom_analysis.yaml 中新增。")
            for a in items:
                print(f"- {a.get('name')}：{a.get('description', '')}")
        elif args.action == "run" and args.name:
            a = next((x for x in cust.load_custom() if x.get("name") == args.name), None)
            if not a:
                print(f"未找到自定义分析：{args.name}")
            else:
                print(json.dumps(cust.run_custom(a, args.year),
                                 ensure_ascii=False, indent=2))
    elif args.cmd == "web":
        from src.web import app
        # debug=False 避免 Werkzeug 调试工具栏（依赖 getBoundingClientRect）在
        # 嵌入式 WebView / 云端预览环境中报 null 引用；host 默认 0.0.0.0 便于外部访问。
        app.run(host=args.host, port=args.port, debug=False)
    elif args.cmd == "collect":
        init_db()
        inds = args.indicators.split(",") if args.indicators else None
        countries = args.countries.split(",") if args.countries else None
        try:
            if args.source == "global":
                n = collector.collect_global(year=args.year,
                                            indicators=inds, countries=countries)
            else:
                n = collector.collect_worldbank(year=args.year,
                                                country=args.country,
                                                indicators=inds)
            print(f"已从网络采集并写入 {n} 条指标"
                  f"（来源标注见 indicators 表 note 字段）。")
        except collector.CollectError as e:
            print(f"[采集失败] {e}\n请确认本机可经 HTTP(S)_PROXY 联网后重试。")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
