"""
公开搜索兜底采集。

用途：当微博/知乎/头条/小红书站内接口拿不到数据时，使用公开搜索结果做“线索级”采集。
优点：不需要登录 Cookie，适合作业演示和舆情线索发现。
限制：只能拿标题、摘要、链接，拿不到完整评论/点赞/收藏；搜索引擎也可能限流。
"""
from typing import Dict, Iterable, List
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup

from .http_client import safe_get
from .save_data import make_record, clean_text

BING_SEARCH_URL = "https://www.bing.com/search"
DUCK_SEARCH_URL = "https://duckduckgo.com/html/"
BAIDU_SEARCH_URL = "https://www.baidu.com/s"


def _domain_hit(url: str, domains: Iterable[str]) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    raw = url.lower()
    for d in domains:
        d = d.lower().strip()
        if not d:
            continue
        if d in host or d in raw:
            return True
    return False


def _bing(keyword: str, domains: List[str], platform_name: str, max_pages: int) -> List[Dict]:
    records: List[Dict] = []
    domain_query = " OR ".join([f"site:{d}" for d in domains])
    query = f"({domain_query}) {keyword}"
    headers = {"Referer": "https://www.bing.com/"}

    for page in range(1, max_pages + 1):
        first = (page - 1) * 10 + 1
        resp = safe_get(BING_SEARCH_URL, params={"q": query, "first": first}, platform="search", headers=headers, retries=1)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select("li.b_algo"):
            a = item.select_one("h2 a")
            if not a:
                continue
            title = clean_text(a.get_text(" "))
            url = a.get("href", "")
            snippet_node = item.select_one("p")
            snippet = clean_text(snippet_node.get_text(" ")) if snippet_node else title
            if not title or not _domain_hit(url, domains):
                continue
            records.append(make_record(title=title, text=snippet or title, source=f"{platform_name}-搜索索引", time_value="", url=url))
    return records


def _duckduckgo(keyword: str, domains: List[str], platform_name: str, max_pages: int) -> List[Dict]:
    records: List[Dict] = []
    domain_query = " OR ".join([f"site:{d}" for d in domains])
    query = f"({domain_query}) {keyword}"
    headers = {"Referer": "https://duckduckgo.com/"}

    # DuckDuckGo html 翻页不如 Bing 稳，这里用 s 做偏移。
    for page in range(1, max_pages + 1):
        offset = (page - 1) * 30
        resp = safe_get(DUCK_SEARCH_URL, params={"q": query, "s": offset}, platform="search", headers=headers, retries=1)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for item in soup.select(".result"):
            a = item.select_one("a.result__a") or item.select_one("a")
            if not a:
                continue
            title = clean_text(a.get_text(" "))
            url = a.get("href", "")
            snippet_node = item.select_one(".result__snippet")
            snippet = clean_text(snippet_node.get_text(" ")) if snippet_node else title
            if not title or not _domain_hit(url, domains):
                continue
            records.append(make_record(title=title, text=snippet or title, source=f"{platform_name}-搜索索引", time_value="", url=url))
    return records


def _baidu(keyword: str, domains: List[str], platform_name: str, max_pages: int) -> List[Dict]:
    records: List[Dict] = []
    domain_query = " OR ".join([f"site:{d}" for d in domains])
    query = f"({domain_query}) {keyword}"
    headers = {"Referer": "https://www.baidu.com/"}

    for page in range(1, max_pages + 1):
        pn = (page - 1) * 10
        resp = safe_get(BAIDU_SEARCH_URL, params={"wd": query, "pn": pn}, platform="search", headers=headers, retries=1)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        # 百度结构经常变，尽量宽松解析。
        for item in soup.select("div.result, div.c-container"):
            a = item.select_one("h3 a") or item.select_one("a")
            if not a:
                continue
            title = clean_text(a.get_text(" "))
            url = a.get("href", "")
            snippet = clean_text(item.get_text(" "))
            # 百度很多是跳转链接，URL 里不一定直接含目标域名，所以这里 title/snippet 命中也收。
            hit = _domain_hit(url, domains) or any(d.split(".")[0] in (title + snippet).lower() for d in domains)
            if not title or not hit:
                continue
            records.append(make_record(title=title, text=snippet[:300] or title, source=f"{platform_name}-搜索索引", time_value="", url=url))
    return records


def crawl_site_search(keyword: str, platform_name: str, domains: List[str], max_pages: int = 3) -> List[Dict]:
    """多搜索引擎兜底：Bing -> DuckDuckGo -> 百度，最后统一返回。"""
    records: List[Dict] = []
    for func in (_bing, _duckduckgo, _baidu):
        try:
            records.extend(func(keyword, domains, platform_name, max_pages=max_pages))
        except Exception as e:
            print(f"[WARN] {platform_name} 搜索兜底失败：{func.__name__} -> {e}")
    return records
