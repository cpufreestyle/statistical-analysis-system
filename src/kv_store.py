"""Upstash Redis 持久化适配层（替代已下线的 Vercel KV）。

Upstash Redis 通过 Vercel Marketplace 安装后会自动注入环境变量：
  UPSTASH_REDIS_REST_URL   → REST API 端点
  UPSTASH_REDIS_REST_TOKEN → 认证 Token

本地开发可通过 QU_STAT_REDIS_URL / QU_STAT_REDIS_TOKEN 手动配置。

策略：
- 冷启动时：从 Redis 恢复数据到 SQLite
- 写入时：先写 SQLite，再同步到 Redis
- 读取时：直接从 SQLite 查询

存储结构（每个 key 存 JSON 数组）：
  qu_stat_ap:indicators  → [IndicatorRow, ...]
  qu_stat_ap:knowledge   → [KnowledgeRow, ...]
  qu_stat_ap:custom      → [CustomAnalysis, ...]
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

# Vercel Marketplace Upstash 集成 → KV_REST_API_URL / KV_REST_API_TOKEN
# Upstash 官网直接创建        → UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN
# 本地自定义                  → QU_STAT_REDIS_URL / QU_STAT_REDIS_TOKEN
_REDIS_URL = (
    os.environ.get("KV_REST_API_URL")
    or os.environ.get("UPSTASH_REDIS_REST_URL")
    or os.environ.get("QU_STAT_REDIS_URL")
    or ""
)
_REDIS_TOKEN = (
    os.environ.get("KV_REST_API_TOKEN")
    or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    or os.environ.get("QU_STAT_REDIS_TOKEN")
    or ""
)

_KV_AVAILABLE = bool(_REDIS_URL and _REDIS_TOKEN)


def kv_available() -> bool:
    """当前环境 Redis 是否可用。"""
    return _KV_AVAILABLE


def _request(method: str, path: str, data: str | None = None) -> Any:
    """发送 Upstash Redis REST 请求。"""
    url = f"{_REDIS_URL.rstrip('/')}{path}"
    headers = {"Authorization": f"Bearer {_REDIS_TOKEN}"}
    resp = requests.request(
        method, url, headers=headers,
        data=data, timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("result")


def kv_get_json(key: str) -> Any:
    """从 Redis 读取并解析 JSON。"""
    if not kv_available():
        return None
    try:
        raw = _request("GET", f"/get/{key}")
        if raw is None:
            return None
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None


def kv_set_json(key: str, value: Any) -> bool:
    """将值序列化为 JSON 写入 Redis。"""
    if not kv_available():
        return False
    try:
        payload = json.dumps(value, ensure_ascii=False, default=str)
        _request("POST", f"/set/{key}", data=payload)
        return True
    except Exception:
        return False


def kv_delete(key: str) -> bool:
    """删除 Redis 中的键。"""
    if not kv_available():
        return False
    try:
        result = _request("POST", f"/del/{key}")
        return bool(result)
    except Exception:
        return False


def kv_keys(prefix: str = "") -> list[str]:
    """列出匹配前缀的所有键。"""
    if not kv_available():
        return []
    pattern = f"{prefix}*" if prefix else "*"
    try:
        result = _request("GET", f"/keys/{pattern}")
        return result if isinstance(result, list) else []
    except Exception:
        return []
