"""出海 i18n 冒烟校验：逐个端点检查英文输出是否残留中文标识符。

只检查「展示字段」——`*_key`（中文规范键）与按设计保留规范键的字段（dimensions /
categories）不计入泄漏。中文界面则反过来检查是否被错误英文化。
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:5000"
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
CJK = re.compile(r"[\u4e00-\u9fff]")

#: 按设计保留中文规范键的字段，不算泄漏
CANONICAL = {
    "category_key", "indicator_key", "dimension_key", "unit_key", "note_key",
    "label_key", "dimensions", "categories", "dimension_key",
}


def get(path: str, **params) -> object:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{BASE}{path}" + (f"?{query}" if query else "")
    return json.loads(_opener.open(url).read().decode("utf-8"))


def leaks(node: object, path: str = "") -> list[str]:
    """收集展示字段里残留的中文片段。"""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in CANONICAL or key.endswith(("_key", "_slug")):
                continue
            # *_options[].key 是规范键（与 dimensions / categories 同类），按设计保留中文
            if key == "key" and "_options" in path:
                continue
            # 自定义分析的「名称 / 说明」是用户配置内容，不机器翻译，允许中文
            if "/api/custom" in path and key in ("name", "description", "name_key"):
                continue
            found += leaks(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found += leaks(item, f"{path}[{i}]")
    elif isinstance(node, str) and CJK.search(node):
        # 知识库正文是人工撰写内容，允许中文
        if "kb_reference" in path or "knowledge" in path:
            return []
        found.append(f"{path} = {node[:70]}")
    return found


CHECKS: list[tuple[str, str, dict]] = [
    ("/api/stats", "数据规模（公开）", {}),
    ("/api/overview", "概览卡片", {"year": 2024, "dimension": "亚太"}),
    ("/api/overview", "概览卡片", {"year": 2024, "dimension": "中国"}),
    ("/api/indicators", "指标宽表", {"year": 2024, "dimension": "日本", "limit": None}),
    ("/api/indicators", "指标搜索", {"q": "retail"}),
    ("/api/indicators", "指标搜索(中)", {"q": "社会消费品"}),
    ("/api/indicator_keys", "可绑定指标键", {}),
    ("/api/report", "统计公报", {"format": "json", "year": 2024, "dimension": "亚太"}),
    ("/api/report", "统计公报", {"format": "json", "year": 2024, "dimension": "中国"}),
    ("/api/ask", "自然语言查询", {"text": "2024 GDP", "dimension": "亚太"}),
    ("/api/ask", "自然语言查询", {"text": "GDP growth", "dimension": "亚太"}),
    ("/api/ask", "自然语言查询", {"text": "工业增加值", "dimension": "中国"}),
    ("/api/ask", "自然语言查询", {"text": "各国人口", "dimension": "亚太"}),
    ("/api/ask", "自然语言查询", {"text": "贸易", "dimension": "中国"}),
    ("/api/ask", "自然语言查询", {"text": "投资", "dimension": "中国"}),
    ("/api/ask", "自然语言查询", {"text": "农业", "dimension": "中国"}),
    ("/api/ask", "自然语言查询", {"text": "服务业", "dimension": "中国"}),
    # 自定义分析：带 ?name= 跑单个分析；预置项的 name_en / description_en 已补齐
    ("/api/custom", "自定义分析运行", {"name": "Trade Openness", "year": 2024}),
]


def main() -> int:
    failures = 0
    for endpoint, title, params in CHECKS:
        try:
            data = get(endpoint, lang="en", **params)
        except Exception as exc:  # 端点异常也要报出来
            print(f"[ERR ] {endpoint} {params} -> {exc}")
            failures += 1
            continue
        bad = leaks(data, endpoint)
        tag = "PASS" if not bad else "FAIL"
        print(f"[{tag}] {endpoint:22s} {title:12s} {params}")
        for item in bad[:8]:
            print(f"        残留中文 {item}")
        if bad:
            failures += 1

    # 反向检查：中文界面不应被英文化
    print()
    zh = get("/api/indicators", lang="zh", year=2024, dimension="日本")
    if zh and not CJK.search(json.dumps(zh[0], ensure_ascii=False)):
        print("[FAIL] /api/indicators lang=zh 丢失中文")
        failures += 1
    else:
        print("[PASS] /api/indicators lang=zh 保持中文规范键")
    zh_ov = get("/api/overview", lang="zh", year=2024, dimension="中国")
    if zh_ov["dimension"] != "中国" or CJK.search(zh_ov["cards"][0]["label"]) is None:
        print("[FAIL] /api/overview lang=zh 未返回中文")
        failures += 1
    else:
        print("[PASS] /api/overview lang=zh 返回中文标签")

    # 英文标签 / slug 作为入参应等价于规范键
    print()
    a = get("/api/overview", lang="en", year=2024, dimension="China")
    b = get("/api/overview", lang="en", year=2024, dimension="中国")
    c = get("/api/overview", lang="en", year=2024, dimension="china")
    ok = a["dimension_key"] == b["dimension_key"] == c["dimension_key"] == "中国"
    print(f"[{'PASS' if ok else 'FAIL'}] 入参 China / china / 中国 等价 -> {a['dimension_key']}")
    failures += 0 if ok else 1

    print()
    print(f"结果：{'全部通过' if not failures else f'{failures} 项未通过'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
