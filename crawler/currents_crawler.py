import os
import time
from typing import Dict, List

import requests
from dotenv import load_dotenv

from crawler.save_data import make_record


CURRENTS_SEARCH_URL = "https://api.currentsapi.services/v1/search"


def crawl(keyword: str, max_pages: int = 1) -> List[Dict]:
    """
    Currents API 新闻采集。
    输出统一格式：
    id/title/text/time/source/url
    """

    load_dotenv()

    api_key = os.getenv("CURRENTS_API_KEY", "").strip()
    if not api_key:
        print("[WARN] 没有找到 CURRENTS_API_KEY，请检查 .env")
        return []

    records = []

    # Currents 文档说 page_size 可到 20
    page_size = 20

    # 防止一次跑太多
    safe_pages = min(max_pages, 5)

    for page in range(1, safe_pages + 1):
        params = {
            "keywords": keyword,
            "language": "zh",
            "page_number": page,
            "page_size": page_size,
            "apiKey": api_key,
        }

        try:
            resp = requests.get(
                CURRENTS_SEARCH_URL,
                params=params,
                timeout=20,
            )
        except Exception as e:
            print(f"[WARN] Currents 请求异常：{e}")
            break

        if resp.status_code != 200:
            print(f"[WARN] Currents HTTP {resp.status_code}: {resp.text[:300]}")
            break

        try:
            data = resp.json()
        except Exception:
            print("[WARN] Currents 返回内容不是 JSON")
            break

        if data.get("status") != "ok":
            print(f"[WARN] Currents 返回错误：{data}")
            break

        news_list = data.get("news", [])
        print(f"[INFO] Currents keyword='{keyword}' page={page} 获取 {len(news_list)} 条")

        if not news_list:
            break

        for item in news_list:
            title = item.get("title") or ""
            description = item.get("description") or ""

            source = item.get("author") or "Currents"
            published = item.get("published") or ""

            record = make_record(
                title=title,
                text=description,
                source=f"Currents-{source}",
                time_value=published,
                url=item.get("url") or "",
            )

            records.append(record)

        if len(news_list) < page_size:
            break

        time.sleep(1.5)

    return records