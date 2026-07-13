"""
评论 / 互动数据采集：
从 data/raw_data.json 中筛选微博帖子 URL，
尝试采集评论和转发互动数据，输出：

data/interactions_data.json
data/interactions_data.jsonl
data/interactions_data.csv

用途：
1. 情感分析
2. 观点聚类
3. 评论热度分析
4. 传播溯源补充
"""

import argparse
import csv
import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from crawler.config import DATA_DIR
from crawler.propagation_crawler import (
    parse_weibo_id,
    safe_json_get,
    strip_html,
    parse_weibo_time,
)


def load_raw_records(input_file: Path) -> List[Dict]:
    if not input_file.exists():
        print(f"[ERROR] 找不到输入文件：{input_file}")
        return []

    with input_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("[ERROR] raw_data.json 格式错误，应该是列表")
        return []

    return data


def is_weibo_record(item: Dict) -> bool:
    source = str(item.get("source", "") or "").lower()
    url = str(item.get("url", "") or "").lower()

    return "weibo" in source or "weibo.com" in url or "m.weibo.cn" in url


def match_keyword(item: Dict, keyword: str) -> bool:
    if not keyword:
        return True

    title = str(item.get("title", "") or "")
    text = str(item.get("text", "") or "")

    return keyword in title or keyword in text


def make_interaction_record(
    interaction_type: str,
    root_record: Dict,
    mid: str,
    item: Dict,
) -> Dict:
    user = item.get("user") or {}

    interaction_id = str(item.get("id") or item.get("mid") or "")
    user_id = str(user.get("id") or "")
    user_name = user.get("screen_name") or ""

    text = strip_html(item.get("text") or "")
    time_value = parse_weibo_time(item.get("created_at"))

    if interaction_type == "comment":
        url = f"https://m.weibo.cn/comment/{interaction_id}"
    else:
        url = f"https://m.weibo.cn/status/{interaction_id}"

    return {
        "id": interaction_id,
        "root_id": root_record.get("id", ""),
        "root_mid": mid,
        "root_title": root_record.get("title", ""),
        "root_url": root_record.get("url", ""),
        "platform": "weibo",
        "type": interaction_type,
        "user_id": user_id,
        "user_name": user_name,
        "text": text,
        "time": time_value,
        "url": url,
    }


def crawl_weibo_comments(mid: str, root_record: Dict, pages: int) -> List[Dict]:
    results: List[Dict] = []

    api = "https://m.weibo.cn/comments/hotflow"
    max_id = ""

    for page in range(1, pages + 1):
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

        print(f"[INFO] 评论 mid={mid} page={page} 获取 {len(comments)} 条")

        if not comments:
            break

        for item in comments:
            if not isinstance(item, dict):
                continue

            record = make_interaction_record(
                interaction_type="comment",
                root_record=root_record,
                mid=mid,
                item=item,
            )

            if record.get("id") and record.get("text"):
                results.append(record)

        max_id = str(data.get("max_id") or "")
        if not max_id or max_id == "0":
            break

        time.sleep(random.uniform(4, 8))

    return results


def crawl_weibo_reposts(mid: str, root_record: Dict, pages: int) -> List[Dict]:
    results: List[Dict] = []

    api = "https://m.weibo.cn/api/statuses/repostTimeline"

    for page in range(1, pages + 1):
        payload = safe_json_get(
            api,
            params={"id": mid, "page": page},
            platform="weibo",
        )

        data = payload.get("data") or {}
        reposts = data.get("data") or []

        print(f"[INFO] 转发 mid={mid} page={page} 获取 {len(reposts)} 条")

        if not reposts:
            break

        for item in reposts:
            if not isinstance(item, dict):
                continue

            record = make_interaction_record(
                interaction_type="repost",
                root_record=root_record,
                mid=mid,
                item=item,
            )

            if record.get("id") and record.get("text"):
                results.append(record)

        time.sleep(random.uniform(4, 8))

    return results


def dedup_records(records: List[Dict]) -> List[Dict]:
    seen = set()
    output = []

    for item in records:
        key = (
            item.get("platform"),
            item.get("type"),
            item.get("id"),
            item.get("root_mid"),
        )

        if key in seen:
            continue

        seen.add(key)
        output.append(item)

    return output


def save_outputs(records: List[Dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    json_path = DATA_DIR / "interactions_data.json"
    jsonl_path = DATA_DIR / "interactions_data.jsonl"
    csv_path = DATA_DIR / "interactions_data.csv"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    with jsonl_path.open("w", encoding="utf-8") as f:
        for item in records:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    fieldnames = [
        "id",
        "root_id",
        "root_mid",
        "root_title",
        "root_url",
        "platform",
        "type",
        "user_id",
        "user_name",
        "text",
        "time",
        "url",
    ]

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for item in records:
            writer.writerow({key: item.get(key, "") for key in fieldnames})

    print("=" * 60)
    print(f"互动数据数量：{len(records)}")
    print(f"JSON ：{json_path}")
    print(f"JSONL：{jsonl_path}")
    print(f"CSV  ：{csv_path}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="微博评论/转发互动数据采集")
    parser.add_argument("--keyword", default="", help="只采集包含该关键词的微博原始记录")
    parser.add_argument("--pages", type=int, default=1, help="每条微博采集评论/转发页数")
    parser.add_argument("--max-posts", type=int, default=10, help="最多处理多少条微博原帖")
    parser.add_argument("--input", default=str(DATA_DIR / "raw_data.json"), help="输入 raw_data.json 路径")

    args = parser.parse_args()

    input_file = Path(args.input)
    raw_records = load_raw_records(input_file)

    if not raw_records:
        return

    candidates = []

    for item in raw_records:
        if not is_weibo_record(item):
            continue

        if not match_keyword(item, args.keyword):
            continue

        url = str(item.get("url", "") or "")
        if not url:
            continue

        try:
            mid = parse_weibo_id(url)
        except Exception:
            continue

        candidates.append((mid, item))

    print("=" * 60)
    print("开始采集微博评论/互动数据")
    print(f"关键词：{args.keyword or '不限'}")
    print(f"候选微博数：{len(candidates)}")
    print(f"最多处理：{args.max_posts} 条")
    print("=" * 60)

    all_interactions: List[Dict] = []

    for index, (mid, root_record) in enumerate(candidates[: args.max_posts], start=1):
        print(f"[INFO] 正在处理第 {index}/{min(len(candidates), args.max_posts)} 条微博 mid={mid}")

        comments = crawl_weibo_comments(mid, root_record, pages=args.pages)
        reposts = crawl_weibo_reposts(mid, root_record, pages=args.pages)

        all_interactions.extend(comments)
        all_interactions.extend(reposts)

        time.sleep(random.uniform(6, 12))

    all_interactions = dedup_records(all_interactions)

    save_outputs(all_interactions)


if __name__ == "__main__":
    main()