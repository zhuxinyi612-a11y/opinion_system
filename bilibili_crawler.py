"""B站搜索爬虫：使用公开搜索接口。"""
from typing import List, Dict

from .http_client import safe_get
from .save_data import make_record, clean_text

BILI_SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"


def normalize_bili_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    return url


def crawl(keyword: str, max_pages: int = 3) -> List[Dict]:
    records = []
    headers = {
        "Referer": "https://search.bilibili.com/",
        "Accept": "application/json,text/plain,*/*",
    }

    for page in range(1, max_pages + 1):
        params = {
            "search_type": "video",
            "keyword": keyword,
            "page": page,
        }
        resp = safe_get(BILI_SEARCH_API, params=params, platform="bilibili", headers=headers)
        if not resp:
            continue

        try:
            payload = resp.json()
        except Exception:
            print("[WARN] bilibili 返回的不是 JSON")
            continue

        result = payload.get("data", {}).get("result", []) or []
        for item in result:
            title = clean_text(item.get("title", ""))
            description = clean_text(item.get("description", ""))
            author = clean_text(item.get("author", ""))
            text = description or title
            url = normalize_bili_url(item.get("arcurl", ""))
            pubdate = item.get("pubdate", "")
            source = f"B站-{author}" if author else "B站"

            records.append(
                make_record(
                    title=title,
                    text=text,
                    source=source,
                    time_value=pubdate,
                    url=url,
                )
            )

    return records
