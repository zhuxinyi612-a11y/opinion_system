import json
from collections import Counter
from pathlib import Path

from crawler.config import DATA_DIR


def load_json(path: Path):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    raw_data = load_json(DATA_DIR / "raw_data.json") or []
    interactions = load_json(DATA_DIR / "interactions_data.json") or []
    interaction_stats = load_json(DATA_DIR / "interactions_stats.json") or {}
    manifest = load_json(DATA_DIR / "propagation_graph_manifest.json") or {"graphs": []}

    source_counter = Counter()
    keyword_counter = Counter()
    platform_counter = Counter()

    for item in raw_data:
        source_counter[item.get("source", "unknown")] += 1

    for item in interactions:
        keyword_counter[item.get("keyword", "unknown")] += 1
        platform_counter[item.get("platform", "unknown")] += 1

    report = {
        "raw_data_count": len(raw_data),
        "interaction_count": len(interactions),
        "propagation_graph_count": len(manifest.get("graphs", [])),
        "top_sources": source_counter.most_common(20),
        "top_interaction_keywords": keyword_counter.most_common(20),
        "interaction_platforms": platform_counter.most_common(),
        "interaction_sentiment": interaction_stats.get("by_sentiment", []),
        "files": {
            "raw_data": "data/raw_data.json",
            "interactions": "data/interactions_data.json",
            "interaction_stats": "data/interactions_stats.json",
            "propagation_manifest": "data/propagation_graph_manifest.json",
            "propagation_graphs": "data/propagation_graphs/",
            "default_graph": "data/propagation_graph.json",
        },
    }

    output_path = DATA_DIR / "data_report.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("数据报告生成完成")
    print(f"原始数据：{report['raw_data_count']} 条")
    print(f"互动数据：{report['interaction_count']} 条")
    print(f"传播图：{report['propagation_graph_count']} 个")
    print(f"输出文件：{output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()