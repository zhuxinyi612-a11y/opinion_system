"""
小红书方向采集。
不破解站内签名，不绕验证码；使用公开搜索索引做线索级采集。
"""
from typing import Dict, List

from .search_fallback import crawl_site_search


def crawl(keyword: str, max_pages: int = 3) -> List[Dict]:
    records = crawl_site_search(keyword, platform_name="小红书", domains=["xiaohongshu.com", "www.xiaohongshu.com"], max_pages=max_pages)
    if not records:
        print("[WARN] 小红书方向没有解析到搜索结果，可能是搜索引擎限制。")
    return records
