import argparse
import json
import os
import random
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

from crawler.config import DATA_DIR
from crawler.save_data import clean_text


BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def base62_decode(text: str) -> int:
    num = 0
    for char in text:
        num = num * 62 + BASE62.index(char)
    return num


def weibo_bid_to_mid(bid: str) -> str:
    """
    把微博网页版 URL 里的短 ID 转成数字 mid。
    例如：https://weibo.com/xxx/NeABCxxx 里面的 NeABCxxx。
    """
    mid = ""

    for end in range(len(bid), 0, -4):
        start = max(end - 4, 0)
        chunk = bid[start:end]
        value = str(base62_decode(chunk))

        if start != 0:
            value = value.zfill(7)

        mid = value + mid

    return mid


def parse_weibo_id(url_or_id: str) -> str:
    """
    支持：
    1. 直接传数字 mid
    2. https://m.weibo.cn/status/数字mid
    3. https://weibo.com/用户id/短ID
    4. https://weibo.com/statuses/show?id=数字mid
    """
    value = url_or_id.strip()

    # 直接传数字 mid
    if value.isdigit():
        return value

    parsed = urlparse(value)
    query = parse_qs(parsed.query)
    parts = [p for p in parsed.path.split("/") if p]

    # 处理 query 里的 id / mid
    for key in ("id", "mid"):
        if key in query and query[key]:
            candidate = query[key][0]
            if candidate.isdigit():
                return candidate

    # m.weibo.cn/status/数字mid
    if "m.weibo.cn" in parsed.netloc:
        if len(parts) >= 2 and parts[-2] == "status" and parts[-1].isdigit():
            return parts[-1]

    # weibo.com/用户ID/短ID
    # 例如：https://weibo.com/1002568141/R7D4YqVGF
    if "weibo.com" in parsed.netloc:
        if len(parts) >= 2:
            bid = parts[1]
            if re.fullmatch(r"[0-9a-zA-Z]+", bid) and not bid.isdigit():
                return weibo_bid_to_mid(bid)

    # 兜底：如果最后一段是短ID，也尝试转换
    if parts:
        bid = parts[-1]
        if re.fullmatch(r"[0-9a-zA-Z]+", bid) and not bid.isdigit():
            return weibo_bid_to_mid(bid)

    raise ValueError(f"无法从微博链接中解析 mid：{url_or_id}")


def get_headers(platform: str) -> Dict[str, str]:
    load_dotenv()

    cookie_map = {
        "weibo": "WEIBO_COOKIE",
        "toutiao": "TOUTIAO_COOKIE",
        "zhihu": "ZHIHU_COOKIE",
        "xhs": "XHS_COOKIE",
    }

    cookie = os.getenv(cookie_map.get(platform, ""), "").strip()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://m.weibo.cn/",
        "Connection": "keep-alive",
    }

    if cookie:
        headers["Cookie"] = cookie

    return headers


def safe_json_get(url: str, params: Dict = None, platform: str = "weibo") -> Dict:
    headers = get_headers(platform)

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=20)
    except Exception as e:
        print(f"[WARN] 请求异常：{e}")
        return {}

    if resp.status_code != 200:
        print(f"[WARN] HTTP {resp.status_code}: {resp.url}")
        return {}

    try:
        return resp.json()
    except Exception:
        print("[WARN] 返回内容不是 JSON，可能被风控或需要登录")
        return {}


def add_node(nodes: Dict[str, Dict], node: Dict):
    node_id = node.get("id")
    if not node_id:
        return

    if node_id not in nodes:
        nodes[node_id] = node


def add_edge(edges: List[Dict], source: str, target: str, edge_type: str, time_value: str, platform: str):
    if not source or not target or source == target:
        return

    edge = {
        "source": source,
        "target": target,
        "type": edge_type,
        "time": time_value or "",
        "platform": platform,
    }

    key = (edge["source"], edge["target"], edge["type"])

    for old in edges:
        if (old["source"], old["target"], old["type"]) == key:
            return

    edges.append(edge)


def parse_weibo_time(value) -> str:
    if not value:
        return ""

    if isinstance(value, int):
        try:
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(value)

    return str(value)


def strip_html(text: str) -> str:
    text = re.sub(r"<.*?>", " ", text or "")
    return clean_text(text)


def crawl_weibo_status(mid: str) -> Dict:
    """
    获取原帖基础信息。
    """
    url = "https://m.weibo.cn/statuses/show"
    payload = safe_json_get(url, params={"id": mid}, platform="weibo")

    if not payload:
        return {}

    return payload


def crawl_weibo_reposts(mid: str, max_pages: int, nodes: Dict[str, Dict], edges: List[Dict], root_id: str):
    """
    采集微博转发列表。
    注意：平台可能只返回部分转发，不保证完整链。
    """
    api = "https://m.weibo.cn/api/statuses/repostTimeline"

    for page in range(1, max_pages + 1):
        payload = safe_json_get(api, params={"id": mid, "page": page}, platform="weibo")

        data = payload.get("data") or {}
        reposts = data.get("data") or []

        print(f"[INFO] 微博转发 page={page} 获取 {len(reposts)} 条")

        if not reposts:
            break

        for item in reposts:
            repost_id = str(item.get("id") or item.get("mid") or "")
            if not repost_id:
                continue

            node_id = f"weibo_repost_{repost_id}"

            user = item.get("user") or {}
            user_name = user.get("screen_name") or ""
            user_id = str(user.get("id") or "")

            text = strip_html(item.get("text") or "")
            time_value = parse_weibo_time(item.get("created_at"))

            add_node(nodes, {
                "id": node_id,
                "type": "repost",
                "platform": "weibo",
                "user_id": user_id,
                "user_name": user_name,
                "text": text,
                "time": time_value,
                "url": f"https://m.weibo.cn/status/{repost_id}",
            })

            add_edge(edges, root_id, node_id, "repost", time_value, "weibo")

        time.sleep(random.uniform(4, 8))


def crawl_weibo_comments(mid: str, max_pages: int, nodes: Dict[str, Dict], edges: List[Dict], root_id: str):
    """
    采集微博评论列表，作为传播互动链补充。
    """
    api = "https://m.weibo.cn/comments/hotflow"
    max_id = ""

    for page in range(1, max_pages + 1):
        params = {
            "id": mid,
            "mid": mid,
            "max_id_type": 0,
        }

        if max_id:
            params["max_id"] = max_id

        payload = safe_json_get(api, params=params, platform="weibo")

        data = payload.get("data") or {}
        comments = data.get("data") or []

        print(f"[INFO] 微博评论 page={page} 获取 {len(comments)} 条")

        if not comments:
            break

        for item in comments:
            comment_id = str(item.get("id") or "")
            if not comment_id:
                continue

            node_id = f"weibo_comment_{comment_id}"

            user = item.get("user") or {}
            user_name = user.get("screen_name") or ""
            user_id = str(user.get("id") or "")

            text = strip_html(item.get("text") or "")
            time_value = parse_weibo_time(item.get("created_at"))

            add_node(nodes, {
                "id": node_id,
                "type": "comment",
                "platform": "weibo",
                "user_id": user_id,
                "user_name": user_name,
                "text": text,
                "time": time_value,
                "url": f"https://m.weibo.cn/comment/{comment_id}",
            })

            add_edge(edges, root_id, node_id, "comment", time_value, "weibo")

        max_id = str(data.get("max_id") or "")
        if not max_id or max_id == "0":
            break

        time.sleep(random.uniform(4, 8))


def crawl_weibo_graph(url_or_id: str, max_pages: int) -> Dict:
    mid = parse_weibo_id(url_or_id)
    print(f"[INFO] 解析到微博 mid={mid}")

    nodes: Dict[str, Dict] = {}
    edges: List[Dict] = []

    root_id = f"weibo_post_{mid}"

    status = crawl_weibo_status(mid)

    user = status.get("user") or {}
    text = strip_html(status.get("text") or "")
    time_value = parse_weibo_time(status.get("created_at"))

    add_node(nodes, {
        "id": root_id,
        "type": "post",
        "platform": "weibo",
        "user_id": str(user.get("id") or ""),
        "user_name": user.get("screen_name") or "",
        "text": text,
        "time": time_value,
        "url": f"https://m.weibo.cn/status/{mid}",
    })

    crawl_weibo_reposts(mid, max_pages, nodes, edges, root_id)
    crawl_weibo_comments(mid, max_pages, nodes, edges, root_id)

    return {
        "platform": "weibo",
        "root": root_id,
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def parse_time_for_sort(value: str) -> datetime:
    """
    把各种时间格式统一转成“无时区”的 datetime，避免排序时报错：
    TypeError: can't compare offset-naive and offset-aware datetimes
    """
    if not value:
        return datetime.max

    value = str(value).strip()

    # 处理 ISO 格式，比如 2026-07-07T05:40:02Z
    try:
        fixed = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(fixed)

        # 如果带时区，统一转成 UTC 后去掉时区
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

        return dt
    except Exception:
        pass

    # 处理 RSS / 英文日期，比如 Tue, 07 Jul 2026 05:40:02 GMT
    try:
        dt = parsedate_to_datetime(value)

        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

        return dt
    except Exception:
        pass

    # 处理常见普通时间
    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
        "%Y年%m月%d日 %H:%M",
        "%Y年%m月%d日",
    ]:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue

    return datetime.max


def infer_graph_from_raw(keyword: str, input_file: Path) -> Dict:
    """
    从 raw_data.json 推断传播链。
    这个不是真实转发链，但可以用于后端传播溯源功能演示：
    按同一关键词过滤，再按时间排序，认为最早来源是传播源头。
    """
    if not input_file.exists():
        print(f"[ERROR] 找不到文件：{input_file}")
        return {"platform": "inferred", "root": "", "nodes": [], "edges": []}

    with input_file.open("r", encoding="utf-8") as f:
        records = json.load(f)

    matched = []

    for item in records:
        title = item.get("title", "")
        text = item.get("text", "")
        if keyword in title or keyword in text:
            matched.append(item)

    matched.sort(key=lambda x: parse_time_for_sort(x.get("time", "")))

    nodes: Dict[str, Dict] = {}
    edges: List[Dict] = []

    if not matched:
        return {
            "platform": "inferred",
            "root": "",
            "nodes": [],
            "edges": [],
        }

    root_item = matched[0]
    root_id = f"infer_{root_item.get('id')}"

    for item in matched:
        node_id = f"infer_{item.get('id')}"

        add_node(nodes, {
            "id": node_id,
            "type": "source",
            "platform": item.get("source", "unknown"),
            "user_id": "",
            "user_name": item.get("source", ""),
            "text": item.get("text", ""),
            "time": item.get("time", ""),
            "url": item.get("url", ""),
            "title": item.get("title", ""),
        })

        if node_id != root_id:
            add_edge(
                edges,
                root_id,
                node_id,
                "time_infer",
                item.get("time", ""),
                "inferred",
            )

    return {
        "platform": "inferred",
        "root": root_id,
        "keyword": keyword,
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def save_graph(graph: Dict, output_prefix: str = "propagation_graph"):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    fixed_path = DATA_DIR / f"{output_prefix}.json"
    batch_path = DATA_DIR / f"{output_prefix}_{timestamp}.json"

    with fixed_path.open("w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    with batch_path.open("w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"传播图节点数：{len(graph.get('nodes', []))}")
    print(f"传播图边数：{len(graph.get('edges', []))}")
    print(f"固定输出：{fixed_path}")
    print(f"批次输出：{batch_path}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="传播链 / 传播溯源采集")
    parser.add_argument("--platform", default="weibo", help="平台：weibo 或 inferred")
    parser.add_argument("--url", default="", help="微博帖子 URL 或 mid")
    parser.add_argument("--keyword", default="", help="用于从 raw_data.json 推断传播链的关键词")
    parser.add_argument("--pages", type=int, default=2, help="采集页数")
    parser.add_argument("--input", default=str(DATA_DIR / "raw_data.json"), help="推断传播链输入文件")

    args = parser.parse_args()

    if args.platform == "weibo":
        if not args.url:
            print("[ERROR] platform=weibo 时必须提供 --url")
            return

        graph = crawl_weibo_graph(args.url, max_pages=args.pages)
        save_graph(graph)
        return

    if args.platform == "inferred":
        if not args.keyword:
            print("[ERROR] platform=inferred 时必须提供 --keyword")
            return

        graph = infer_graph_from_raw(args.keyword, Path(args.input))
        save_graph(graph)
        return

    print(f"[ERROR] 暂不支持的平台：{args.platform}")


if __name__ == "__main__":
    main()