import os
import time
from datetime import datetime, timedelta
from typing import List, Dict

import requests
from dotenv import load_dotenv

from crawler.save_data import make_record


NEWSAPI_URL = "https://newsapi.org/v2/everything"


def crawl(keyword: str, max_pages: int = 1) -> List[Dict]:
    """
    NewsAPI 新闻采集。
    输出字段统一为：
    id/title/text/time/source/url

    注意：
    - NewsAPI 免费版每天 100 次请求。
    - 每个 page 算 1 次请求。
    - pageSize 最大 100。
    """

    load_dotenv()

    api_key = os.getenv("NEWSAPI_KEY", "").strip()
    if not api_key:
        print("[WARN] 没有找到 NEWSAPI_KEY，请检查项目根目录下的 .env 文件")
        return []

    records = []

    # 免费版最多搜一个月内数据，所以这里取最近 29 天更稳
    from_date = (datetime.utcnow() - timedelta(days=29)).strftime("%Y-%m-%d")

    # NewsAPI pageSize 最大 100
    page_size = 100

    # 防止一不小心把每天 100 次请求额度用光
    safe_pages = min(max_pages, 5)

    for page in range(1, safe_pages + 1):
        params = {
            "q": keyword,
            "language": "zh",
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "page": page,
            "from": from_date,
        }

        headers = {
            "X-Api-Key": api_key,
            "User-Agent": "Mozilla/5.0",
        }

        try:
            resp = requests.get(
                NEWSAPI_URL,
                params=params,
                headers=headers,
                timeout=20,
            )
        except Exception as e:
            print(f"[WARN] NewsAPI 请求异常：{e}")
            break

        if resp.status_code != 200:
            print(f"[WARN] NewsAPI HTTP {resp.status_code}: {resp.text[:300]}")
            break

        try:
            data = resp.json()
        except Exception:
            print("[WARN] NewsAPI 返回内容不是 JSON")
            break

        if data.get("status") != "ok":
            print(f"[WARN] NewsAPI 返回错误：{data}")
            break

        articles = data.get("articles", [])
        print(f"[INFO] NewsAPI keyword='{keyword}' page={page} 获取 {len(articles)} 条")

        if not articles:
            break

        for item in articles:
            source_obj = item.get("source") or {}
            source_name = source_obj.get("name") or "NewsAPI"

            title = item.get("title") or ""
            description = item.get("description") or ""
            content = item.get("content") or ""

            text = " ".join([description, content]).strip()

            record = make_record(
                title=title,
                text=text,
                source=f"NewsAPI-{source_name}",
                time_value=item.get("publishedAt") or "",
                url=item.get("url") or "",
            )

            records.append(record)

        # 不足 100 条说明后面大概率没了
        if len(articles) < page_size:
            break

        time.sleep(1.5)

    return records