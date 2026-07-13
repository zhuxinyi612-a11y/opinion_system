"""
微博真实转发链采集：
从 m.weibo.cn 搜索接口中读取 mblog 数据，
如果 mblog 中存在 retweeted_status，就构造真实 parent_node_id 和真实转发边。

输出：
data/real_propagation_graph.json
data/real_propagation_edges.json
data/real_propagation_nodes.json

注意：
1. 这不是 time_infer 推断图
2. 边来自微博 retweeted_status 字段
3. is_inferred=false
"""

import argparse
import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from crawler.config import DATA_DIR


SEARCH_API = "https://m.weibo.cn/api/container/getIndex"


def strip_html(text: str) -> str:
    text = text or ""
    text = BeautifulSoup(text, "lxml").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def get_headers(keyword: str = "食品安全") -> Dict[str, str]:
    load_dotenv()

    cookie = os.getenv("WEIBO_COOKIE", "").strip()
    xsrf_token = os.getenv("WEIBO_XSRF_TOKEN", "").strip()

    encoded_keyword = quote(keyword)
    referer = (
        "https://m.weibo.cn/search?"
        f"containerid=100103type%3D1%26q%3D{encoded_keyword}"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": referer,
        "X-Requested-With": "XMLHttpRequest",
        "MWeibo-Pwa": "1",
        "Connection": "keep-alive",
    }

    if cookie:
        headers["Cookie"] = cookie
        print(f"[INFO] WEIBO_COOKIE 已读取，长度={len(cookie)}")

    if xsrf_token:
        headers["X-XSRF-TOKEN"] = xsrf_token
        print(f"[INFO] 已添加 X-XSRF-TOKEN：{xsrf_token}")
    else:
        m = re.search(r"XSRF-TOKEN=([^;]+)", cookie)
        if m:
            headers["X-XSRF-TOKEN"] = m.group(1)
            print("[INFO] 已从 Cookie 中添加 X-XSRF-TOKEN")

    return headers



def safe_get_json(url: str, params: Dict[str, Any], keyword: str = "食品安全") -> Dict:
    headers = get_headers(keyword)

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=20)
    except Exception as e:
        print(f"[WARN] 微博请求异常：{e}")
        return {}

    print(f"[DEBUG] 微博状态码：{resp.status_code}")
    print(f"[DEBUG] Content-Type：{resp.headers.get('Content-Type', '')}")
    print(f"[DEBUG] 实际请求URL：{resp.url}")
    print(f"[DEBUG] 返回前300字符：{resp.text[:300]}")

    if resp.status_code != 200:
        print(f"[WARN] 微博 HTTP {resp.status_code}: {resp.url}")
        return {}

    try:
        payload = resp.json()
    except Exception:
        print("[WARN] 微博返回的不是 JSON，可能被风控或需要重新登录")
        return {}

    if payload.get("ok") == -100:
        print("[WARN] 微博返回 ok=-100，表示当前会话需要登录或被风控")
        print("[WARN] 建议：暂停几分钟，重新从浏览器 getIndex 请求复制最新 X-XSRF-TOKEN / Cookie")
        return {}

    return payload


def get_mblog_id(mblog: Dict) -> str:
    return str(
        mblog.get("mid")
        or mblog.get("id")
        or mblog.get("idstr")
        or ""
    )


def get_user_info(mblog: Dict) -> Dict:
    user = mblog.get("user") or {}

    return {
        "user_id": str(user.get("id") or ""),
        "user_name": user.get("screen_name") or "",
    }


def make_node_id(mid: str) -> str:
    return f"weibo_{mid}"


def add_mblog_recursive(
    mblog: Dict,
    nodes: Dict[str, Dict],
    edges: Dict[str, Dict],
    keyword: str,
    depth: int = 0,
) -> str:
    """
    递归添加微博节点。
    如果该微博转发了别人的微博，则 retweeted_status 就是真实父节点。
    """

    if not isinstance(mblog, dict):
        return ""

    mid = get_mblog_id(mblog)

    if not mid:
        return ""

    node_id = make_node_id(mid)

    retweeted = mblog.get("retweeted_status")
    parent_node_id = ""

    # 如果存在 retweeted_status，先递归加入父节点
    if isinstance(retweeted, dict):
        parent_mid = get_mblog_id(retweeted)

        if parent_mid:
            parent_node_id = add_mblog_recursive(
                retweeted,
                nodes=nodes,
                edges=edges,
                keyword=keyword,
                depth=depth + 1,
            )

    user_info = get_user_info(mblog)

    text = (
        mblog.get("text_raw")
        or mblog.get("text")
        or mblog.get("longText", {}).get("longTextContent")
        or ""
    )

    text = strip_html(text)

    created_at = str(mblog.get("created_at") or "")
    reposts_count = int(mblog.get("reposts_count") or 0)
    comments_count = int(mblog.get("comments_count") or 0)
    attitudes_count = int(mblog.get("attitudes_count") or 0)

    node = {
        "id": node_id,
        "platform": "weibo",
        "post_id": mid,
        "parent_node_id": parent_node_id,
        "is_repost": bool(parent_node_id),
        "is_inferred": False,
        "keyword": keyword,
        "user_id": user_info["user_id"],
        "user_name": user_info["user_name"],
        "text": text,
        "time": created_at,
        "url": f"https://m.weibo.cn/status/{mid}",
        "reposts_count": reposts_count,
        "comments_count": comments_count,
        "attitudes_count": attitudes_count,
        "depth": depth,
    }

    # 已存在也更新一下 parent_node_id，避免之前空节点覆盖真实关系
    if node_id not in nodes:
        nodes[node_id] = node
    else:
        old = nodes[node_id]
        if parent_node_id and not old.get("parent_node_id"):
            old["parent_node_id"] = parent_node_id
            old["is_repost"] = True
        if text and not old.get("text"):
            old["text"] = text

    # 添加真实转发边：父微博 -> 当前微博
    if parent_node_id and parent_node_id != node_id:
        edge_id = f"{parent_node_id}__{node_id}"

        edges[edge_id] = {
            "id": edge_id,
            "source": parent_node_id,
            "target": node_id,
            "source_post_id": parent_node_id.replace("weibo_", ""),
            "target_post_id": mid,
            "type": "weibo_retweeted_status",
            "relation": "retweeted_status",
            "platform": "weibo",
            "keyword": keyword,
            "time": created_at,
            "is_inferred": False,
        }

    return node_id


def iter_mblogs_from_cards(cards: List[Dict]):
    """
    微博接口返回 cards，里面可能直接有 mblog，
    也可能在 card_group 里嵌套。
    """

    for card in cards or []:
        if not isinstance(card, dict):
            continue

        mblog = card.get("mblog")

        if isinstance(mblog, dict):
            yield mblog

        card_group = card.get("card_group")

        if isinstance(card_group, list):
            for sub_mblog in iter_mblogs_from_cards(card_group):
                yield sub_mblog


def crawl_weibo_search_real_graph(
    keyword: str,
    pages: int,
    nodes: Dict[str, Dict],
    edges: Dict[str, Dict],
):
    """
    用 m.weibo.cn 搜索接口抓微博 mblog。
    mblog 中如果存在 retweeted_status，就可以得到真实父子关系。
    """

    for page in range(1, pages + 1):
        params = {
            "containerid": f"100103type=1&q={keyword}",
            "page_type": "searchall",
            "page": page,
        }

        payload = safe_get_json(SEARCH_API, params=params, keyword=keyword)

        data = payload.get("data") or {}
        cards = data.get("cards") or []

        mblogs = list(iter_mblogs_from_cards(cards))

        print(f"[INFO] 微博真实链 keyword='{keyword}' page={page} 获取 mblog={len(mblogs)} 条")

        retweeted_count = sum(
            1 for m in mblogs
            if isinstance(m.get("retweeted_status"), dict)
        )

        repost_count_gt0 = sum(
            1 for m in mblogs
            if int(m.get("reposts_count") or 0) > 0
        )

        print(
            f"[DEBUG] page={page} reposts_count>0 的微博={repost_count_gt0} 条，"
            f"包含 retweeted_status 的微博={retweeted_count} 条"
        )

        if not mblogs:
            break

        before_edges = len(edges)

        for mblog in mblogs:
            add_mblog_recursive(
                mblog,
                nodes=nodes,
                edges=edges,
                keyword=keyword,
                depth=0,
            )

        new_edges = len(edges) - before_edges
        print(f"[INFO] keyword='{keyword}' page={page} 新增真实转发边 {new_edges} 条")

        time.sleep(random.uniform(15, 25))


def save_outputs(nodes: Dict[str, Dict], edges: Dict[str, Dict], keywords: List[str]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    node_list = list(nodes.values())
    edge_list = list(edges.values())

    graph_path = DATA_DIR / "real_propagation_graph.json"
    nodes_path = DATA_DIR / "real_propagation_nodes.json"
    edges_path = DATA_DIR / "real_propagation_edges.json"

    # 防止风控时 0 节点结果覆盖之前的有效真实传播图
    if len(node_list) == 0 and graph_path.exists():
        print("=" * 60)
        print("[WARN] 本次真实微博传播图节点数为 0，疑似 Cookie 失效或风控")
        print("[WARN] 为避免覆盖之前的有效 real_propagation_graph.json，本次跳过写入")
        print(f"[INFO] 保留旧文件：{graph_path}")
        print("=" * 60)
        return

    graph = {
        "graph_type": "real",
        "platform": "weibo",
        "relation_source": "retweeted_status",
        "is_inferred": False,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "keywords": keywords,
        "node_count": len(node_list),
        "edge_count": len(edge_list),
        "nodes": node_list,
        "edges": edge_list,
        "description": "真实传播图：边来自微博 mblog.retweeted_status 字段，不是时间推断。",
    }


    with graph_path.open("w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    with nodes_path.open("w", encoding="utf-8") as f:
        json.dump(node_list, f, ensure_ascii=False, indent=2)

    with edges_path.open("w", encoding="utf-8") as f:
        json.dump(edge_list, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("真实微博传播图生成完成")
    print(f"节点数：{len(node_list)}")
    print(f"真实边数：{len(edge_list)}")
    print(f"图文件：{graph_path}")
    print(f"节点文件：{nodes_path}")
    print(f"边文件：{edges_path}")
    print("=" * 60)

    if len(edge_list) == 0:
        print("[WARN] 没有采到真实转发边。可能原因：")
        print("1. 当前关键词下搜索结果大多是原创微博")
        print("2. 微博接口没有返回 retweeted_status")
        print("3. Cookie 权限不足或被风控")
        print("4. 需要换更容易出现转发的关键词，比如 官方通报、辟谣、网暴、食品安全")


def main():
    parser = argparse.ArgumentParser(description="采集微博真实转发传播图")
    parser.add_argument(
        "--keywords",
        nargs="+",
        required=True,
        help="关键词列表，例如 食品安全 官方通报 辟谣",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=3,
        help="每个关键词搜索页数，建议 1-3",
    )

    args = parser.parse_args()

    nodes: Dict[str, Dict] = {}
    edges: Dict[str, Dict] = {}

    safe_pages = min(args.pages, 3)

    print("=" * 60)
    print("开始采集微博真实转发链")
    print(f"关键词：{args.keywords}")
    print(f"页数：{safe_pages}")
    print("=" * 60)

    for keyword in args.keywords:
        crawl_weibo_search_real_graph(
            keyword=keyword,
            pages=safe_pages,
            nodes=nodes,
            edges=edges,
        )

    save_outputs(nodes, edges, args.keywords)


if __name__ == "__main__":
    main()