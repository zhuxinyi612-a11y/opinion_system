from pathlib import Path

START_ID = 10001

DEFAULT_KEYWORDS = [
    "校园舆情",
    "网络舆情",
]

DEFAULT_MAX_PAGES = 3

# 请求超时与间隔。想更稳可以把 MIN_DELAY/MAX_DELAY 调大。
TIMEOUT = 15
MIN_DELAY = 1.8
MAX_DELAY = 4.5

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Connection": "keep-alive",
}

COOKIE_ENV_MAP = {
    "weibo": "WEIBO_COOKIE",
    "zhihu": "ZHIHU_COOKIE",
    "toutiao": "TOUTIAO_COOKIE",
    "xiaohongshu": "XHS_COOKIE",
}
