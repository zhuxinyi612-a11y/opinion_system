import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from crawler.config import DATA_DIR
from crawler.propagation_crawler import parse_time_for_sort


DEFAULT_KEYWORDS = [
    "食品安全", "交通事故", "火灾", "爆炸", "校园安全",
    "校园欺凌", "医疗", "医保", "就业", "招聘",
    "诈骗", "网络诈骗", "网络谣言", "消费维权", "退费难",
    "直播带货", "暴雨", "台风", "烂尾楼", "物业纠纷",
    "快递丢件", "个人信息保护", "AI造谣", "数据安全"
]


def load_records(input_file: Path) -> List[Dict]:
    if not input_file.exists():
        print(f"[ERROR] 找不到输入文件：{input_file}")
        return []

    with input_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("[ERROR] raw_data.json 格式错误，应该是列表")
        return []

    return data


def match_keyword(item: Dict, keyword: str) -> bool:
    title = str(item.get("title", "") or "")
    text = str(item.get("text", "") or "")
    source = str(item.get("source", "") or "")
    url = str(item.get("url", "") or "")

    content = title + "\n" + text + "\n" + source + "\n" + url
    return keyword in content


def short_text(text: str, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def classify_platform(source: str, url: str) -> str:
    source_lower = str(source or "").lower()
    url_lower = str(url or "").lower()

    if "weibo" in source_lower or "weibo" in url_lower:
        return "weibo"
    if "toutiao" in source_lower or "toutiao" in url_lower:
        return "toutiao"
    if "bilibili" in source_lower or "bilibili" in url_lower:
        return "bilibili"
    if "zhihu" in source_lower or "zhihu" in url_lower:
        return "zhihu"
    if "mediacloud" in source_lower:
        return "mediacloud"
    if "newsapi" in source_lower:
        return "newsapi"
    if "currents" in source_lower:
        return "currents"
    if "rss" in source_lower:
        return "rss"

    return "unknown"


def infer_sentiment(text: str) -> str:
    text = str(text or "")

    negative_words = [
        "投诉", "质疑", "通报", "调查", "违法", "事故", "诈骗",
        "暴雷", "失联", "死亡", "受伤", "退费难", "拒绝",
        "曝光", "问题", "风险", "隐患", "维权", "造谣",
        "网暴", "泄露", "起火", "爆炸"
    ]

    positive_words = [
        "辟谣", "解决", "整改", "已处理", "救援", "恢复",
        "保障", "成功", "获救", "澄清", "回应"
    ]

    neg = sum(1 for w in negative_words if w in text)
    pos = sum(1 for w in positive_words if w in text)

    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def build_interactions(keyword: str, records: List[Dict], max_items: int = 150) -> List[Dict]:
    matched = [r for r in records if match_keyword(r, keyword)]
    matched.sort(key=lambda x: parse_time_for_sort(x.get("time", "")))

    if max_items > 0:
        matched = matched[:max_items]

    if not matched:
        return []

    root = matched[0]
    root_id = str(root.get("id", "root"))

    interactions = []

    for index, item in enumerate(matched):
        raw_id = str(item.get("id", index))
        source = str(item.get("source", "") or "")
        url = str(item.get("url", "") or "")
        platform = classify_platform(source, url)

        title = short_text(item.get("title", ""), 100)
        text = short_text(item.get("text", ""), 260)

        if not text:
            text = title

        if index == 0:
            interaction_type = "root_event"
            parent_id = ""
        elif platform == "weibo":
            interaction_type = "weibo_discussion"
            parent_id = root_id
        elif platform == "toutiao":
            interaction_type = "toutiao_followup"
            parent_id = root_id
        elif platform in ("newsapi", "mediacloud", "currents", "rss"):
            interaction_type = "media_followup"
            parent_id = root_id
        elif platform == "bilibili":
            interaction_type = "video_discussion"
            parent_id = root_id
        else:
            interaction_type = "related_discussion"
            parent_id = root_id

        interactions.append(
            {
                "id": f"infer_interaction_{keyword}_{raw_id}",
                "root_id": root_id,
                "parent_id": parent_id,
                "keyword": keyword,
                "platform": platform,
                "source": source,
                "type": interaction_type,
                "user_id": "",
                "user_name": source,
                "title": title,
                "text": text,
                "sentiment": infer_sentiment(title + " " + text),
                "time": str(item.get("time", "") or ""),
                "url": url,
                "raw_id": raw_id,
                "is_inferred": True,
                "order": index + 1,
            }
        )

    return interactions


def dedup(records: List[Dict]) -> List[Dict]:
    seen = set()
    output = []

    for item in records:
        key = (item.get("keyword"), item.get("raw_id"), item.get("type"))

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
    stats_path = DATA_DIR / "interactions_stats.json"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    with jsonl_path.open("w", encoding="utf-8") as f:
        for item in records:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    fieldnames = [
        "id", "root_id", "parent_id", "keyword", "platform",
        "source", "type", "user_id", "user_name", "title",
        "text", "sentiment", "time", "url", "raw_id",
        "is_inferred", "order"
    ]

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for item in records:
            writer.writerow({key: item.get(key, "") for key in fieldnames})

    stats = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(records),
        "by_keyword": Counter(item.get("keyword", "") for item in records).most_common(),
        "by_platform": Counter(item.get("platform", "") for item in records).most_common(),
        "by_type": Counter(item.get("type", "") for item in records).most_common(),
        "by_sentiment": Counter(item.get("sentiment", "") for item in records).most_common(),
        "description": "该互动数据由 raw_data.json 推断生成，is_inferred=true 表示不是真实评论/转发。",
    }

    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"推断互动数据数量：{len(records)}")
    print(f"JSON ：{json_path}")
    print(f"JSONL：{jsonl_path}")
    print(f"CSV  ：{csv_path}")
    print(f"统计 ：{stats_path}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="从 raw_data.json 生成推断互动数据")
    parser.add_argument("--keywords", nargs="*", default=DEFAULT_KEYWORDS)
    parser.add_argument("--input", default=str(DATA_DIR / "raw_data.json"))
    parser.add_argument("--max-items", type=int, default=150)

    args = parser.parse_args()

    input_file = Path(args.input)
    records = load_records(input_file)

    if not records:
        return

    all_interactions: List[Dict] = []

    print("=" * 60)
    print("开始生成推断互动数据")
    print(f"原始数据：{len(records)} 条")
    print(f"关键词数：{len(args.keywords)}")
    print("=" * 60)

    for keyword in args.keywords:
        batch = build_interactions(keyword, records, max_items=args.max_items)
        print(f"[INFO] {keyword}: 生成 {len(batch)} 条推断互动")
        all_interactions.extend(batch)

    all_interactions = dedup(all_interactions)

    save_outputs(all_interactions)


if __name__ == "__main__":
    main()