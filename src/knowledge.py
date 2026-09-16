"""知识库引擎：在本地 SQLite 中管理结构化统计知识（指标口径 / 制度方法 / 政策说明）。

设计目标：
- 与指标宽表共用同一数据库（src/db.py 的 KNOWLEDGE 表），实现「数据 + 知识」本地一体化。
- 提供增 / 查 / 删 / 搜 / 种子能力；并对外暴露 retrieve_context()，把与查询相关的
  知识条目拼成文本，供云端 AI 解读时作为上下文（RAG 轻量版，无外部向量库依赖）。
- 仅做关键词召回，离线可用；未来可平滑替换为向量检索而不影响调用方。
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, TypedDict

from sqlalchemy import func, select

from src.db import KNOWLEDGE, engine, init_db

# ---------------------------------------------------------------------------
# KV 同步辅助
# ---------------------------------------------------------------------------
_KNOWLEDGE_KV_KEY = "qu_stat_ap:knowledge"


def _sync_knowledge_to_kv() -> None:
    """将 knowledge 表全量导出到 Vercel KV。"""
    from src.kv_store import kv_available, kv_set_json
    if not kv_available():
        return
    rows = list_knowledge()
    kv_set_json(_KNOWLEDGE_KV_KEY, [dict(r) for r in rows])


class KnowledgeRow(TypedDict):
    """knowledge 表的一行。"""
    id: int
    title: str
    category: str
    tags: str
    content: str
    source: str


def _row_to_dict(mp: Mapping[Any, Any]) -> KnowledgeRow:
    return KnowledgeRow(
        id=int(mp["id"]),
        title=str(mp["title"]),
        category=str(mp["category"]),
        tags=str(mp["tags"]),
        content=str(mp["content"]),
        source=str(mp["source"]),
    )


def add_knowledge(title: str, category: str, tags: str, content: str,
                  source: str) -> int:
    """新增一条知识；相同 (title, category) 覆盖更新。返回记录 id。"""
    init_db()
    title = title.strip()
    category = category.strip() or "通用"
    with engine.begin() as conn:
        conn.execute(
            KNOWLEDGE.delete().where(
                (KNOWLEDGE.c.title == title)
                & (KNOWLEDGE.c.category == category)
            )
        )
        result = conn.execute(
            KNOWLEDGE.insert().values(
                title=title, category=category,
                tags=tags, content=content, source=source,
            )
        )
        pk = result.inserted_primary_key
        kid = int(pk[0]) if pk is not None else 0
    _sync_knowledge_to_kv()
    return kid


def get_knowledge(kid: int) -> KnowledgeRow | None:
    init_db()
    stmt = KNOWLEDGE.select().where(KNOWLEDGE.c.id == kid)
    with engine.connect() as conn:
        row = conn.execute(stmt).mappings().first()
    if row is None:
        return None
    return _row_to_dict(row)


def list_knowledge(category: str | None = None) -> list[KnowledgeRow]:
    init_db()
    stmt = KNOWLEDGE.select().order_by(KNOWLEDGE.c.id)
    if category:
        stmt = stmt.where(KNOWLEDGE.c.category == category)
    with engine.connect() as conn:
        return [_row_to_dict(r) for r in conn.execute(stmt).mappings()]


def _extract_grams(text: str) -> list[str]:
    """把查询拆成可匹配的「词元」：英文/数字整词 + 中文二元组。

    中文没有空格，整句直接做 LIKE 必然落空；改为二元组 + 英文整词，
    可在小知识库上稳健召回相关条目。
    """
    text = text.strip()
    grams: list[str] = [t.upper() for t in re.findall(r"[A-Za-z0-9]+", text)]
    cjk = re.sub(r"[A-Za-z0-9\s]+", "", text)
    grams += [cjk[i:i + 2] for i in range(len(cjk) - 1)]
    return [g for g in grams if g]


def search_knowledge(query: str, limit: int = 20,
                     lang: str | None = None) -> list[KnowledgeRow]:
    """关键词召回（中英双语）：在标题 / 标签 / 正文中命中任一词元即算相关，按相关度排序。

    知识库规模小，采用「全量取出 + Python 侧打分」策略，避免 SQL LIKE 对中文失效。
    `lang` 给定时（"zh" / "en"）只返回该语种的条目——英文条目的 tags 里带 `lang:en` 标记。
    """
    grams = _extract_grams(query)
    if not grams:
        return []
    rows = list_knowledge()
    if lang:
        want_en = lang.startswith("en")
        rows = [r for r in rows
                if ("lang:en" in r["tags"].lower()) == want_en]
    scored: list[tuple[int, KnowledgeRow]] = []
    for r in rows:
        hay = f"{r['title']} {r['tags']} {r['content']}".upper()
        score = 0
        for g in grams:
            if g.upper() in hay:
                score += 1
        # 标签 / 标题作为整体关键词被查询包含时加权
        for key in [r["title"], *r["tags"].split(",")]:
            key = key.strip()
            if key and key in query:
                score += 2
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:limit]]


def delete_knowledge(kid: int) -> bool:
    init_db()
    with engine.begin() as conn:
        result = conn.execute(KNOWLEDGE.delete().where(KNOWLEDGE.c.id == kid))
        ok = int(result.rowcount) > 0
    _sync_knowledge_to_kv()
    return ok


def count_knowledge() -> int:
    init_db()
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(KNOWLEDGE)).scalar() or 0)


# 种子知识：贴近公开统计制度口径，便于「数据 + 知识」联动演示。
SEED_KNOWLEDGE: list[KnowledgeRow] = [
    KnowledgeRow(
        id=0, title="地区生产总值(GDP)口径", category="综合",
        tags="GDP,地区生产总值,核算",
        content=(
            "地区生产总值(GDP)指按市场价格计算的一个国家（或地区）所有常住单位"
            "在一定时期内生产活动的最终成果，是国民经济核算的核心指标。亚太“综合”"
            "专业的“地区生产总值”为现价核算值，同比为按不变价计算的增速。可通过 "
            "collect 子命令从世界银行开放数据获取真实年度数据，单位亿元。"
        ),
        source="统计制度方法",
    ),
    KnowledgeRow(
        id=0, title="规模以上工业统计范围", category="工业",
        tags="规上工业,工业总产值,主营业务收入,统计范围",
        content=(
            "“规模以上工业”指年主营业务收入 2000 万元及以上的工业法人单位。"
            "规模以上工业总产值为其报告期内生产的工业产品总价值，单位亿元；"
            "规模以上工业增加值为总产值扣除中间投入后的新增价值。"
        ),
        source="工业统计报表制度",
    ),
    KnowledgeRow(
        id=0, title="社会消费品零售总额定义", category="贸易",
        tags="社零,消费,零售",
        content=(
            "社会消费品零售总额是指企业(单位)通过交易售给个人、社会集团非生产用的"
            "实物商品金额，以及提供餐饮服务所取得的收入总额，是反映消费需求的核心指标，单位亿元。"
        ),
        source="贸易外经统计制度",
    ),
    KnowledgeRow(
        id=0, title="固定资产投资统计口径", category="投资",
        tags="固定资产投资,投资,第二产业,第三产业",
        content=(
            "固定资产投资额以货币形式表现的在一定时期内建造和购置固定资产的工作量"
            "以及与此有关的费用总称。本系统按产业划分为第二产业投资与第三产业投资，"
            "工业投资占比 = 第二产业投资 / 固定资产投资总额 × 100%。"
        ),
        source="投资统计制度",
    ),
    KnowledgeRow(
        id=0, title="常住人口与人均可支配收入", category="人口",
        tags="人口,常住,可支配收入",
        content=(
            "常住人口指实际经常居住在某地区半年及以上的人口。居民人均可支配收入"
            "指居民可用于最终消费和储蓄的总和，即居民可用于自由支配的收入，单位元。"
        ),
        source="人口与就业统计",
    ),
]

# 英文条目：tags 里带 `lang:en` 标记，`search_knowledge(..., lang="en")` 只取这些。
SEED_KNOWLEDGE_EN: list[KnowledgeRow] = [
    KnowledgeRow(
        id=0, title="World Bank Open Data (Asia-Pacific aggregates)",
        category="Sources", tags="lang:en,worldbank,open data,source,caliber",
        content=(
            "Asia-Pacific figures are World Bank Open Data series for the "
            "`East Asia & Pacific` (EAS) aggregate, retrieved from "
            "api.worldbank.org and stored with the World Bank indicator code in "
            "each row's note. Values are yearly, in current US dollars for "
            "monetary series (converted to USD 100 million) and in the source "
            "unit otherwise. Because the aggregate mixes economies of very "
            "different size, always compare growth rates rather than levels."
        ),
        source="World Bank Open Data",
    ),
    KnowledgeRow(
        id=0, title="China NBS and Customs data caliber",
        category="Sources", tags="lang:en,nbs,customs,china,caliber",
        content=(
            "China rows are taken from the National Bureau of Statistics press "
            "releases and the General Administration of Customs: GDP and its "
            "three industry value-added components, total retail sales of "
            "consumer goods, fixed asset investment (excluding rural "
            "households), year-end resident population and per-capita "
            "disposable income. Monetary series are in CNY 100 million. "
            "Preliminary accounting figures may be revised, so treat the "
            "official final release as authoritative."
        ),
        source="National Bureau of Statistics / Customs",
    ),
    KnowledgeRow(
        id=0, title="YoY vs. contribution share",
        category="Methods", tags="lang:en,yoy,share,method,caliber",
        content=(
            "Year-over-year (YoY) is the change against the same period of the "
            "previous year; the system computes it from the previous year's row "
            "of the same indicator and dimension. Contribution share expresses a "
            "component as a percentage of its total (e.g. industry value added / "
            "GDP). YoY answers 'how fast', share answers 'how much of the whole' "
            "— do not read one as the other."
        ),
        source="Statistical methodology",
    ),
    KnowledgeRow(
        id=0, title="Cross-economy comparison caveats",
        category="Methods", tags="lang:en,comparison,ranking,method,caliber",
        content=(
            "Rankings compare economies on the same indicator, year and unit. "
            "Population-weighted aggregates (e.g. the Asia-Pacific total) are "
            "dominated by the largest member economies, and USD series move with "
            "exchange rates as well as real output. Use per-capita or growth "
            "series when the question is about living standards or momentum."
        ),
        source="Statistical methodology",
    ),
]


def seed_default_knowledge() -> int:
    """灌入种子知识（中英各一组）。按标题去重，已存在则跳过 —— 
    因此**升级新增的条目会在下一次启动时自动补齐**。返回新增条数。
    """
    existing = {r["title"] for r in list_knowledge()}
    added = 0
    for k in [*SEED_KNOWLEDGE, *SEED_KNOWLEDGE_EN]:
        if k["title"] in existing:
            continue
        add_knowledge(
            title=k["title"], category=k["category"],
            tags=k["tags"], content=k["content"], source=k["source"],
        )
        added += 1
    return added


def retrieve_context(query: str, limit: int = 5, lang: str | None = None) -> str:
    """把与查询相关的最多 limit 条知识拼为文本，供 AI 解读作为上下文。"""
    rows = search_knowledge(query, limit=limit, lang=lang)
    if not rows:
        return ""
    blocks = []
    for r in rows:
        head = f"【{r['category']}】{r['title']}"
        if r["source"]:
            head += f"（来源：{r['source']}）"
        blocks.append(f"{head}\n{r['content']}")
    return "\n\n".join(blocks)
