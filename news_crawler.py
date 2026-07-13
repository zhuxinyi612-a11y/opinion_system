"""
新闻爬虫：使用 GDELT 公开新闻检索接口。
优点：不用登录、不用 Cookie，适合作业演示和批量收集新闻标题/链接。
注意：不同新闻站点正文结构不同，正文抓取不一定每条都成功，失败时 text 会退化为标题。
"""
import re
from bs4 import BeautifulSoup
from typing import List, Dict
from urllib.parse import urlparse

from .http_client import safe_get
from .save_data import make_record, clean_text

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

def chinese_char_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def is_good_chinese_news(title: str, text: str, url: str, source: str) -> bool:
    """
    过滤 GDELT/news 中的低质量结果：
    1. 中文太少的不要
    2. 正文太短的不要
    3. title 和 text 完全一样时，通常说明正文没抽成功
    4. 英文站点为主的来源先过滤
    """
    title = title or ""
    text = text or ""
    url = url or ""
    source = source or ""

    content = title + " " + text
    chinese_count = chinese_char_count(content)

    # 中文太少，基本不是中文舆情数据
    if chinese_count < 8:
        return False

    # 正文太短，质量不够
    if len(text.strip()) < 30:
        return False

    # text 完全等于 title，说明没有真正抽到正文
    if text.strip() == title.strip():
        return False

    bad_sources = [
        "taipeitimes.com",
        "jamestown.org",
        "kiro7.com",
        "kgw.com",
        "dailygalaxy.com",
        "newsonjapan.com",
        "themarketsdaily.com",
    ]

    source_text = (source + " " + url).lower()

    if any(bad in source_text for bad in bad_sources):
        return False

    return True

def extract_article_text(url: str, max_chars: int = 1500) -> str:
    """
    提取新闻正文：
    只从 article、正文容器、p 标签中提取文本，
    避免混入页面 DOM 里的坐标、ID、时间戳、布局数字等噪声。
    """
    try:
        resp = safe_get(url, platform="news_detail")
    except Exception as e:
        print(f"[WARN] 新闻详情页请求失败：{url} -> {e}")
        return ""

    if not resp:
        return ""

    try:
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception:
        return ""

    # 删除明显不是正文的标签
    for tag in soup([
        "script", "style", "noscript", "svg", "canvas",
        "header", "footer", "nav", "aside", "form",
        "button", "input", "select", "option", "iframe"
    ]):
        tag.decompose()

    candidates = []

    # 1. 优先取 article 标签
    article = soup.find("article")
    if article:
        candidates.append(article)

    # 2. 常见正文容器
    selectors = [
        "[class*=article]",
        "[class*=content]",
        "[class*=main]",
        "[class*=text]",
        "[class*=detail]",
        "[class*=news]",
        "[id*=article]",
        "[id*=content]",
        "[id*=main]",
        "[id*=detail]",
        "[id*=news]",
    ]

    for selector in selectors:
        try:
            for node in soup.select(selector):
                candidates.append(node)
        except Exception:
            continue

    # 3. 如果没有正文容器，就只取所有 p 标签
    if not candidates:
        candidates = soup.find_all("p")

    paragraphs = []

    for node in candidates:
        ps = node.find_all("p")

        if not ps:
            ps = [node]

        for p in ps:
            text = p.get_text(" ", strip=True)
            text = clean_text(text)

            if not is_valid_article_paragraph(text):
                continue

            paragraphs.append(text)

    # 去重，保持顺序
    seen = set()
    clean_paragraphs = []

    for p in paragraphs:
        if p in seen:
            continue

        seen.add(p)
        clean_paragraphs.append(p)

    final_text = "\n".join(clean_paragraphs).strip()

    return final_text[:max_chars]

def is_valid_article_paragraph(text: str) -> bool:
    """
    判断一段文本是不是新闻正文段落。
    过滤：
    1. 太短文本
    2. 数字比例过高文本
    3. 中文比例过低文本
    4. 长数字 ID / 时间戳 / 坐标
    5. 页面导航和版权信息
    """
    if not text:
        return False

    if len(text) < 20:
        return False

    digits = sum(ch.isdigit() for ch in text)
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))

    total = max(len(text), 1)
    digit_ratio = digits / total
    chinese_ratio = chinese / total

    # 数字太多，通常是 ID、坐标、时间戳、统计代码
    if digit_ratio > 0.35:
        return False

    # 中文太少，通常不是中文正文
    if chinese_ratio < 0.2:
        return False

    # 连续长数字，通常是 ID、时间戳、坐标、埋点参数
    if re.search(r"\d{8,}", text):
        return False

    noise_words = [
        "版权所有", "ICP备案", "责任编辑", "免责声明",
        "登录", "注册", "分享", "点赞", "收藏",
        "二维码", "扫一扫", "客户端", "广告",
        "上一页", "下一页", "返回首页"
    ]

    if any(word in text for word in noise_words) and len(text) < 100:
        return False

    return True


def crawl(keyword: str, max_pages: int = 3, fetch_detail: bool = True) -> List[Dict]:
    """
    GDELT 新闻采集。
    现在默认抓取详情页正文：
    1. 正文抓取成功且质量合格才保存
    2. 正文抓取失败就跳过，不再用 title 冒充正文
    3. 降低 maxrecords，减少 GDELT 429 限流
    """

    # GDELT 容易 429，别一次取太多
    max_records = min(max_pages * 15, 30)

    params = {
        "query": keyword,
        "mode": "ArtList",
        "format": "json",
        "sort": "HybridRel",
        "maxrecords": max_records,
    }

    resp = safe_get(
        GDELT_DOC_API,
        params=params,
        platform="news",
        headers={"Accept": "application/json"},
    )

    if not resp:
        return []

    try:
        payload = resp.json()
    except Exception:
        print("[WARN] news 返回的不是 JSON")
        return []

    records = []

    for item in payload.get("articles", []):
        title = clean_text(item.get("title", "") or "")
        url = item.get("url", "") or ""
        domain = item.get("domain") or urlparse(url).netloc
        source_name = item.get("sourceCommonName") or domain or "新闻网站"
        time_value = item.get("seendate", "") or ""

        if not title or not url:
            continue

        # 默认抓详情页正文
        detail_text = ""

        if fetch_detail and url:
            detail_text = extract_article_text(url)

        final_text = clean_text(detail_text or "")

        # 关键：正文没抓到就跳过，不再用标题冒充正文
        if not is_good_chinese_news(title, final_text, url, source_name):
            continue

        record = make_record(
            title=title,
            text=final_text,
            source=source_name,
            time_value=time_value,
            url=url,
        )

        records.append(record)

    print(f"[INFO] news keyword='{keyword}' 过滤后保留 {len(records)} 条高质量中文新闻")

    return records