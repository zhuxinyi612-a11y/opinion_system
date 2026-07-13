"""
批量生成传播图：
从 data/raw_data.json 中按关键词抽取事件数据，
按时间顺序构造“推断传播链”，批量输出多个 propagation_graph_xxx.json。

适合后端“传播溯源 / 传播路径 / 舆情扩散图”功能演示。
"""

import argparse
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from crawler.config import DATA_DIR
from crawler.propagation_crawler import add_node, add_edge, parse_time_for_sort


DEFAULT_KEYWORDS = [
    # 公共安全
    "食品安全",
    "消防",
    "火灾",
    "爆炸",
    "交通事故",
    "安全事故",
    "生产安全",
    "燃气泄漏",
    "电动车火灾",

    # 教育校园
    "高校",
    "学校",
    "学生",
    "校园安全",
    "校园欺凌",
    "考试",
    "考研",
    "就业指导",
    "师德师风",

    # 医疗民生
    "医疗",
    "医院",
    "医保",
    "药品安全",
    "养老",
    "托育",
    "心理健康",
    "传染病",
    "疫苗",

    # 经济消费
    "就业",
    "招聘",
    "工资",
    "房价",
    "楼市",
    "消费维权",
    "预付卡",
    "直播带货",
    "虚假宣传",

    # 政务治理
    "官方通报",
    "调查组",
    "问责",
    "整改",
    "政务服务",
    "营商环境",
    "基层治理",
    "行政处罚",

    # 网络舆情
    "诈骗",
    "反诈",
    "网络诈骗",
    "网络谣言",
    "不实信息",
    "辟谣",
    "网暴",
    "个人信息泄露",
    "数据安全",
    "AI诈骗",

    # 灾害天气
    "暴雨",
    "灾害",
    "洪水",
    "台风",
    "地震",
    "山体滑坡",
    "泥石流",
    "高温",
    "寒潮",
    "极端天气",

    # 文娱体育社会热点
    "电影",
    "演唱会",
    "明星",
    "体育赛事",
    "足球",
    "篮球",
    "短视频",
    "游戏",
    "旅游",
    "文旅",
]


def safe_filename(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|]', "_", text)
    text = text.strip()
    return text or "unknown"


def load_records(input_file: Path) -> List[Dict]:
    if not input_file.exists():
        print(f"[ERROR] 找不到输入文件：{input_file}")
        return []

    with input_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("[ERROR] raw_data.json 格式不对，应该是列表")
        return []

    return data


def match_keyword(record: Dict, keyword: str) -> bool:
    title = str(record.get("title", "") or "")
    text = str(record.get("text", "") or "")
    source = str(record.get("source", "") or "")
    url = str(record.get("url", "") or "")

    content = title + "\n" + text + "\n" + source + "\n" + url
    return keyword in content


def short_text(text: str, max_len: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def classify_platform(source: str, url: str) -> str:
    source_lower = str(source or "").lower()
    url_lower = str(url or "").lower()

    if "weibo" in source_lower or "weibo" in url_lower:
        return "weibo"
    if "newsapi" in source_lower:
        return "newsapi"
    if "mediacloud" in source_lower:
        return "mediacloud"
    if "currents" in source_lower:
        return "currents"
    if "bilibili" in source_lower or "bilibili" in url_lower:
        return "bilibili"
    if "zhihu" in source_lower or "zhihu" in url_lower:
        return "zhihu"
    if "toutiao" in source_lower or "toutiao" in url_lower:
        return "toutiao"
    if "rss" in source_lower:
        return "rss"

    return "unknown"


def build_graph_for_keyword(
    keyword: str,
    records: List[Dict],
    min_nodes: int = 3,
    max_nodes: int = 80,
) -> Dict:
    matched = [r for r in records if match_keyword(r, keyword)]

    matched.sort(key=lambda x: parse_time_for_sort(x.get("time", "")))

    if max_nodes > 0:
        matched = matched[:max_nodes]

    nodes: Dict[str, Dict] = {}
    edges: List[Dict] = []

    if len(matched) < min_nodes:
        return {
            "platform": "inferred",
            "keyword": keyword,
            "root": "",
            "nodes": [],
            "edges": [],
            "stats": {
                "node_count": 0,
                "edge_count": 0,
                "source_count": 0,
                "platform_count": 0,
            },
        }

    root_item = matched[0]
    root_id = f"infer_{root_item.get('id')}"

    source_counter = Counter()
    platform_counter = Counter()
    source_first_node = {}
    prev_node_id = ""

    for index, item in enumerate(matched):
        item_id = item.get("id", index)
        node_id = f"infer_{item_id}"

        source = str(item.get("source", "unknown") or "unknown")
        url = str(item.get("url", "") or "")
        platform = classify_platform(source, url)

        source_counter[source] += 1
        platform_counter[platform] += 1

        title = short_text(item.get("title", ""), 100)
        text = short_text(item.get("text", ""), 220)
        time_value = str(item.get("time", "") or "")

        add_node(
            nodes,
            {
                "id": node_id,
                "type": "source" if node_id != root_id else "root",
                "platform": platform,
                "source": source,
                "user_id": "",
                "user_name": source,
                "title": title,
                "text": text,
                "time": time_value,
                "url": url,
                "keyword": keyword,
                "order": index + 1,
            },
        )

        # 1. 源头扩散边：最早来源 -> 后续来源
        if node_id != root_id:
            add_edge(
                edges,
                root_id,
                node_id,
                "time_infer",
                time_value,
                "inferred",
            )

        # 2. 时间链边：上一条 -> 下一条
        if prev_node_id and prev_node_id != node_id:
            add_edge(
                edges,
                prev_node_id,
                node_id,
                "timeline",
                time_value,
                "inferred",
            )

        prev_node_id = node_id

        # 3. 同来源内部传播边：同一个 source 第一次出现 -> 后续出现
        if source not in source_first_node:
            source_first_node[source] = node_id
        else:
            first_node = source_first_node[source]
            if first_node != node_id:
                add_edge(
                    edges,
                    first_node,
                    node_id,
                    "same_source",
                    time_value,
                    "inferred",
                )

    graph = {
        "platform": "inferred",
        "keyword": keyword,
        "root": root_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "description": "由 raw_data.json 按关键词和时间顺序生成的推断传播图，不代表真实转发关系。",
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "source_count": len(source_counter),
            "platform_count": len(platform_counter),
            "top_sources": source_counter.most_common(10),
            "top_platforms": platform_counter.most_common(10),
        },
    }

    return graph


def save_graph(graph: Dict, output_dir: Path) -> Dict:
    keyword = graph.get("keyword", "unknown")
    filename = f"propagation_{safe_filename(keyword)}.json"
    path = output_dir / filename

    with path.open("w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    return {
        "keyword": keyword,
        "file": str(path),
        "relative_file": f"data/propagation_graphs/{filename}",
        "node_count": len(graph.get("nodes", [])),
        "edge_count": len(graph.get("edges", [])),
        "root": graph.get("root", ""),
        "generated_at": graph.get("generated_at", ""),
    }


def main():
    parser = argparse.ArgumentParser(description="批量生成传播图")
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=DEFAULT_KEYWORDS,
        help="要生成传播图的关键词列表",
    )
    parser.add_argument(
        "--input",
        default=str(DATA_DIR / "raw_data.json"),
        help="输入 raw_data.json 路径",
    )
    parser.add_argument(
        "--min-nodes",
        type=int,
        default=3,
        help="至少多少个节点才输出传播图",
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=80,
        help="每个传播图最多多少个节点，0 表示不限制",
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    output_dir = DATA_DIR / "propagation_graphs"
    output_dir.mkdir(parents=True, exist_ok=True)

    records = load_records(input_file)

    if not records:
        print("[ERROR] 没有读取到 raw_data 数据")
        return

    manifest = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input_file": str(input_file),
        "total_raw_records": len(records),
        "graphs": [],
    }

    print("=" * 60)
    print("开始批量生成传播图")
    print(f"原始数据：{len(records)} 条")
    print(f"关键词数：{len(args.keywords)}")
    print("=" * 60)

    first_valid_graph_path = None

    for keyword in args.keywords:
        graph = build_graph_for_keyword(
            keyword=keyword,
            records=records,
            min_nodes=args.min_nodes,
            max_nodes=args.max_nodes,
        )

        node_count = len(graph.get("nodes", []))
        edge_count = len(graph.get("edges", []))

        if node_count < args.min_nodes:
            print(f"[SKIP] {keyword}: 节点太少，只有 {node_count} 个")
            continue

        info = save_graph(graph, output_dir)
        manifest["graphs"].append(info)

        graph_path = Path(info["file"])
        if first_valid_graph_path is None:
            first_valid_graph_path = graph_path

        print(f"[OK] {keyword}: nodes={node_count}, edges={edge_count}")

    manifest_path = DATA_DIR / "propagation_graph_manifest.json"

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 给后端一个固定默认文件：复制第一个有效图为 propagation_graph.json
    if first_valid_graph_path and first_valid_graph_path.exists():
        fixed_path = DATA_DIR / "propagation_graph.json"
        shutil.copyfile(first_valid_graph_path, fixed_path)
        print(f"[INFO] 已生成默认传播图：{fixed_path}")

    print("=" * 60)
    print(f"成功生成传播图：{len(manifest['graphs'])} 个")
    print(f"传播图目录：{output_dir}")
    print(f"传播图索引：{manifest_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()