"""
知乎采集：先尝试知乎公开搜索 API；失败或结果太少时，自动使用公开搜索索引兜底。
"""
from typing import Any, Dict, List

from .http_client import safe_get
from .save_data import make_record, clean_text
from .search_fallback import crawl_site_search

ZHIHU_SEARCH_API = "https://www.zhihu.com/api/v4/search_v3"


def extract_zhihu_item(obj: Dict[str, Any]) -> Dict[str, str]:
    obj_type = obj.get("type", "")
    title = ""
    text = ""
    url = ""
    time_value = obj.get("created_time") or obj.get("updated_time") or ""

    if obj_type == "answer":
        question = obj.get("question") or {}
        title = question.get("name") or question.get("title") or "知乎回答"
        text = obj.get("excerpt") or obj.get("content") or title
        url = obj.get("url") or question.get("url") or ""
        if "/api/v4/answers/" in url:
            answer_id = url.rstrip("/").split("/")[-1]
            qid = str(question.get("id", ""))
            if qid:
                url = f"https://www.zhihu.com/question/{qid}/answer/{answer_id}"
    elif obj_type == "article":
        title = obj.get("title") or "知乎文章"
        text = obj.get("excerpt") or obj.get("content") or title
        url = obj.get("url") or ""
        if "/api/v4/articles/" in url:
            article_id = url.rstrip("/").split("/")[-1]
            url = f"https://zhuanlan.zhihu.com/p/{article_id}"
    elif obj_type == "question":
        title = obj.get("name") or obj.get("title") or "知乎问题"
        text = obj.get("excerpt") or title
        qid = obj.get("id", "")
        url = f"https://www.zhihu.com/question/{qid}" if qid else obj.get("url", "")
    else:
        title = obj.get("title") or obj.get("name") or obj.get("excerpt") or "知乎内容"
        text = obj.get("excerpt") or obj.get("content") or title
        url = obj.get("url") or ""

    return {"title": clean_text(title), "text": clean_text(text), "url": clean_text(url), "time": time_value}


def _crawl_api(keyword: str, max_pages: int) -> List[Dict]:
    records: List[Dict] = []
    headers = {
        "Referer": "https://www.zhihu.com/search",
        "Accept": "application/json,text/plain,*/*",
        "x-api-version": "3.0.91",
    }
    for page in range(1, max_pages + 1):
        offset = (page - 1) * 20
        params = {"t": "general", "q": keyword, "correction": 1, "offset": offset, "limit": 20}
        resp = safe_get(ZHIHU_SEARCH_API, params=params, platform="zhihu", headers=headers)
        if not resp:
            continue
        try:
            payload = resp.json()
        except Exception:
            print("[WARN] zhihu 返回的不是 JSON，可能需要 Cookie")
            continue
        for item in payload.get("data", []) or []:
            obj = item.get("object") or {}
            extracted = extract_zhihu_item(obj)
            if not extracted["title"] and not extracted["text"]:
                continue
            records.append(make_record(title=extracted["title"], text=extracted["text"], source="知乎", time_value=extracted["time"], url=extracted["url"]))
    return records


def crawl(keyword: str, max_pages: int = 3) -> List[Dict]:
    records = _crawl_api(keyword, max_pages=max_pages)
    if len(records) < 5:
        print("[INFO] 知乎 API 数据较少，启用公开搜索索引兜底。")
        records.extend(crawl_site_search(keyword, platform_name="知乎", domains=["zhihu.com", "zhuanlan.zhihu.com"], max_pages=max_pages))
    return records
