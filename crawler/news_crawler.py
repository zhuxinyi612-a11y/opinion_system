"""
新闻爬虫：使用 GDELT 公开新闻检索接口。
优点：不用登录、不用 Cookie，适合作业演示和批量收集新闻标题/链接。
注意：不同新闻站点正文结构不同，正文抓取不一定每条都成功，失败时 text 会退化为标题。
"""
from typing import List, Dict
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .http_client import safe_get
from .save_data import make_record, clean_text

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def extract_article_text(url: str, max_chars: int = 1500) -> str:
    """尽量从新闻详情页提取正文段落，失败则返回空字符串。"""
    if not url:
        return ""
    resp = safe_get(url, retries=1, timeout=10)
    if not resp:
        return ""
    soup = BeautifulSoup(resp.text, "lxml")

    for bad in soup.select("script,style,noscript,header,footer,nav,aside"):
        bad.extract()

    paragraphs = []
    for p in soup.select("p"):
        t = clean_text(p.get_text(" "))
        if len(t) >= 15:
            paragraphs.append(t)
        if sum(len(x) for x in paragraphs) >= max_chars:
            break

    return clean_text(" ".join(paragraphs))[:max_chars]


def crawl(keyword: str, max_pages: int = 3, fetch_detail: bool = False) -> List[Dict]:
    # GDELT 单次最多适合取几十到几百条；这里用 max_pages 映射数量
    max_records = min(max_pages * 30, 100)
    params = {
        "query": keyword,
        "mode": "ArtList",
        "format": "json",
        "sort": "HybridRel",
        "maxrecords": max_records,
    }
    resp = safe_get(GDELT_DOC_API, params=params, platform="news", headers={"Accept": "application/json"})
    if not resp:
        return []

    try:
        payload = resp.json()
    except Exception:
        print("[WARN] news 返回的不是 JSON")
        return []

    records = []
    for item in payload.get("articles", []):
        title = item.get("title", "")
        url = item.get("url", "")
        domain = item.get("domain") or urlparse(url).netloc
        source_name = item.get("sourceCommonName") or domain or "新闻网站"
        time_value = item.get("seendate", "")

        text = title
        if fetch_detail and url:
            detail_text = extract_article_text(url)
            if detail_text:
                text = detail_text

        records.append(
            make_record(
                title=title,
                text=text,
                source=source_name,
                time_value=time_value,
                url=url,
            )
        )

    return records
