import time
import urllib.parse
from typing import Dict, List

import feedparser

from crawler.save_data import make_record


def parse_rss(url: str, source_name: str) -> List[Dict]:
    records = []

    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"[WARN] RSS 解析失败：{source_name} {e}")
        return []

    entries = getattr(feed, "entries", []) or []

    for item in entries:
        title = item.get("title", "") or ""
        summary = item.get("summary", "") or item.get("description", "") or title
        link = item.get("link", "") or ""
        published = item.get("published", "") or item.get("updated", "") or ""

        if not title and not summary:
            continue

        record = make_record(
            title=title,
            text=summary,
            source=source_name,
            time_value=published,
            url=link,
        )
        records.append(record)

    return records


def crawl(keyword: str, max_pages: int = 1) -> List[Dict]:
    """
    RSS 新闻聚合源：
    1. Bing News RSS
    2. Google News RSS

    优点：
    - 不需要 Cookie
    - 不需要 API Key
    - 适合作为新闻兜底源
    """

    records = []
    q = urllib.parse.quote(keyword)

    rss_sources = [
        (
            "BingNewsRSS",
            f"https://www.bing.com/news/search?q={q}&format=rss&cc=cn",
        ),
        (
            "GoogleNewsRSS",
            f"https://news.google.com/rss/search?q={q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        ),
    ]

    for source_name, url in rss_sources:
        batch = parse_rss(url, source_name)
        print(f"[INFO] {source_name} keyword='{keyword}' 获取 {len(batch)} 条")
        records.extend(batch)
        time.sleep(1)

    return records