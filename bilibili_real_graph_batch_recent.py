import argparse
import json
import shutil
import time
from datetime import datetime
from typing import Dict, Any, List, Tuple, Set

from crawler.bilibili_real_graph import build_graph, export_outputs
from crawler.config import DATA_DIR


DEFAULT_KEYWORDS = [
    "校园霸凌",
    "食品安全",
    "食品中毒",
    "交通事故",
    "车祸",
    "火灾",
    "爆炸",
    "燃气爆炸",
    "暴雨",
    "洪水",
    "地质灾害",
    "坍塌",
    "医疗纠纷",
    "医疗事故",
    "诈骗",
    "电信诈骗",
    "辟谣",
    "官方通报",
    "突发",
    "安全事故",
    "学校",
    "学生",
    "消防",
    "网络谣言",
]


def parse_year(value: str) -> int:
    if not value:
        return 0

    s = str(value).strip()

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt).year
        except Exception:
            pass

    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).year
    except Exception:
        return 0


def edge_key(edge: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        str(edge.get("source", "")),
        str(edge.get("target", "")),
        str(edge.get("relation", "")),
    )


def filter_recent_graph(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    min_year: int,
):
    """
    只保留近期视频根节点及其评论/回复子树。
    规则：
    1. video 节点 post_time 年份 >= min_year，作为根节点保留
    2. 保留这些 video 下面的 comment/reply 后代节点
    3. 删除没有近期根节点支撑的旧图
    """
    node_map = {str(n.get("id", "")): n for n in nodes if n.get("id")}

    keep_ids: Set[str] = set()

    for node_id, node in node_map.items():
        if node.get("node_type") != "video":
            continue

        year = parse_year(node.get("post_time", "") or node.get("time", ""))

        if year >= min_year:
            keep_ids.add(node_id)

    changed = True

    while changed:
        changed = False

        for edge in edges:
            source = str(edge.get("source", ""))
            target = str(edge.get("target", ""))

            if source in keep_ids and target in node_map and target not in keep_ids:
                keep_ids.add(target)
                changed = True

    recent_nodes = [n for n in nodes if str(n.get("id", "")) in keep_ids]

    recent_edges = [
        e for e in edges
        if str(e.get("source", "")) in keep_ids
        and str(e.get("target", "")) in keep_ids
    ]

    return recent_nodes, recent_edges


def merge_graphs(
    all_nodes: Dict[str, Dict[str, Any]],
    all_edges: Dict[Tuple[str, str, str], Dict[str, Any]],
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
):
    for node in nodes:
        node_id = str(node.get("id", ""))
        if node_id:
            all_nodes[node_id] = node

    for edge in edges:
        k = edge_key(edge)
        if k[0] and k[1]:
            all_edges[k] = edge

def load_json_list(path):
    if not path.exists():
        return []
    try:
        return json.load(open(path, "r", encoding="utf-8"))
    except Exception:
        return []


def backend_score(path):
    """
    返回一个分数：
    节点数、有父节点数、真实节点数
    用来判断新图是不是比旧图更好。
    """
    data = load_json_list(path)
    node_count = len(data)
    parent_count = sum(1 for x in data if x.get("parent_node_id"))
    real_count = sum(1 for x in data if x.get("is_inferred") is False)
    return node_count, parent_count, real_count


def make_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def copy_if_exists(src, dst):
    if src.exists():
        shutil.copy2(src, dst)
        print(f"[INFO] 已备份：{dst}")


def backup_current_as_version(tag):
    """
    给当前成功文件打一个不会被覆盖的时间戳备份。
    """
    ts = make_timestamp()

    files = [
        "backend_propagation_nodes.json",
        "real_propagation_graph.json",
        "real_propagation_nodes.json",
        "real_propagation_edges.json",
    ]

    for name in files:
        src = DATA_DIR / name
        dst = DATA_DIR / name.replace(".json", f".{tag}_{ts}.json")
        copy_if_exists(src, dst)


def update_best_if_better():
    """
    只有当前输出比 recent_best 更大，才更新 best。
    """
    current_backend = DATA_DIR / "backend_propagation_nodes.json"
    best_backend = DATA_DIR / "backend_propagation_nodes.recent_best.json"

    current_score = backend_score(current_backend)
    best_score = backend_score(best_backend)

    print("=" * 60)
    print("[INFO] 当前图评分：", current_score)
    print("[INFO] 最佳图评分：", best_score)
    print("=" * 60)

    # 比较规则：先比节点数，再比有父节点数
    if current_score[0] > best_score[0] or (
        current_score[0] == best_score[0] and current_score[1] > best_score[1]
    ):
        print("[INFO] 当前图更大，更新 recent_best")

        mapping = [
            ("backend_propagation_nodes.json", "backend_propagation_nodes.recent_best.json"),
            ("real_propagation_graph.json", "real_propagation_graph.recent_best.json"),
            ("real_propagation_nodes.json", "real_propagation_nodes.recent_best.json"),
            ("real_propagation_edges.json", "real_propagation_edges.recent_best.json"),
        ]

        for src_name, dst_name in mapping:
            copy_if_exists(DATA_DIR / src_name, DATA_DIR / dst_name)

        backup_current_as_version("recent")
        return True

    print("[WARN] 当前图没有超过 recent_best，不更新最佳版")
    return False

def main():
    parser = argparse.ArgumentParser(description="批量采集近期 B站真实传播图")
    parser.add_argument("--keywords", nargs="*", default=DEFAULT_KEYWORDS, help="关键词列表")
    parser.add_argument("--min-year", type=int, default=2025, help="只保留该年份及以后的 video 根节点")
    parser.add_argument("--max-videos", type=int, default=30, help="每个关键词最多处理几个视频")
    parser.add_argument("--comment-pages", type=int, default=2, help="每个视频抓几页一级评论")
    parser.add_argument("--reply-pages", type=int, default=1, help="每条一级评论抓几页二级回复")
    args = parser.parse_args()

    all_nodes: Dict[str, Dict[str, Any]] = {}
    all_edges: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    print("=" * 60)
    print("开始批量采集近期 B站真实传播图")
    print(f"关键词：{args.keywords}")
    print(f"只保留年份：{args.min_year} 年及以后")
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

        print(f"[INFO] 关键词 {keyword} 原始获取节点 {len(nodes)}，边 {len(edges)}")

        recent_nodes, recent_edges = filter_recent_graph(
            nodes=nodes,
            edges=edges,
            min_year=args.min_year,
        )

        print(f"[INFO] 关键词 {keyword} 近期过滤后节点 {len(recent_nodes)}，边 {len(recent_edges)}")

        if recent_nodes and recent_edges:
            merge_graphs(all_nodes, all_edges, recent_nodes, recent_edges)
            print(f"[INFO] 当前累计近期节点 {len(all_nodes)}，累计近期边 {len(all_edges)}")
        else:
            print(f"[WARN] 关键词 {keyword} 没有近期有效边，跳过合并")

        time.sleep(3)

    merged_nodes = list(all_nodes.values())
    merged_edges = list(all_edges.values())

    print("\n" + "=" * 60)
    print("近期批量采集结束")
    print(f"合并后近期节点数：{len(merged_nodes)}")
    print(f"合并后近期边数：{len(merged_edges)}")
    print("=" * 60)

    if not merged_nodes or not merged_edges:
        print("[WARN] 合并结果没有近期有效边，不写入文件，避免覆盖旧成功数据")
        return

    # 先看新采集结果是否为空
    if not merged_nodes or not merged_edges:
        print("[WARN] 合并结果没有近期有效边，不写入文件，避免覆盖旧成功数据")
        return

    # 先检查旧 best 分数
    best_backend = DATA_DIR / "backend_propagation_nodes.recent_best.json"
    best_score = backend_score(best_backend)

    new_node_count = len(merged_nodes)
    new_edge_count = len(merged_edges)

    print("=" * 60)
    print(f"[INFO] 新采集节点数：{new_node_count}")
    print(f"[INFO] 新采集边数：{new_edge_count}")
    print(f"[INFO] 当前 recent_best 评分：{best_score}")
    print("=" * 60)

    # 如果已经有 best，并且新图更小，直接不写入，避免覆盖当前工作文件
    if best_score[0] > 0 and new_node_count < best_score[0]:
        print("[WARN] 新图节点数小于 recent_best，不写入，避免小图覆盖大图")
        print(f"[WARN] 新图节点数：{new_node_count}")
        print(f"[WARN] best 节点数：{best_score[0]}")
        return

    # 新图不小于 best，才真正写入当前文件
    export_outputs(merged_nodes, merged_edges)

    # 写入之后，再判断是否更新 best
    update_best_if_better()

    print("[INFO] 近期真实传播图输出完成")


if __name__ == "__main__":
    main()