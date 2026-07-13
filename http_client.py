import os
import random
import time
from typing import Any, Dict, Optional

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from .config import COOKIE_ENV_MAP, DEFAULT_HEADERS, MAX_DELAY, MIN_DELAY, TIMEOUT

SESSION = requests.Session()


def sleep_a_bit(multiplier: float = 1.0) -> None:
    """控制请求速度，避免请求过快。"""
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY) * multiplier)


def get_cookie(platform: Optional[str]) -> str:
    if not platform:
        return ""
    env_name = COOKIE_ENV_MAP.get(platform, "")
    if not env_name:
        return ""
    return os.getenv(env_name, "").strip()


def safe_get(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    platform: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    retries: int = 2,
    timeout: int = TIMEOUT,
) -> Optional[requests.Response]:
    """
    安全 GET：失败不抛异常，返回 None。
    platform 用于自动带上 .env 里的 Cookie。
    碰到 403/412/418/429 会退避等待，不做验证码绕过、不做风控规避。
    """
    merged_headers = DEFAULT_HEADERS.copy()
    if headers:
        merged_headers.update(headers)

    cookie = get_cookie(platform)
    if cookie:
        merged_headers["Cookie"] = cookie

    last_status = None
    for attempt in range(retries + 1):
        try:
            sleep_a_bit(multiplier=1 + attempt)
            resp = SESSION.get(url, params=params, headers=merged_headers, timeout=timeout, allow_redirects=True)
            last_status = resp.status_code

            if resp.status_code in (403, 412, 418, 429):
                wait_seconds = min(20, 3 * (attempt + 1) + random.random() * 3)
                print(f"[WARN] {platform or 'request'} 被限制或需要登录：HTTP {resp.status_code} -> {resp.url}，等待 {wait_seconds:.1f}s 后重试")
                time.sleep(wait_seconds)
                continue

            if 200 <= resp.status_code < 300:
                if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                    resp.encoding = resp.apparent_encoding
                return resp

            print(f"[WARN] 请求失败 HTTP {resp.status_code}: {resp.url}")
        except requests.RequestException as e:
            print(f"[WARN] 请求异常 attempt={attempt + 1}: {url} -> {e}")

    if last_status in (403, 412, 418, 429):
        print("[INFO] 当前平台触发了风控，建议降低 pages、增加关键词分批运行，或改用公开新闻/B站作为主数据源。")
    return None
