import re
import time
import urllib.parse
from typing import Dict, List, Tuple

import feedparser
import requests

from crawler.save_data import make_record


TARGET_SITES: List[Tuple[str, str]] = [
    ("人民网", "people.com.cn"),
    ("央视网", "cctv.com"),
    ("央视新闻", "news.cctv.com"),
    ("中国新闻网", "chinanews.com.cn"),
    ("澎湃新闻", "thepaper.cn"),
    ("腾讯新闻", "qq.com"),
    ("新浪新闻", "sina.com.cn"),
    ("网易新闻", "163.com"),
    ("环球网", "huanqiu.com"),
    ("中国青年网", "youth.cn"),
    ("光明网", "gmw.cn"),
    ("中国网", "china.com.cn"),
]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


def clean_html(text: str) -> str:
    text = re.sub(r"<.*?>", " ", text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_rss(url: str, source_name: str) -> List[Dict]:
    records = []

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except Exception as e:
        print(f"[WARN] RSS 请求失败：{source_name} {e}")
        return []

    if resp.status_code != 200:
        print(f"[WARN] RSS HTTP {resp.status_code}：{source_name}")
        return []

    feed = feedparser.parse(resp.content)
    entries = getattr(feed, "entries", []) or []

    for item in entries:
        title = clean_html(item.get("title", ""))
        summary = clean_html(
            item.get("summary", "")
            or item.get("description", "")
            or title
        )
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


def google_news_rss(query: str) -> str:
    q = urllib.parse.quote(query)
    return (
        f"https://news.google.com/rss/search?"
        f"q={q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    )


def bing_news_rss(query: str) -> str:
    q = urllib.parse.quote(query)
    return f"https://www.bing.com/news/search?q={q}&format=rss&cc=cn"


def crawl_one_site(keyword: str, media_name: str, domain: str) -> List[Dict]:
    """
    一个媒体站点的多重兜底搜索：
    1. Google News: site:domain keyword
    2. Google News: media_name keyword
    3. Bing News: media_name keyword
    """

    records = []

    queries = [
        (
            f"{media_name}-Google站内索引",
            google_news_rss(f"site:{domain} {keyword}"),
        ),
        (
            f"{media_name}-Google媒体索引",
            google_news_rss(f"{media_name} {keyword}"),
        ),
        (
            f"{media_name}-Bing媒体索引",
            bing_news_rss(f"{media_name} {keyword}"),
        ),
    ]

    for source_name, url in queries:
        batch = fetch_rss(url, source_name)
        print(f"[INFO] {source_name} keyword='{keyword}' 获取 {len(batch)} 条")

        records.extend(batch)

        # 如果已经拿到数据，就不用继续对同一个媒体兜底太多
        if len(records) >= 10:
            break

        time.sleep(0.8)

    return records


def crawl(keyword: str, max_pages: int = 1) -> List[Dict]:
    """
    指定媒体新闻采集。

    max_pages 在这里表示搜索强度：
    - 1：搜前 6 个媒体
    - 2：搜前 10 个媒体
    - 3 及以上：搜全部媒体
    """

    if max_pages <= 1:
        sites = TARGET_SITES[:6]
    elif max_pages == 2:
        sites = TARGET_SITES[:10]
    else:
        sites = TARGET_SITES

    records = []

    for media_name, domain in sites:
        batch = crawl_one_site(keyword, media_name, domain)
        records.extend(batch)
        time.sleep(1.2)

    return records