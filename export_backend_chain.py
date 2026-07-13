import json
from pathlib import Path
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List

from crawler.config import DATA_DIR


OUTPUT_FILE = DATA_DIR / "backend_propagation_nodes.json"


def load_json(path: Path):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def format_time(value: Any) -> str:
    if not value:
        return ""

    s = str(value).strip()

    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    try:
        return parsedate_to_datetime(s).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    return s

def is_valid_post_time(value: str) -> bool:
    """
    判断 post_time 是否是有效时间。
    1970 年通常说明原始时间缺失或被当成 0 时间戳。
    """
    if not value:
        return False

    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        if dt.year < 2020:
            return False
        return True
    except Exception:
        return False

def get_node_old_id(node: Dict[str, Any], idx: int) -> str:
    return str(
        node.get("id")
        or node.get("node_id")
        or node.get("post_id")
        or node.get("record_id")
        or f"old_{idx}"
    )


def get_node_time(node: Dict[str, Any]) -> str:
    return format_time(
        node.get("time")
        or node.get("post_time")
        or node.get("created_at")
        or node.get("timestamp")
        or ""
    )


def get_account_name(node: Dict[str, Any]) -> str:
    return (
        node.get("account_name")
        or node.get("user_name")
        or node.get("screen_name")
        or node.get("source")
        or "未知账号"
    )


def get_source(node: Dict[str, Any]) -> str:
    source = str(node.get("source") or node.get("platform") or "")

    if source.lower() == "weibo":
        return "微博"

    return source or "未知来源"


def choose_graph():
    """
    优先用真实微博传播图。
    如果真实图为空，则使用 propagation_graph.json 的 time_infer 图兜底。
    """
    real_path = DATA_DIR / "real_propagation_graph.json"
    infer_path = DATA_DIR / "propagation_graph.json"

    real_graph = load_json(real_path)

    if isinstance(real_graph, dict):
        nodes = real_graph.get("nodes", [])
        edges = real_graph.get("edges", [])
        if nodes and edges:
            print(f"[INFO] 使用真实传播图：{real_path}")
            return real_graph, False

    infer_graph = load_json(infer_path)

    if isinstance(infer_graph, dict):
        nodes = infer_graph.get("nodes", [])
        edges = infer_graph.get("edges", [])
        if nodes:
            print(f"[WARN] 真实传播图为空，使用 time_infer 图兜底：{infer_path}")
            return infer_graph, True

    print("[ERROR] 没有可用传播图")
    return None, True


def main():
    graph, force_inferred = choose_graph()

    if not graph:
        with OUTPUT_FILE.open("w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        print(f"[WARN] 已生成空文件：{OUTPUT_FILE}")
        return

    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []

    if not isinstance(nodes, list):
        nodes = []

    if not isinstance(edges, list):
        edges = []

    # 按时间排序，让 N001/N002 顺序更像传播顺序
    nodes = sorted(
        nodes,
        key=lambda n: get_node_time(n)
    )

    old_to_new: Dict[str, str] = {}

    for idx, node in enumerate(nodes, start=1):
        old_id = get_node_old_id(node, idx)
        old_to_new[old_id] = f"N{idx:03d}"

    # 根据 edges 反推 parent：source -> target，所以 target 的父节点是 source
    parent_map: Dict[str, str] = {}

    for edge in edges:
        source_old = str(edge.get("source") or edge.get("from") or edge.get("source_id") or "")
        target_old = str(edge.get("target") or edge.get("to") or edge.get("target_id") or "")

        if source_old and target_old and target_old not in parent_map:
            parent_map[target_old] = source_old

    backend_nodes = []

    for idx, node in enumerate(nodes, start=1):
        old_id = get_node_old_id(node, idx)
        node_id = old_to_new.get(old_id, f"N{idx:03d}")

        parent_old = (
            node.get("parent_node_id")
            or parent_map.get(old_id)
        )

        if parent_old:
            parent_node_id = old_to_new.get(str(parent_old))
        else:
            parent_node_id = None

        post_time = get_node_time(node)
        time_is_generated = False

        # 如果原始时间无效，就生成一个演示用传播时间
        if not is_valid_post_time(post_time):
            base_time = datetime(2026, 7, 6, 8, 0, 0)
            post_time = (base_time + timedelta(minutes=30 * (idx - 1))).strftime("%Y-%m-%d %H:%M:%S")
            time_is_generated = True

        backend_node = {
            "node_id": node_id,
            "parent_node_id": parent_node_id,
            "post_time": post_time,
            "account_name": get_account_name(node),
            "source": get_source(node),
            "is_inferred": bool(force_inferred or node.get("is_inferred", False)),
            "time_is_generated": time_is_generated,
        }

        backend_nodes.append(backend_node)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(backend_nodes, f, ensure_ascii=False, indent=2)

    root_count = sum(1 for n in backend_nodes if n["parent_node_id"] is None)
    child_count = sum(1 for n in backend_nodes if n["parent_node_id"] is not None)

    print("=" * 60)
    print("后端传播链节点导出完成")
    print(f"输出文件：{OUTPUT_FILE}")
    print(f"节点数：{len(backend_nodes)}")
    print(f"根节点数：{root_count}")
    print(f"有父节点的节点数：{child_count}")
    print(f"是否推断图：{force_inferred}")
    print("=" * 60)

    print("前 5 条示例：")
    print(json.dumps(backend_nodes[:5], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()