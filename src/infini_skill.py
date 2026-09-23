"""按 agent_infini 官方 Skill 规范，规范并强化本项目对 InfiniSynapse 的集成。

本模块把 agent_infini Skill 中「推荐工作流」（Step 1–5）固化为可复用代码资产，
使 Web/CLI 与平台原生 Agent 使用同一套约定：

  1. **统一凭证/配置链**（Skill Step 1）
     支持 ``~/.agent_infini/config.txt``（Skill 推荐位置，YAML 的 ``global:`` 段）
     与 ``~/.agent_infini/config.json``，字段：server / api-key / console /
     prefer-language。项目 ``config.yaml`` 与环境变量优先级更高。
  2. **资源预检**（Skill Step 2–3）
     声明任务所需的 db / rag 资源；若本机可调用 ``agent_infini`` 二进制，
     则执行 ``task context`` / ``db ls`` / ``rag ls`` 做真实核验（尽力而为、绝不阻塞）。
  3. **审计链接**（Skill「调用日志可查验」）
     由 ``console`` + ``task_id`` 生成可回溯的调用审计地址。
  4. **多轮会话语义**（Skill Step 4）
     统一 ``task new`` → ``task ask <taskId>`` 的稳定 taskId 语义。

全部为**增量能力**：未配置时静默降级，不改变既有行为、不影响可用性。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import cast

#: 对齐的 Skill 版本标识（便于排障时核对）。
SKILL_NAME = "agent_infini"
SKILL_REFERENCE = "https://app.infinisynapse.cn"


def skill_config_paths() -> list[Path]:
    """Skill 规定的配置查找顺序（见 agent_infini --skill「Credential Chain」）。"""
    home = Path.home()
    return [
        home / ".agent_infini" / "config.txt",
        home / ".agent_infini" / "config.json",
    ]


def load_skill_config() -> dict[str, object]:
    """读取 agent_infini 配置（config.txt 优先，其次 config.json）。

    返回 ``global`` 段的扁平字典；均不存在时返回空字典。
    """
    for p in skill_config_paths():
        if not p.exists():
            continue
        try:
            raw = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if p.suffix == ".json":
            try:
                data = cast("dict[str, object]", json.loads(raw))
            except json.JSONDecodeError:
                continue
        else:
            try:
                import yaml
                data = cast("dict[str, object]", yaml.safe_load(raw) or {})
            except Exception:  # noqa: BLE001 - 解析失败不影响主流程
                continue
        merged = cast("dict[str, object]", data.get("global", data))
        if isinstance(merged, dict) and merged:
            return merged
    return {}


def skill_credentials() -> dict[str, str]:
    """把 Skill 配置归一化为统一键名（api_key/server/console/prefer_language）。"""
    cfg = load_skill_config()
    return {
        "api_key": str(cfg.get("api-key") or cfg.get("api_key") or ""),
        "server": str(cfg.get("server") or ""),
        "console": str(cfg.get("console") or ""),
        "prefer_language": str(cfg.get("prefer-language") or cfg.get("prefer_language") or ""),
    }


def console_task_url(task_id: str, server: str = "", console: str = "",
                     template: str = "") -> str:
    """生成任务审计链接（Skill：调用记录可在服务端审计）。

    ``template`` 可用 ``{task_id}`` / ``{server}`` / ``{console}`` 占位；
    缺省直接返回 ``console``（或 ``server``）基地址——**不臆造路径**，具体路由由
    部署方通过 ``infinisynapse.console_task_url_template`` 指定。
    """
    if not task_id:
        return ""
    if template:
        return (template.replace("{task_id}", task_id)
                .replace("{server}", server).replace("{console}", console))
    return console or server or ""


def resolve_cli_path() -> str | None:
    """定位 agent_infini CLI 可执行文件（环境变量 > PATH）。

    仅在「本机确有 CLI」时才启用资源核验；云端/Serverless 下自然返回 None。
    """
    env = os.environ.get("AGENT_INFINI_CLI")
    if env and Path(env).exists():
        return env
    found = shutil.which("agent_infini")
    return found or None


def run_skill_cli(args: list[str], timeout: int = 15) -> tuple[bool, object]:
    """尽力调用 agent_infini CLI 并解析 JSON 输出；任何异常均安全降级。

    返回 ``(ok, data)``：``ok=True`` 时 ``data`` 为解析后的对象（或原文）。
    """
    cli = resolve_cli_path()
    if not cli:
        return (False, "agent_infini CLI not found (set AGENT_INFINI_CLI or add to PATH)")
    try:
        r = subprocess.run([cli, *args, "--json"], capture_output=True,
                           text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        return (False, f"CLI 调用失败: {e}")
    raw = (r.stdout or "").strip()
    if not raw:
        return (False, (r.stderr or "").strip() or "no output")
    try:
        return (True, json.loads(raw))
    except json.JSONDecodeError:
        return (True, raw)


def preflight(db_ids: list[str] | None = None,
              rag_ids: list[str] | None = None) -> dict[str, object]:
    """资源预检（Skill Step 2–3）：确认任务可访问的 db / rag 是否就绪。

    - 若 CLI 可用：执行 ``task context`` 取真实启用清单；缺失声明的资源时给出提示。
    - 若 CLI 不可用：返回声明的资源与说明（不阻塞分析）。
    """
    declared_db = list(db_ids or [])
    declared_rag = list(rag_ids or [])
    result: dict[str, object] = {
        "declared_db": declared_db,
        "declared_rag": declared_rag,
        "cli": resolve_cli_path(),
        "checked": False,
        "missing_db": [],
        "missing_rag": [],
        "note": "",
    }
    ok, data = run_skill_cli(["task", "context"])
    if not ok:
        result["note"] = ("未检测到 agent_infini CLI，跳过实时资源核验"
                          "（不影响本地统计与云端解读）。")
        return result
    result["checked"] = True
    result["context"] = data
    # 尽力从 context 输出里提取已启用的 db / rag 标识做比对
    try:
        blob = json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        blob = str(data)
    result["missing_db"] = [d for d in declared_db if d and d not in blob]
    result["missing_rag"] = [r for r in declared_rag if r and r not in blob]
    return result


def recommended_workflow() -> list[dict[str, str]]:
    """返回 agent_infini Skill 的推荐工作流（Step 1–5），供文档与看板展示。"""
    return [
        {"step": "1", "action": "init --api-key <key>",
         "desc": "首次配置服务器地址与 API Key（~/.agent_infini/config.txt）"},
        {"step": "2", "action": "db ls / rag ls",
         "desc": "列出可用数据库与 RAG 知识库"},
        {"step": "3", "action": "task context（必要时 db enable / rag enable）",
         "desc": "核验目标资源已对任务启用，再开始分析"},
        {"step": "4", "action": "task new → task ask <taskId>",
         "desc": "创建任务并多轮追问（沿用同一 taskId）"},
        {"step": "5", "action": "task file / preview / download",
         "desc": "取回任务工作区产物（图表、CSV、报告等）"},
    ]


def workflow_markdown() -> str:
    """把推荐工作流渲染为 Markdown 列表（便于写入 README / 看板）。"""
    lines = ["| Step | 命令 | 说明 |", "|---|---|---|"]
    for s in recommended_workflow():
        lines.append(f"| {s['step']} | `{s['action']}` | {s['desc']} |")
    return "\n".join(lines)