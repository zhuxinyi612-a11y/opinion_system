"""
把真实传播图 real_propagation_graph.json
转换成后端需要的节点列表格式：

[
  {
    "node_id": "N001",
    "account_name": "普通网友小王",
    "post_time": "2026-07-06 08:00:00",
    "source": "微博",
    "parent_node_id": null
  }
]
"""

import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List

from crawler.config import DATA_DIR


INPUT_FILE = DATA_DIR / "real_propagation_graph.json"
OUTPUT_FILE = DATA_DIR / "backend_propagation_nodes.json"


def format_time(value: Any) -> str:
    """
    尽量把微博时间统一成：
    2026-07-06 08:00:00
    """
    if not value:
        return ""

    s = str(value).strip()

    # ISO 时间，例如 2026-07-06T08:00:00Z
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}[T ]", s):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    # 微博常见英文时间，例如 Sun Jul 05 20:30:00 +0800 2026
    try:
        dt = parsedate_to_datetime(s)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    return s


def get_platform_name(node: Dict[str, Any]) -> str:
    platform = str(node.get("platform") or node.get("source") or "").lower()

    if platform == "weibo":
        return "微博"
    if platform == "zhihu":
        return "知乎"
    if platform == "bilibili":
        return "B站"
    if platform == "toutiao":
        return "今日头条"

    return node.get("source") or "微博"


def load_nodes() -> List[Dict[str, Any]]:
    if not INPUT_FILE.exists():
        print(f"[ERROR] 找不到文件：{INPUT_FILE}")
        return []

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        nodes = data.get("nodes", [])
    elif isinstance(data, list):
        nodes = data
    else:
        nodes = []

    if not isinstance(nodes, list):
        nodes = []

    return nodes


def main():
    nodes = load_nodes()

    if not nodes:
        print("[WARN] real_propagation_graph.json 里没有节点")
        with OUTPUT_FILE.open("w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        print(f"[INFO] 已生成空文件：{OUTPUT_FILE}")
        return

    # 按时间排序，保证 N001、N002 大致符合传播顺序
    nodes = sorted(
        nodes,
        key=lambda x: format_time(x.get("time") or x.get("post_time") or x.get("created_at") or "")
    )

    # 原始 node id -> 后端 N001 格式 id
    id_map: Dict[str, str] = {}

    for idx, node in enumerate(nodes, start=1):
        old_id = str(node.get("id") or node.get("node_id") or node.get("post_id") or "")
        if not old_id:
            old_id = f"unknown_{idx}"

        id_map[old_id] = f"N{idx:03d}"

    backend_nodes = []

    for idx, node in enumerate(nodes, start=1):
        old_id = str(node.get("id") or node.get("node_id") or node.get("post_id") or f"unknown_{idx}")

        parent_old_id = node.get("parent_node_id")

        if parent_old_id:
            parent_node_id = id_map.get(str(parent_old_id))
        else:
            parent_node_id = None

        account_name = (
            node.get("user_name")
            or node.get("account_name")
            or node.get("screen_name")
            or "未知账号"
        )

        post_time = format_time(
            node.get("time")
            or node.get("post_time")
            or node.get("created_at")
            or ""
        )

        backend_node = {
            "node_id": id_map.get(old_id, f"N{idx:03d}"),
            "account_name": account_name,
            "post_time": post_time,
            "source": get_platform_name(node),
            "parent_node_id": parent_node_id,
        }

        backend_nodes.append(backend_node)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(backend_nodes, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("后端传播节点格式导出完成")
    print(f"输入文件：{INPUT_FILE}")
    print(f"输出文件：{OUTPUT_FILE}")
    print(f"节点数：{len(backend_nodes)}")
    print("=" * 60)

    if backend_nodes:
        print("第一条示例：")
        print(json.dumps(backend_nodes[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()