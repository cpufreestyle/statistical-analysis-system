"""云端 AI 分析层（可选）：封装 InfiniSynapse CLI (agent_infini)。

设计原则：
- 默认关闭；仅当 config.yaml 中 infinisynapse.enabled=true 且配置了
  server/api_key 时启用。未启用或二进制缺失时，调用方应回退到本地统计。
- 直接复用 agent_infini 二进制，与其本身命令/输出格式完全一致：
    init --api-key --server --prefer-language zh_CN
    task new <query>  -> data 含 task_id
    task ask <taskId> <query>
    task show <taskId>
- 外部请求（InfiniSynapse REST API）会经系统 HTTP(S)_PROXY 环境变量，
  因此在配置了 127.0.0.1:7897 代理的机器上可正常联网。

注意：本模块不会执行任何远程安装脚本，也不会联网下载二进制。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import cast

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


class AgentInfiniError(Exception):
    """agent_infini 调用相关错误。"""


def _load_cfg() -> dict[str, object]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return cast("dict[str, object]", yaml.safe_load(f) or {})


def find_binary(explicit: str | None = None) -> str:
    """定位 agent_infini 可执行文件。"""
    if explicit:
        p = Path(explicit).expanduser()
        if p.exists():
            return str(p)
        raise AgentInfiniError(f"指定的二进制不存在: {explicit}")
    on_path = shutil.which("agent_infini")
    if on_path:
        return on_path
    # 默认安装位置（与 install.ps1 一致）
    home = Path.home()
    cand = home / ".infini" / "bin" / "agent_infini.exe"
    if not cand.exists():
        cand = home / ".infini" / "bin" / "agent_infini"
    if cand.exists():
        return str(cand)
    raise AgentInfiniError(
        "未找到 agent_infini。请先安装 InfiniSynapse CLI 并确保其在 PATH 中。"
    )


class AgentInfiniAnalyzer:
    """对 agent_infini 二进制的薄封装，支持多轮分析。"""

    def __init__(self, api_key: str, server: str | None = None,
                 binary: str | None = None, prefer_language: str = "zh_CN"):
        self.api_key: str = api_key
        self.server: str | None = server
        self.binary: str = find_binary(binary)
        self.prefer_language: str = prefer_language
        self._initialized: bool = False

    # ------------------------------------------------------------------
    def _run(self, *cli_args: str) -> dict[str, object]:
        """执行命令并解析 JSON 输出；失败时抛 AgentInfiniError。"""
        cmd = [self.binary, *cli_args, "--json"]
        # 继承当前环境（包含 HTTP_PROXY/HTTPS_PROXY 代理设置）
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  env=os.environ, timeout=300)
        except subprocess.TimeoutExpired as e:
            raise AgentInfiniError(f"调用超时: {' '.join(cmd)}") from e
        if proc.returncode != 0:
            raise AgentInfiniError(
                f"agent_infini 返回非零({proc.returncode}): {proc.stderr.strip()}"
            )
        try:
            payload = cast("dict[str, object]", json.loads(proc.stdout))
        except json.JSONDecodeError as e:
            raise AgentInfiniError(f"输出非 JSON: {proc.stdout[:200]}") from e
        if not payload.get("success", False):
            raise AgentInfiniError(str(payload.get("error", "未知错误")))
        return cast("dict[str, object]", payload.get("data", {}))

    def init(self) -> dict[str, object]:
        args = ["init", "--api-key", self.api_key,
                "--prefer-language", self.prefer_language]
        if self.server:
            args += ["--server", self.server]
        self._initialized = True
        return self._run(*args)

    def new_task(self, query: str) -> str:
        if not self._initialized:
            self.init()
        data = self._run("task", "new", query)
        task_id = data.get("task_id") or data.get("id") or data.get("taskId")
        if not task_id:
            raise AgentInfiniError(f"未从 task new 响应中获取 task_id: {data}")
        return str(task_id)

    def ask_task(self, task_id: str, query: str) -> dict[str, object]:
        return self._run("task", "ask", task_id, query)

    def show_task(self, task_id: str) -> dict[str, object]:
        return self._run("task", "show", task_id)

    def analyze(self, query: str, followups: list[str] | None = None) -> dict[str, object]:
        """一站式：新建任务 -> (可选追问) -> 返回结果。"""
        task_id = self.new_task(query)
        result = self.show_task(task_id)
        for fq in (followups or []):
            _ = self.ask_task(task_id, fq)
            result = self.show_task(task_id)
        return {"task_id": task_id, "result": result}


def get_analyzer() -> AgentInfiniAnalyzer | None:
    """按 config.yaml 构造分析器；未启用或配置不全时返回 None。"""
    cfg = cast("dict[str, object]", _load_cfg().get("infinisynapse", {}))
    if not cfg.get("enabled"):
        return None
    api_key_obj = cfg.get("api_key")
    if not api_key_obj:
        raise AgentInfiniError("infinisynapse.enabled=true 但未配置 api_key")
    api_key = str(api_key_obj)
    server = cast("str | None", cfg.get("server"))
    binary = cast("str | None", cfg.get("binary_path"))
    prefer = str(cfg.get("prefer_language", "zh_CN"))
    return AgentInfiniAnalyzer(
        api_key=api_key,
        server=server,
        binary=binary,
        prefer_language=prefer,
    )
