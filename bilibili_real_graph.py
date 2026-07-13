"""
B站真实传播图：从 B站视频评论区构建真实父子传播关系。
支持 --keyword 从 raw_data 找视频，也支持 --url 直接指定 BV/av 链接。
输出 real_propagation_graph.json / real_propagation_nodes.json / real_propagation_edges.json / backend_propagation_nodes.json。
"""

import argparse
import json
import os
import re
import time
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from crawler.config import DATA_DIR
from crawler.http_client import safe_get
from crawler.save_data import clean_text


VIEW_API = "https://api.bilibili.com/x/web-interface/view"
COMMENT_API = "https://api.bilibili.com/x/v2/reply/main"
REPLY_API = "https://api.bilibili.com/x/v2/reply/reply"


def get_headers(url: str = "") -> Dict[str, str]:
    load_dotenv()
    cookie = os.getenv("BILIBILI_COOKIE", "").strip()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": url or "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
        "Connection": "keep-alive",
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers


def format_bili_time(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        ts = int(value)
        if ts <= 946656000:  # 2000-01-01 以前基本视为无效
            return ""
        dt = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def extract_bili_video_id(url: str) -> Dict[str, str]:
    """同时支持 BV 链接和 av 链接。"""
    result = {"bvid": "", "aid": ""}
    if not url:
        return result

    m = re.search(r"(BV[a-zA-Z0-9]+)", url)
    if m:
        result["bvid"] = m.group(1)
        return result

    m = re.search(r"/video/av(\d+)", url)
    if m:
        result["aid"] = m.group(1)
        return result

    m = re.search(r"av(\d+)", url)
    if m:
        result["aid"] = m.group(1)
        return result

    return result


def load_raw_bili_records(keyword: str = "", max_videos: int = 5) -> List[Dict[str, Any]]:
    raw_path = DATA_DIR / "raw_data.json"
    if not raw_path.exists():
        print(f"[ERROR] 找不到 raw_data.json：{raw_path}")
        return []

    with raw_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for item in data:
        title = clean_text(item.get("title", ""))
        text = clean_text(item.get("text", ""))
        source = clean_text(item.get("source", ""))
        url = clean_text(item.get("url", ""))

        if "bilibili.com/video" not in url.lower() and not source.startswith("B站"):
            continue

        if keyword and keyword not in (title + " " + text):
            continue

        video_id = extract_bili_video_id(url)
        bvid = video_id.get("bvid", "")
        aid = video_id.get("aid", "")

        if not bvid and not aid:
            continue

        records.append({
            "title": title,
            "source": source or "B站",
            "url": url,
            "bvid": bvid,
            "aid": aid,
        })

    seen = set()
    unique = []
    for r in records:
        key = r.get("bvid") or r.get("aid") or r.get("url")
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    print(f"[INFO] 找到 B站视频记录 {len(unique)} 条")
    return unique[:max_videos]


def resolve_video_info(bvid: str = "", aid: str = "", url: str = "") -> Optional[Dict[str, Any]]:
    if bvid:
        params = {"bvid": bvid}
    elif aid:
        params = {"aid": aid}
    else:
        return None

    resp = safe_get(VIEW_API, params=params, platform="bilibili_view", headers=get_headers(url))
    if not resp:
        print(f"[WARN] B站 view 请求失败 bvid={bvid}, aid={aid}")
        return None

    try:
        payload = resp.json()
    except Exception:
        print("[WARN] B站 view 返回不是 JSON")
        return None

    if payload.get("code") != 0:
        print(f"[WARN] B站 view 失败 bvid={bvid}, aid={aid}, code={payload.get('code')}, msg={payload.get('message')}")
        return None

    data = payload.get("data") or {}
    real_aid = data.get("aid") or aid
    real_bvid = clean_text(data.get("bvid", "")) or bvid
    owner = data.get("owner") or {}

    if not real_aid:
        print("[WARN] B站 view 没有 aid")
        return None

    return {
        "aid": str(real_aid),
        "bvid": real_bvid,
        "title": clean_text(data.get("title", "")),
        "owner_name": clean_text(owner.get("name", "")),
        "pubdate": format_bili_time(data.get("pubdate")),
        "url": f"https://www.bilibili.com/video/{real_bvid}" if real_bvid else url,
    }


def fetch_comments(aid: str, url: str, comment_pages: int = 2) -> List[Dict[str, Any]]:
    all_comments = []
    next_page = 0

    for page_idx in range(comment_pages):
        params = {"type": 1, "oid": aid, "mode": 3, "next": next_page, "ps": 20}
        resp = safe_get(COMMENT_API, params=params, platform="bilibili_comment", headers=get_headers(url))
        if not resp:
            print(f"[WARN] B站评论请求失败 aid={aid}")
            break

        try:
            payload = resp.json()
        except Exception:
            print("[WARN] B站评论返回不是 JSON")
            break

        if payload.get("code") != 0:
            print(f"[WARN] B站评论接口失败 aid={aid}, code={payload.get('code')}, msg={payload.get('message')}")
            break

        data = payload.get("data") or {}
        replies = data.get("replies") or []
        if not replies:
            print(f"[INFO] aid={aid} 没有一级评论或评论区不可见")
            break

        all_comments.extend(replies)
        cursor = data.get("cursor") or {}
        next_page = cursor.get("next", 0)
        print(f"[INFO] aid={aid} 评论页 {page_idx + 1} 获取一级评论 {len(replies)} 条")

        if not next_page:
            break
        time.sleep(random.uniform(2, 4))

    return all_comments


def fetch_sub_replies(aid: str, root_rpid: str, url: str, reply_pages: int = 1) -> List[Dict[str, Any]]:
    all_replies = []

    for pn in range(1, reply_pages + 1):
        params = {"type": 1, "oid": aid, "root": root_rpid, "pn": pn, "ps": 20}
        resp = safe_get(REPLY_API, params=params, platform="bilibili_sub_reply", headers=get_headers(url))
        if not resp:
            break

        try:
            payload = resp.json()
        except Exception:
            print("[WARN] B站二级回复返回不是 JSON")
            break

        if payload.get("code") != 0:
            break

        data = payload.get("data") or {}
        replies = data.get("replies") or []
        if not replies:
            break

        all_replies.extend(replies)
        print(f"[INFO] root={root_rpid} 二级回复页 {pn} 获取 {len(replies)} 条")
        time.sleep(random.uniform(1, 2))

    return all_replies


def get_member_name(reply: Dict[str, Any]) -> str:
    member = reply.get("member") or {}
    return clean_text(member.get("uname", "")) or "B站用户"


def get_reply_text(reply: Dict[str, Any]) -> str:
    content = reply.get("content") or {}
    return clean_text(content.get("message", ""))


def add_edge(edges: List[Dict[str, Any]], source: str, target: str, relation: str, post_time: str):
    edges.append({
        "source": source,
        "target": target,
        "relation": relation,
        "type": relation,
        "platform": "bilibili",
        "post_time": post_time,
        "is_inferred": False,
    })


def build_graph(keyword: str, max_videos: int, comment_pages: int, reply_pages: int, url: str = ""):
    if url:
        video_id = extract_bili_video_id(url)
        bvid = video_id.get("bvid", "")
        aid = video_id.get("aid", "")
        if not bvid and not aid:
            print(f"[ERROR] 无法从链接中提取 BV/av 号：{url}")
            records = []
        else:
            records = [{"title": "", "source": "B站", "url": url, "bvid": bvid, "aid": aid}]
            print(f"[INFO] 使用手动输入的 B站视频：bvid={bvid or '-'}, aid={aid or '-'}")
    else:
        records = load_raw_bili_records(keyword=keyword, max_videos=max_videos)

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    for record in records:
        bvid = record.get("bvid", "")
        aid_from_record = record.get("aid", "")
        record_url = record["url"]

        video_info = resolve_video_info(bvid=bvid, aid=aid_from_record, url=record_url)
        if not video_info:
            continue

        aid = video_info["aid"]
        video_node_id = f"bili_video_{aid}"
        nodes[video_node_id] = {
            "id": video_node_id,
            "platform": "bilibili",
            "node_type": "video",
            "account_name": video_info["owner_name"] or record["source"],
            "user_name": video_info["owner_name"] or record["source"],
            "title": video_info["title"] or record["title"],
            "text": video_info["title"] or record["title"],
            "post_time": video_info["pubdate"],
            "time": video_info["pubdate"],
            "source": "B站",
            "url": video_info["url"],
            "parent_node_id": None,
            "is_inferred": False,
            "time_is_generated": False,
        }

        comments = fetch_comments(aid, video_info["url"], comment_pages=comment_pages)
        print(f"[INFO] 视频 {video_info.get('bvid') or aid_from_record or aid} 一级评论总数：{len(comments)}")

        for comment in comments:
            rpid = str(comment.get("rpid") or "")
            if not rpid:
                continue

            comment_node_id = f"bili_comment_{rpid}"
            comment_time = format_bili_time(comment.get("ctime"))
            nodes[comment_node_id] = {
                "id": comment_node_id,
                "platform": "bilibili",
                "node_type": "comment",
                "account_name": get_member_name(comment),
                "user_name": get_member_name(comment),
                "title": video_info["title"],
                "text": get_reply_text(comment),
                "post_time": comment_time,
                "time": comment_time,
                "source": "B站",
                "url": video_info["url"],
                "parent_node_id": video_node_id,
                "is_inferred": False,
                "time_is_generated": False,
            }
            add_edge(edges, source=video_node_id, target=comment_node_id, relation="bilibili_video_comment", post_time=comment_time)

            sub_replies = fetch_sub_replies(aid=aid, root_rpid=rpid, url=video_info["url"], reply_pages=reply_pages)
            for sub in sub_replies:
                sub_rpid = str(sub.get("rpid") or "")
                if not sub_rpid:
                    continue

                sub_node_id = f"bili_reply_{sub_rpid}"
                sub_time = format_bili_time(sub.get("ctime"))
                nodes[sub_node_id] = {
                    "id": sub_node_id,
                    "platform": "bilibili",
                    "node_type": "reply",
                    "account_name": get_member_name(sub),
                    "user_name": get_member_name(sub),
                    "title": video_info["title"],
                    "text": get_reply_text(sub),
                    "post_time": sub_time,
                    "time": sub_time,
                    "source": "B站",
                    "url": video_info["url"],
                    "parent_node_id": comment_node_id,
                    "is_inferred": False,
                    "time_is_generated": False,
                }
    return list(nodes.values()), edges


def export_outputs(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    graph_path = DATA_DIR / "real_propagation_graph.json"
    nodes_path = DATA_DIR / "real_propagation_nodes.json"
    edges_path = DATA_DIR / "real_propagation_edges.json"
    backend_path = DATA_DIR / "backend_propagation_nodes.json"

    if len(nodes) == 0 or len(edges) == 0:
        print("=" * 60)
        print("[WARN] 本次 B站真实传播图没有有效边，不写入文件，避免覆盖旧数据")
        print(f"[INFO] 节点数：{len(nodes)}，边数：{len(edges)}")
        print(f"[INFO] 保留旧真实图：{graph_path}")
        print(f"[INFO] 保留旧后端文件：{backend_path}")
        print("=" * 60)
        return

    graph = {
        "graph_type": "real",
        "platform": "bilibili",
        "relation_source": "bilibili_video_comment_reply",
        "is_inferred": False,
        "time_is_generated": False,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "description": "真实传播图：边来自 B站视频-评论-回复结构，不是时间推断。",
    }

    with graph_path.open("w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    with nodes_path.open("w", encoding="utf-8") as f:
        json.dump(nodes, f, ensure_ascii=False, indent=2)
    with edges_path.open("w", encoding="utf-8") as f:
        json.dump(edges, f, ensure_ascii=False, indent=2)

    old_to_new: Dict[str, str] = {}
    sorted_nodes = sorted(nodes, key=lambda n: n.get("post_time") or "")
    for idx, node in enumerate(sorted_nodes, start=1):
        old_to_new[node["id"]] = f"N{idx:03d}"

    backend_nodes = []
    for node in sorted_nodes:
        old_id = node["id"]
        parent_old = node.get("parent_node_id")
        backend_nodes.append({
            "node_id": old_to_new[old_id],
            "parent_node_id": old_to_new.get(parent_old) if parent_old else None,
            "post_time": node.get("post_time", ""),
            "account_name": node.get("account_name", "未知账号"),
            "source": node.get("source", "B站"),
            "is_inferred": False,
            "time_is_generated": False,
            "raw_node_id": old_id,
            "node_type": node.get("node_type", ""),
            "title": node.get("title", ""),
            "text": node.get("text", ""),
            "url": node.get("url", ""),
        })

    with backend_path.open("w", encoding="utf-8") as f:
        json.dump(backend_nodes, f, ensure_ascii=False, indent=2)

    root_count = sum(1 for n in backend_nodes if n["parent_node_id"] is None)
    child_count = sum(1 for n in backend_nodes if n["parent_node_id"] is not None)

    print("=" * 60)
    print("B站真实传播图生成完成")
    print(f"真实节点数：{len(nodes)}")
    print(f"真实边数：{len(edges)}")
    print(f"后端节点数：{len(backend_nodes)}")
    print(f"根节点数：{root_count}")
    print(f"有父节点节点数：{child_count}")
    print(f"真实图文件：{graph_path}")
    print(f"后端文件：{backend_path}")
    print("=" * 60)
    print("后端前 5 条示例：")
    print(json.dumps(backend_nodes[:5], ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="采集 B站真实视频-评论-回复传播图")
    parser.add_argument("--keyword", default="", help="从 raw_data 中筛选包含该关键词的 B站视频")
    parser.add_argument("--url", default="", help="直接指定 B站视频链接，例如 https://www.bilibili.com/video/BVxxxx 或 http://www.bilibili.com/video/av123456")
    parser.add_argument("--max-videos", type=int, default=3, help="最多处理几个 B站视频")
    parser.add_argument("--comment-pages", type=int, default=2, help="每个视频抓几页一级评论")
    parser.add_argument("--reply-pages", type=int, default=1, help="每条一级评论抓几页二级回复")
    args = parser.parse_args()

    print("=" * 60)
    print("开始采集 B站真实传播图")
    print(f"关键词：{args.keyword or '不限'}")
    print(f"手动链接：{args.url or '未指定'}")
    print(f"最大视频数：{args.max_videos}")
    print(f"一级评论页数：{args.comment_pages}")
    print(f"二级回复页数：{args.reply_pages}")
    print("=" * 60)

    nodes, edges = build_graph(
        keyword=args.keyword,
        max_videos=args.max_videos,
        comment_pages=args.comment_pages,
        reply_pages=args.reply_pages,
        url=args.url,
    )
    export_outputs(nodes, edges)


if __name__ == "__main__":
    main()
