import argparse
import json
import time
from typing import Dict, Any, List, Tuple

from crawler.bilibili_real_graph import build_graph, export_outputs
from crawler.config import DATA_DIR


DEFAULT_KEYWORDS = [
    "校园霸凌",
    "食品安全",
    "交通事故",
    "官方通报",
    "辟谣",
    "火灾",
    "暴雨",
    "医疗纠纷",
    "诈骗",
]


def edge_key(edge: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        str(edge.get("source", "")),
        str(edge.get("target", "")),
        str(edge.get("relation", "")),
    )


def merge_graphs(all_nodes: Dict[str, Dict[str, Any]], all_edges: Dict[Tuple[str, str, str], Dict[str, Any]], nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
    for node in nodes:
        node_id = str(node.get("id", ""))
        if not node_id:
            continue
        all_nodes[node_id] = node

    for edge in edges:
        k = edge_key(edge)
        if not k[0] or not k[1]:
            continue
        all_edges[k] = edge


def main():
    parser = argparse.ArgumentParser(description="批量采集 B站真实传播图，并合并输出")
    parser.add_argument("--keywords", nargs="*", default=DEFAULT_KEYWORDS, help="关键词列表")
    parser.add_argument("--max-videos", type=int, default=15, help="每个关键词最多处理几个视频")
    parser.add_argument("--comment-pages", type=int, default=2, help="每个视频抓几页一级评论")
    parser.add_argument("--reply-pages", type=int, default=1, help="每条一级评论抓几页二级回复")
    args = parser.parse_args()

    all_nodes: Dict[str, Dict[str, Any]] = {}
    all_edges: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    print("=" * 60)
    print("开始批量采集 B站真实传播图")
    print(f"关键词：{args.keywords}")
    print(f"每个关键词最大视频数：{args.max_videos}")
    print(f"一级评论页数：{args.comment_pages}")
    print(f"二级回复页数：{args.reply_pages}")
    print("=" * 60)

    for idx, keyword in enumerate(args.keywords, start=1):
        print("\n" + "=" * 60)
        print(f"[{idx}/{len(args.keywords)}] 开始关键词：{keyword}")
        print("=" * 60)

        try:
            nodes, edges = build_graph(
                keyword=keyword,
                max_videos=args.max_videos,
                comment_pages=args.comment_pages,
                reply_pages=args.reply_pages,
                url="",
            )
        except Exception as e:
            print(f"[ERROR] 关键词 {keyword} 采集失败：{e}")
            continue

        print(f"[INFO] 关键词 {keyword} 获取节点 {len(nodes)}，边 {len(edges)}")

        if nodes and edges:
            merge_graphs(all_nodes, all_edges, nodes, edges)
            print(f"[INFO] 当前累计节点 {len(all_nodes)}，累计边 {len(all_edges)}")
        else:
            print(f"[WARN] 关键词 {keyword} 没有有效边，跳过合并")

        time.sleep(3)

    merged_nodes = list(all_nodes.values())
    merged_edges = list(all_edges.values())

    print("\n" + "=" * 60)
    print("批量采集结束")
    print(f"合并后节点数：{len(merged_nodes)}")
    print(f"合并后边数：{len(merged_edges)}")
    print("=" * 60)

    if not merged_nodes or not merged_edges:
        print("[WARN] 合并结果没有有效边，不写入文件，避免覆盖旧成功数据")
        return

    # 使用原来的 export_outputs 输出：
    # real_propagation_graph.json
    # real_propagation_nodes.json
    # real_propagation_edges.json
    # backend_propagation_nodes.json
    export_outputs(merged_nodes, merged_edges)

    # 额外备份一份批量成功版
    files = [
        "backend_propagation_nodes.json",
        "real_propagation_graph.json",
        "real_propagation_nodes.json",
        "real_propagation_edges.json",
    ]

    for name in files:
        src = DATA_DIR / name
        dst = DATA_DIR / name.replace(".json", ".batch_success.json")
        if src.exists():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"[INFO] 已备份：{dst}")

    print("[INFO] 批量真实传播图输出完成")


if __name__ == "__main__":
    main()