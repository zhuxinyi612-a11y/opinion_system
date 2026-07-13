import os
import re
import time
import random
import urllib.parse
from typing import Dict, List

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from crawler.save_data import make_record


def get_headers() -> Dict[str, str]:
    load_dotenv()

    cookie = os.getenv("TOUTIAO_COOKIE", "").strip()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.toutiao.com/",
        "Connection": "keep-alive",
    }

    if cookie:
        headers["Cookie"] = cookie

    return headers


def clean_text(text: str) -> str:
    text = re.sub(r"<.*?>", " ", text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_from_html(html: str, keyword: str) -> List[Dict]:
    records = []

    soup = BeautifulSoup(html, "lxml")

    # 方式一：从 a 标签里提取搜索结果
    for a in soup.find_all("a"):
        title = clean_text(a.get_text(" ", strip=True))
        href = a.get("href", "")

        if not title:
            continue

        if keyword not in title and len(title) < 6:
            continue

        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = "https://www.toutiao.com" + href

        if "toutiao.com" not in href and href:
            continue

        records.append(
            make_record(
                title=title,
                text=title,
                source="今日头条",
                time_value="",
                url=href,
            )
        )

    return records


def crawl(keyword: str, max_pages: int = 1) -> List[Dict]:
    """
    今日头条搜索采集。
    说明：
    - 优先使用 .env 里的 TOUTIAO_COOKIE
    - 不破解验证码、不绕签名
    - 如果页面强风控，返回 0 条是正常的
    """

    load_dotenv()

    records = []
    headers = get_headers()

    safe_pages = min(max_pages, int(os.getenv("AUTH_MAX_PAGES", "2")))

    for page in range(1, safe_pages + 1):
        encoded = urllib.parse.quote(keyword)

        # 今日头条搜索页
        url = f"https://www.toutiao.com/search/?keyword={encoded}"

        try:
            resp = requests.get(url, headers=headers, timeout=20)
        except Exception as e:
            print(f"[WARN] 今日头条请求异常：{e}")
            break

        if resp.status_code != 200:
            print(f"[WARN] 今日头条 HTTP {resp.status_code}: {url}")
            break

        html = resp.text or ""

        # 常见风控/登录提示
        if "captcha" in html.lower() or "验证" in html[:1000] or "登录" in html[:1000]:
            print("[WARN] 今日头条可能触发登录/验证/风控，当前页面不适合继续采集")
            break

        batch = extract_from_html(html, keyword)
        print(f"[INFO] 今日头条 keyword='{keyword}' page={page} 解析 {len(batch)} 条")

        records.extend(batch)

        time.sleep(random.uniform(6, 15))

    return records