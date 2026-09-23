"""AI 解读结果缓存：同一问题 + 同一份事实数据 -> 直接复用上一次的解读。

为什么值得做
------------
看板上每点一次「AI 解读」都会真的打一次云端。而送入模型的全部事实都来自本地
SQLite——**数据没变、问题没变，解读就不该重算**。实测 InfiniSynapse 一次任务
5-20 秒，重复提问既费 token 又费时；Serverless 冷启动后更会每次全量重来。

正确性边界（这个缓存的生死线）
------------------------------
- 缓存键覆盖 **提示词全文 + 全部事实文件内容 + 语言 + 模型身份**。
  事实文件里带的就是送入模型的那些数字，因此数据一变键就变——绝不会把旧数据的
  解读配给新数据（呼应项目「AI 不得编造数字」的原则）。
- 只缓存**成功**结果。异常由上层捕获、不进缓存；模型没给出文本也不缓存，
  避免把一句「（模型未返回文本结果）」当成有效解读长期复用。
- 可整体关闭：``QU_STAT_AI_CACHE=0``。
- 命中时在返回里加 ``from_cache: True``，调用方原样透出，前端据此打「来自缓存」标。

两级
----
- **L1 进程内** ``OrderedDict``：LRU + TTL，热实例内零成本命中。
- **L2 Upstash Redis**（仅当 ``kv_available()`` 且 ``QU_STAT_AI_CACHE_KV!=0``）：
  跨冷启动、跨实例共享；Redis 不可用或读写失败一律降级为「未命中」，
  绝不影响主链路（与 ``kv_store`` 的既有容错策略一致）。

CLI（``src/cli.py``）不接本模块：一次性进程，退出即失效，没有复用窗口。
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import OrderedDict
from typing import Any, cast

from src import kv_store

#: 总开关；置 "0" 完全关闭（含 L1），用于 A/B 或排障。
_ENV_ENABLED = "QU_STAT_AI_CACHE"
#: 缓存有效期（秒）。云端解读依赖的只是本地数据，默认 1 小时足够覆盖同一会话。
_ENV_TTL = "QU_STAT_AI_CACHE_TTL"
#: L1 最大条数（超出按 LRU 淘汰）。
_ENV_MAX = "QU_STAT_AI_CACHE_MAX"
#: L2（Redis）开关；置 "0" 只用进程内缓存。
_ENV_KV = "QU_STAT_AI_CACHE_KV"

_OFF = {"0", "false", "no", "off"}
_ON = {"1", "true", "yes", "on"}

_lock = threading.Lock()
#: key -> (过期时刻, 结果字典)。OrderedDict 用于实现 LRU。
_l1: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
_stats: dict[str, int] = {
    "hits": 0, "misses": 0, "kv_hits": 0, "kv_errors": 0, "writes": 0,
}


def _flag(name: str, default: bool = True) -> bool:
    """读开关类环境变量：空值走默认，无法识别的值也走默认（绝不因拼写错误而静默关闭）。"""
    raw = (os.environ.get(name) or "").strip().lower()
    if raw in _OFF:
        return False
    if raw in _ON:
        return True
    return default


def _int_env(name: str, default: int) -> int:
    try:
        parsed = int((os.environ.get(name) or "").strip())
    except ValueError:
        return default
    return max(1, parsed)


def enabled() -> bool:
    """缓存是否启用（两级共用的总闸）。"""
    return _flag(_ENV_ENABLED, True)


def ttl_seconds() -> int:
    """缓存有效期（秒）。"""
    return _int_env(_ENV_TTL, 3600)


def max_entries() -> int:
    """L1 容量上限（条）。"""
    return _int_env(_ENV_MAX, 128)


def _kv_enabled() -> bool:
    """L2 是否可用：总闸 + KV 闸 + 环境里真的配了 Redis。"""
    return enabled() and _flag(_ENV_KV, True) and kv_store.kv_available()


def reset_cache() -> None:
    """清空 L1 并复位计数器。生产无调用方，供测试与排障使用。"""
    with _lock:
        _l1.clear()
        for name in _stats:
            _stats[name] = 0


def _model_tag(az: object) -> str:
    """模型身份：换 provider / 换模型 / 换服务地址都必须换键。

    两类 provider 的字段名不同（``model``/``base_url`` vs ``server``），
    这里统一取「类名 + 已知字段」；取不到的字段跳过——只要同一进程内稳定，
    就不会把 A 模型的解读派给 B 模型。
    """
    parts = [type(az).__name__]
    for attr in ("model", "base_url", "server", "prefer_language"):
        value = getattr(az, attr, None)
        if value:
            parts.append(f"{attr}={value}")
    return "|".join(parts)


def _fingerprint(files: list[dict[str, object]] | None) -> str:
    """事实文件的内容指纹。

    键的**唯一防串数据机制**就在这里：prompt 里可能只提到指标名，
    而真正的数字全在 ``files`` 里，所以必须把文件内容一起进指纹。
    """
    if not files:
        return ""
    blocks: list[str] = []
    for item in files:
        name = str(item.get("name") or "")
        content = item.get("content")
        blocks.append(name + "\x00" + ("" if content is None else str(content)))
    return "\n\x01".join(blocks)


def cache_key(prompt: str,
              files: list[dict[str, object]] | None,
              lang: str | None,
              model_tag: str) -> str:
    """计算缓存键。相同问题 + 相同事实 + 相同语言 + 相同模型 -> 同一键。"""
    payload = "\n\x02".join([
        prompt or "", _fingerprint(files), lang or "", model_tag or "",
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _kv_key(key: str) -> str:
    return f"qu_stat_ap:ai:{key}"


def _l1_get(key: str, now: float) -> dict[str, Any] | None:
    with _lock:
        item = _l1.get(key)
        if item is None:
            return None
        expires, payload = item
        if expires <= now:
            _l1.pop(key, None)
            return None
        _l1.move_to_end(key)
        return payload


def _l1_put(key: str, payload: dict[str, Any], now: float) -> None:
    with _lock:
        _l1[key] = (now + ttl_seconds(), payload)
        _l1.move_to_end(key)
        while len(_l1) > max_entries():
            _l1.popitem(last=False)


def _kv_get(key: str) -> dict[str, Any] | None:
    if not _kv_enabled():
        return None
    try:
        raw = kv_store.kv_get_json(_kv_key(key))
    except Exception:  # pragma: no cover - kv_store 自身已容错，这是双保险
        with _lock:
            _stats["kv_errors"] += 1
        return None
    if not isinstance(raw, dict):
        return None
    expires_at = raw.get("_expires_at")
    if isinstance(expires_at, (int, float)) and float(expires_at) <= time.time():
        return None
    result = raw.get("result")
    return cast("dict[str, Any]", result) if isinstance(result, dict) else None


def _kv_put(key: str, payload: dict[str, Any], now: float) -> bool:
    if not _kv_enabled():
        return False
    with _lock:
        _stats["writes"] += 1
    try:
        return kv_store.kv_set_json(
            _kv_key(key), {"_expires_at": now + ttl_seconds(), "result": payload})
    except Exception:  # pragma: no cover - 同上
        with _lock:
            _stats["kv_errors"] += 1
        return False


def _decorate(payload: dict[str, Any]) -> dict[str, Any]:
    """命中时返回**副本**并打标记，绝不污染缓存里那份原始结果。"""
    out = dict(payload)
    out["from_cache"] = True
    return out


def _cacheable(out: dict[str, Any]) -> bool:
    """只有「跑完了且有文本」的结果才值得缓存。"""
    return bool(out.get("done")) and bool(str(out.get("result") or "").strip())


def analyze_cached(az: Any,
                   prompt: str,
                   files: list[dict[str, object]] | None = None,
                   lang: str | None = None
                   ) -> tuple[dict[str, object], bool]:
    """调用云端分析，命中缓存则**不发起网络请求**。

    返回 ``(结果, 是否来自缓存)``。结果结构始终是 ``az.analyze()`` 的原始结构
    （``task_id`` / ``done`` / ``result``）；命中时额外带 ``from_cache: True``，
    未命中时**不加任何字段**，保证对外形状向后兼容。

    ``az`` 异常原样向上抛：由调用方决定怎么降级（本地统计 + 注记），
    与不接缓存时的行为完全一致——失败绝不被缓存吞掉。
    """
    if not enabled():
        return dict(az.analyze(prompt, files=files)), False

    key = cache_key(prompt, files, lang, _model_tag(az))
    now = time.time()

    hit = _l1_get(key, now)
    if hit is None:
        hit = _kv_get(key)
        if hit is not None:
            _l1_put(key, hit, now)
            with _lock:
                _stats["hits"] += 1
                _stats["kv_hits"] += 1
            return _decorate(hit), True
    if hit is not None:
        with _lock:
            _stats["hits"] += 1
        return _decorate(hit), True

    with _lock:
        _stats["misses"] += 1
    out = dict(az.analyze(prompt, files=files))
    if _cacheable(out):
        _l1_put(key, out, now)
        _kv_put(key, out, now)
    return out, False


def cache_stats() -> dict[str, Any]:
    """缓存运行指标，供 ``GET /api/ai-cache`` 观测与测试断言。"""
    with _lock:
        snapshot = dict(_stats)
        l1_size = len(_l1)
    snapshot.update({
        "enabled": enabled(),
        "ttl_seconds": ttl_seconds(),
        "l1_size": l1_size,
        "l1_max": max_entries(),
        "kv": _flag(_ENV_KV, True) and kv_store.kv_available(),
    })
    return snapshot
