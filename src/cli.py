"""命令行入口，模仿 agent_infini 的子命令风格。

用法：
  python -m src.cli init                     # 初始化数据库 + 示例数据
  python -m src.cli load <file.csv>          # 导入数据
  python -m src.cli ask "2024年宝山区GDP"     # 本地自然语言查询
  python -m src.cli ask "..." --cloud        # 走 InfiniSynapse 云端 AI 分析
  python -m src.cli cloud "分析宝山工业结构"   # 云端多轮分析(需配置开启)
  python -m src.cli report [--year 2024]     # 生成统计公报
  python -m src.cli export [--year 2024]     # 导出 CSV
  python -m src.cli web                       # 启动 Web 看板
"""
from __future__ import annotations

import argparse
import json
from src import loader
from src.stats import query as nlq
from src import report


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
    p = argparse.ArgumentParser(prog="qu-stat", description="宝山区统计系统")
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
    sub.add_parser("web", help="启动 Web 看板")

    args = p.parse_args()

    if args.cmd == "init":
        n = loader.generate_sample_data()
        print(f"已初始化，写入 {n} 条示例指标。")
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
    elif args.cmd == "web":
        from src.web import app
        app.run(host="127.0.0.1", port=5000, debug=True)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
