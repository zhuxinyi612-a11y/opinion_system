"""
今日头条采集：先尝试公开搜索接口；失败或结果太少时，自动使用公开搜索索引兜底。
"""
from typing import Dict, List

from .http_client import safe_get
from .save_data import make_record, clean_text
from .search_fallback import crawl_site_search

TOUTIAO_SEARCH_API = "https://www.toutiao.com/api/search/content/"


def normalize_toutiao_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://www.toutiao.com" + url
    return url


def _crawl_api(keyword: str, max_pages: int) -> List[Dict]:
    records: List[Dict] = []
    headers = {"Referer": "https://www.toutiao.com/search/", "Accept": "application/json,text/plain,*/*"}
    for page in range(1, max_pages + 1):
        offset = (page - 1) * 20
        params = {"aid": 24, "app_name": "web_search", "offset": offset, "format": "json", "keyword": keyword, "count": 20, "from": "search_tab", "pd": "synthesis"}
        resp = safe_get(TOUTIAO_SEARCH_API, params=params, platform="toutiao", headers=headers)
        if not resp:
            continue
        try:
            payload = resp.json()
        except Exception:
            print("[WARN] toutiao 返回的不是 JSON，可能需要 Cookie")
            continue
        for item in payload.get("data", []) or []:
            title = item.get("title") or item.get("display", {}).get("title") or ""
            abstract = item.get("abstract") or item.get("description") or item.get("display", {}).get("summary") or ""
            source = item.get("source") or item.get("media_name") or "今日头条"
            url = item.get("article_url") or item.get("share_url") or item.get("display_url") or item.get("url") or ""
            time_value = item.get("display_time") or item.get("publish_time") or ""
            title = clean_text(title)
            abstract = clean_text(abstract)
            if not title and not abstract:
                continue
            records.append(make_record(title=title or abstract[:50], text=abstract or title, source=source, time_value=time_value, url=normalize_toutiao_url(url)))
    return records


def crawl(keyword: str, max_pages: int = 3) -> List[Dict]:
    records = _crawl_api(keyword, max_pages=max_pages)
    if len(records) < 5:
        print("[INFO] 今日头条 API 数据较少，启用公开搜索索引兜底。")
        records.extend(crawl_site_search(keyword, platform_name="今日头条", domains=["toutiao.com", "www.toutiao.com"], max_pages=max_pages))
    return records
