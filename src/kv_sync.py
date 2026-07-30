"""KV ↔ SQLite 同步层。

职责：
- restore_from_kv(): 冷启动时从 KV 恢复数据到 SQLite
- sync_indicators_to_kv(): 将 indicators 表全量导出到 KV
- sync_knowledge_to_kv(): 将 knowledge 表全量导出到 KV

设计要点：
- 本模块在 api/index.py 初始化过程中调用，可安全引用 db / knowledge
- 写入钩子在 db.py / knowledge.py 中直接调用 kv_store，不经过本模块，避免循环导入
- 恢复优先级：KV 有数据 → 用 KV；KV 为空 → 保持 _ensure_data() 的示例数据
"""

from __future__ import annotations

from src.kv_store import kv_available, kv_get_json

_INDICATORS_KV_KEY = "qu_stat_ap:indicators"
_KNOWLEDGE_KV_KEY = "qu_stat_ap:knowledge"


def restore_from_kv() -> bool:
    """从 KV 恢复数据到 SQLite。KV 有数据时覆盖示例数据，实现持久化。"""
    if not kv_available():
        return False

    from src.db import INDICATORS, KNOWLEDGE, engine, init_db, upsert_indicators

    init_db()
    any_restored = False

    # 1) 恢复 indicators
    data = kv_get_json(_INDICATORS_KV_KEY)
    if data and isinstance(data, list) and len(data) > 0:
        with engine.begin() as conn:
            conn.execute(INDICATORS.delete())
        upsert_indicators(data)  # type: ignore[arg-type]
        any_restored = True

    # 2) 恢复 knowledge
    data = kv_get_json(_KNOWLEDGE_KV_KEY)
    if data and isinstance(data, list) and len(data) > 0:
        with engine.begin() as conn:
            conn.execute(KNOWLEDGE.delete())
        from src.knowledge import add_knowledge as _add
        for k in data:
            _add(
                title=str(k.get("title", "")),
                category=str(k.get("category", "通用")),
                tags=str(k.get("tags", "")),
                content=str(k.get("content", "")),
                source=str(k.get("source", "")),
            )
        any_restored = True

    return any_restored
