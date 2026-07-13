"""
微博采集：先抓 s.weibo.com 公开搜索页；失败或结果太少时，自动使用公开搜索索引兜底。
"""
from typing import Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .http_client import safe_get
from .save_data import make_record, clean_text
from .search_fallback import crawl_site_search

WEIBO_SEARCH_URL = "https://s.weibo.com/weibo"


def _crawl_search_page(keyword: str, max_pages: int) -> List[Dict]:
    records: List[Dict] = []
    headers = {
        "Referer": "https://s.weibo.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    for page in range(1, max_pages + 1):
        resp = safe_get(WEIBO_SEARCH_URL, params={"q": keyword, "page": page}, platform="weibo", headers=headers)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("div.card-wrap[action-type='feed_list_item']")
        if not cards and page == 1:
            text_hint = clean_text(soup.get_text(" "))[:120]
            print(f"[WARN] 微博没有解析到内容，可能需要 Cookie。页面提示：{text_hint}")
        for card in cards:
            content_node = card.select_one("p.txt[node-type='feed_list_content_full']") or card.select_one("p.txt[node-type='feed_list_content']") or card.select_one("p.txt")
            text = clean_text(content_node.get_text(" ")) if content_node else ""
            if not text:
                continue
            from_node = card.select_one("div.from a")
            time_value = clean_text(from_node.get_text(" ")) if from_node else ""
            href = from_node.get("href", "") if from_node else ""
            if href.startswith("//"):
                url = "https:" + href
            elif href.startswith("/"):
                url = urljoin("https://weibo.com", href)
            else:
                url = href
            name_node = card.select_one("a.name")
            username = clean_text(name_node.get_text(" ")) if name_node else ""
            records.append(make_record(title=text[:50], text=text, source=f"微博-{username}" if username else "微博", time_value=time_value, url=url))
    return records


def crawl(keyword: str, max_pages: int = 3) -> List[Dict]:
    records = _crawl_search_page(keyword, max_pages=max_pages)
    if len(records) < 5:
        print("[INFO] 微博站内数据较少，启用公开搜索索引兜底。")
        records.extend(crawl_site_search(keyword, platform_name="微博", domains=["weibo.com", "m.weibo.cn", "s.weibo.com"], max_pages=max_pages))
    return records
