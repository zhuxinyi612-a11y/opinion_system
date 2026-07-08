import os
import time
from datetime import date, timedelta
from typing import Dict, List

from dotenv import load_dotenv

from crawler.save_data import make_record


DEFAULT_COLLECTION_IDS = [34412234]
# 34412234 是官方示例里的 US National Collection。
# 先用它保证 MediaCloud 跑通，后面可以换成你自己在 MediaCloud 页面里找到的 collection id。


def parse_collection_ids() -> List[int]:
    """
    从 .env 读取 MEDIACLOUD_COLLECTION_IDS。
    例如：
    MEDIACLOUD_COLLECTION_IDS=34412234
    或：
    MEDIACLOUD_COLLECTION_IDS=34412234,34412118
    """
    raw = os.getenv("MEDIACLOUD_COLLECTION_IDS", "").strip()

    if not raw:
        return DEFAULT_COLLECTION_IDS

    ids = []

    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue

        try:
            ids.append(int(part))
        except ValueError:
            print(f"[WARN] 无效的 MediaCloud collection id：{part}")

    return ids or DEFAULT_COLLECTION_IDS

def parse_source_ids() -> List[int]:
    """
    从 .env 读取 MEDIACLOUD_SOURCE_IDS。
    例如：
    MEDIACLOUD_SOURCE_IDS=12345,67890,11111
    """
    raw = os.getenv("MEDIACLOUD_SOURCE_IDS", "").strip()

    if not raw:
        return []

    ids = []

    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue

        try:
            ids.append(int(part))
        except ValueError:
            print(f"[WARN] 无效的 MediaCloud source id：{part}")

    return ids

def crawl(keyword: str, max_pages: int = 1) -> List[Dict]:
    """
    MediaCloud 新闻归档采集。
    输出统一格式：
    id/title/text/time/source/url
    """

    load_dotenv()

    api_key = os.getenv("MEDIACLOUD_API_KEY", "").strip()

    if not api_key:
        print("[WARN] 没有找到 MEDIACLOUD_API_KEY，请检查 .env")
        return []

    try:
        import mediacloud.api
    except Exception as e:
        print(f"[WARN] 没有正确安装 mediacloud：{e}")
        print("[WARN] 请运行：pip install mediacloud")
        return []

    collection_ids = parse_collection_ids()
    source_ids = parse_source_ids()

    print(f"[INFO] MediaCloud collection_ids={collection_ids}")
    print(f"[INFO] MediaCloud source_ids={source_ids}")

    # 如果配置了 source_ids，就优先用 source_ids
    # 因为中文媒体最好按具体媒体源搜
    if source_ids:
        collection_ids = []

    try:
        mc_search = mediacloud.api.SearchApi(api_key)
    except Exception as e:
        print(f"[WARN] MediaCloud 初始化失败：{e}")
        return []

    records = []

    days = int(os.getenv("MEDIACLOUD_DAYS", "365"))
    start_date = date.today() - timedelta(days=days)
    end_date = date.today()

    print(f"[INFO] MediaCloud date range: {start_date} -> {end_date}")

    pagination_token = None
    safe_pages = min(max_pages, 3)

    for page_index in range(1, safe_pages + 1):
        try:
            page, pagination_token = mc_search.story_list(
                keyword,
                start_date=start_date,
                end_date=end_date,
                collection_ids=collection_ids,
                source_ids=source_ids,
                pagination_token=pagination_token,
            )
        except TypeError:
            try:
                page, pagination_token = mc_search.story_list(
                    keyword,
                    start_date,
                    end_date,
                    collection_ids=collection_ids,
                    source_ids=source_ids,
                    pagination_token=pagination_token,
                )
            except Exception as e:
                print(f"[WARN] MediaCloud 请求失败：{e}")
                break
        except Exception as e:
            print(f"[WARN] MediaCloud 请求失败：{e}")
            break

        print(f"[INFO] MediaCloud keyword='{keyword}' page={page_index} 获取 {len(page)} 条")

        if not page:
            break

        for item in page:
            title = item.get("title") or item.get("name") or ""

            url = (
                item.get("url")
                or item.get("canonical_url")
                or item.get("guid")
                or ""
            )

            publish_time = (
                item.get("publish_date")
                or item.get("published_date")
                or item.get("date")
                or item.get("collect_date")
                or ""
            )

            media_name = (
                item.get("media_name")
                or item.get("source_name")
                or item.get("media", {}).get("name", "")
                or "MediaCloud"
            )

            text = (
                item.get("description")
                or item.get("text")
                or item.get("content")
                or title
            )

            record = make_record(
                title=title,
                text=text,
                source=f"MediaCloud-{media_name}",
                time_value=str(publish_time),
                url=str(url),
            )

            records.append(record)

        if not pagination_token:
            break

        time.sleep(1.5)

    return records