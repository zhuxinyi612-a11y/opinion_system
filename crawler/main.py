"""
统一入口。
运行方式：
  python -m crawler.main --keywords 校园舆情 暴雨灾害 --pages 3
或者：
  python crawler/main.py --keywords 校园舆情 --pages 3
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List

# 兼容 python crawler/main.py 这种运行方式
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawler.config import DATA_DIR, DEFAULT_KEYWORDS, DEFAULT_MAX_PAGES, START_ID
from crawler.save_data import assign_ids, deduplicate, save_csv, save_json, save_jsonl

from crawler.news_crawler import crawl as crawl_news
from crawler.weibo_crawler import crawl as crawl_weibo
from crawler.bilibili_crawler import crawl as crawl_bilibili
from crawler.newsapi_crawler import crawl as crawl_newsapi
from crawler.zhihu_crawler import crawl as crawl_zhihu
from crawler.toutiao_crawler import crawl as crawl_toutiao
from crawler.xiaohongshu_crawler import crawl as crawl_xiaohongshu
from crawler.currents_crawler import crawl as crawl_currents
from crawler.mediacloud_crawler import crawl as crawl_mediacloud
from crawler.rss_news_crawler import crawl as crawl_rssnews
from crawler.site_news_crawler import crawl as crawl_sitenews

CrawlerFunc = Callable[..., List[dict]]

CRAWLERS: Dict[str, CrawlerFunc] = {
    "news": crawl_news,
    "newsapi": crawl_newsapi,
    "currents": crawl_currents,
    "mediacloud": crawl_mediacloud,
    "rssnews": crawl_rssnews,
    "sitenews": crawl_sitenews,
    "weibo": crawl_weibo,
    "bilibili": crawl_bilibili,
    "zhihu": crawl_zhihu,
    "toutiao": crawl_toutiao,
    "xiaohongshu": crawl_xiaohongshu,
}

PLATFORM_CN = {
    "news": "新闻",
    "newsapi": "NewsAPI新闻",
    "currents": "Currents新闻",
    "mediacloud": "MediaCloud新闻",
    "rssnews": "RSS新闻聚合",
    "sitenews": "指定媒体新闻",
    "weibo": "微博",
    "bilibili": "B站",
    "zhihu": "知乎",
    "toutiao": "今日头条",
    "xiaohongshu": "小红书",
}

def load_existing_records(path: Path) -> List[dict]:
    """
    读取已经存在的历史数据。
    如果文件不存在、为空、格式不对，就返回空列表。
    """
    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        print(f"[WARN] 历史文件不是列表格式，已忽略：{path}")
        return []

    except Exception as e:
        print(f"[WARN] 读取历史数据失败，已忽略：{path}，原因：{e}")
        return []

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="网络舆情数据采集统一入口")
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=DEFAULT_KEYWORDS,
        help="关键词，可以写多个，例如：--keywords 校园舆情 暴雨灾害",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help="每个平台每个关键词爬取页数，默认 3",
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        default=list(CRAWLERS.keys()),
        choices=list(CRAWLERS.keys()),
        help="指定平台，例如：--platforms news bilibili zhihu",
    )
    parser.add_argument(
        "--fetch-news-detail",
        action="store_true",
        help="新闻是否进一步进入详情页抓正文。更慢，但 text 更完整。",
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=START_ID,
        help="后端需要的起始 id，默认 10001",
    )
    parser.add_argument(
        "--output-prefix",
        default="raw_data",
        help="输出文件名前缀，默认 raw_data",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="不合并历史数据，只保存本次采集结果。默认会自动合并历史数据。",
    )

    return parser.parse_args()


def run() -> None:
    args = parse_args()
    all_records: List[dict] = []

    print("=" * 60)
    print("网络舆情数据采集开始")
    print(f"关键词：{args.keywords}")
    print(f"平台：{[PLATFORM_CN.get(p, p) for p in args.platforms]}")
    print(f"页数：{args.pages}")
    print("=" * 60)

    for keyword in args.keywords:
        for platform in args.platforms:
            crawler = CRAWLERS[platform]
            print(f"\n[INFO] 正在采集：关键词='{keyword}' 平台={PLATFORM_CN.get(platform, platform)}")
            try:
                if platform == "news":
                    records = crawler(keyword, max_pages=args.pages, fetch_detail=args.fetch_news_detail)
                else:
                    records = crawler(keyword, max_pages=args.pages)
            except Exception as e:
                print(f"[ERROR] {platform} 爬虫运行失败：{e}")
                records = []

            print(f"[INFO] {PLATFORM_CN.get(platform, platform)} 获取 {len(records)} 条")
            all_records.extend(records)

    print("\n[INFO] 正在处理本次采集数据 ...")

    # 1. 本次采集结果先去重
    new_records = deduplicate(all_records)
    new_records = assign_ids(new_records, start_id=args.start_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 2. 保存“本次采集批次”，方便以后追溯
    batch_json_path = DATA_DIR / f"{args.output_prefix}_{timestamp}.json"
    batch_jsonl_path = DATA_DIR / f"{args.output_prefix}_{timestamp}.jsonl"
    batch_csv_path = DATA_DIR / f"{args.output_prefix}_{timestamp}.csv"

    save_json(new_records, batch_json_path)
    save_jsonl(new_records, batch_jsonl_path)
    save_csv(new_records, batch_csv_path)

    # 3. 固定文件名，给后端读取
    fixed_json_path = DATA_DIR / f"{args.output_prefix}.json"
    fixed_csv_path = DATA_DIR / f"{args.output_prefix}.csv"

    # 4. 默认合并历史数据，除非手动加 --reset
    if args.reset:
        print("[INFO] 已启用 --reset，本次不会合并历史数据")
        merged_records = new_records
    else:
        old_records = load_existing_records(fixed_json_path)
        print(f"[INFO] 历史数据：{len(old_records)} 条")
        print(f"[INFO] 本次新增：{len(new_records)} 条")

        merged_records = old_records + new_records
        merged_records = deduplicate(merged_records)
        merged_records = assign_ids(merged_records, start_id=args.start_id)

    # 5. 保存累计总数据，后端固定读这个
    save_json(merged_records, fixed_json_path)
    save_csv(merged_records, fixed_csv_path)

    print("=" * 60)
    print(f"本次采集：{len(new_records)} 条")
    print(f"累计总数：{len(merged_records)} 条")
    print(f"本次批次 JSON ：{batch_json_path}")
    print(f"本次批次 JSONL：{batch_jsonl_path}")
    print(f"本次批次 CSV  ：{batch_csv_path}")
    print(f"后端固定读取文件：{fixed_json_path}")
    print("=" * 60)

    if merged_records:
        print("\n第一条累计数据示例：")
        print(merged_records[0])


if __name__ == "__main__":
    run()
