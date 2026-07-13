# -*- coding: utf-8 -*-
"""
repair_text_fields_v2.py

作用：
1. 清理 raw_data.json 中正文末尾的“来源/责任编辑/编辑/版权”等尾巴。
2. 去掉明显的数字噪音、股票/金融串、Yahoo consent 提示、[+1045 chars] 残留。
3. 识别 text == title 的情况，不再把标题当正文。
4. 可选：对正文缺失/无效的数据，根据 url 重新抓详情页正文。

推荐放到项目目录：crawler/repair_text_fields_v2.py

运行示例：
python -m crawler.repair_text_fields_v2 --input data/raw_data.json --output data/raw_data_text_fixed.json --limit 100
python -m crawler.repair_text_fields_v2 --input data/raw_data.json --output data/raw_data_text_fixed.json --fetch-detail --sleep 0.5
"""

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable

try:
    import requests
except Exception:
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None


def normalize_space(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def compact_for_compare(text: Any) -> str:
    text = normalize_space(text)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。！？、,.!?:：;；“”\"'‘’（）()\[\]【】<>《》\-—_丨|/\\]", "", text)
    return text.lower()


def chinese_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def is_title_as_text(title: str, text: str) -> bool:
    title_c = compact_for_compare(title)
    text_c = compact_for_compare(text)
    if not title_c or not text_c:
        return False
    if title_c == text_c:
        return True
    if text_c.startswith(title_c) and len(text_c) <= len(title_c) + 30:
        return True
    return False


CONSENT_PATTERNS = [
    r"If you click 'Accept all'.*?(?:\[\+\d+\s*chars\])?",
    r"we and our partners.*?(?:\[\+\d+\s*chars\])?",
    r"IAB Transparency & Consent Framework.*?(?:\[\+\d+\s*chars\])?",
    r"store and/or access information on a device.*?(?:\[\+\d+\s*chars\])?",
    r"consent\.yahoo\.com\S*",
]

TAIL_PATTERNS = [
    r"\s*来源[:：]\s*[^。\n]{1,120}$",
    r"\s*資料來源[:：]\s*[^。\n]{1,120}$",
    r"\s*资料来源[:：]\s*[^。\n]{1,120}$",
    r"\s*本文来源[:：]\s*[^。\n]{1,120}$",
    r"\s*文章来源[:：]\s*[^。\n]{1,120}$",
    r"\s*图源[:：]\s*[^。\n]{1,120}$",
    r"\s*視頻來源[:：]\s*[^。\n]{1,120}$",
    r"\s*视频来源[:：]\s*[^。\n]{1,120}$",
    r"\s*责任编辑[:：]\s*[^。\n]{1,80}$",
    r"\s*責任編輯[:：]\s*[^。\n]{1,80}$",
    r"\s*编辑[:：]\s*[^。\n]{1,80}$",
    r"\s*編輯[:：]\s*[^。\n]{1,80}$",
    r"\s*责编[:：]\s*[^。\n]{1,80}$",
    r"\s*审核[:：]\s*[^。\n]{1,80}$",
    r"\s*記者[:：]\s*[^。\n]{1,80}$",
    r"\s*记者[:：]\s*[^。\n]{1,80}$",
    r"\s*原标题[:：]\s*[^。\n]{1,160}$",
    r"\s*原標題[:：]\s*[^。\n]{1,160}$",
    r"\s*©\s*\d{4}(?:-\d{4})?.{0,120}$",
    r"\s*All rights reserved\.?.{0,120}$",
    r"\s*版权.*?所有.{0,120}$",
    r"\s*版權.*?所有.{0,120}$",
    r"\s*违法和不良信息举报.{0,120}$",
    r"\s*打开.{0,20}新闻.{0,120}$",
    r"\s*下載.{0,20}客戶端.{0,120}$",
    r"\s*下载.{0,20}客户端.{0,120}$",
    r"\s*更多精彩.{0,120}$",
    r"\s*关注.{0,30}公众号.{0,120}$",
    r"\s*聲明[:：].{0,160}$",
    r"\s*声明[:：].{0,160}$",
    r"\s*\[\+\d+\s*chars\]\s*$",
]

TAIL_LINE_PATTERNS = [
    r"^来源[:：].{0,120}$",
    r"^資料來源[:：].{0,120}$",
    r"^资料来源[:：].{0,120}$",
    r"^本文来源[:：].{0,120}$",
    r"^文章来源[:：].{0,120}$",
    r"^责任编辑[:：].{0,80}$",
    r"^責任編輯[:：].{0,80}$",
    r"^编辑[:：].{0,80}$",
    r"^編輯[:：].{0,80}$",
    r"^责编[:：].{0,80}$",
    r"^审核[:：].{0,80}$",
    r"^记者[:：].{0,80}$",
    r"^記者[:：].{0,80}$",
    r"^原标题[:：].{0,160}$",
    r"^原標題[:：].{0,160}$",
    r"^打开.{0,20}新闻.{0,120}$",
    r"^下载.{0,20}客户端.{0,120}$",
    r"^下載.{0,20}客戶端.{0,120}$",
    r"^更多精彩.{0,120}$",
    r"^关注.{0,30}公众号.{0,120}$",
    r"^©\s*\d{4}(?:-\d{4})?.{0,120}$",
    r"^All rights reserved\.?.{0,120}$",
]

NUMERIC_NOISE_TAIL = re.compile(r"(\s(?:[\d,\.%％\-\+\(\)（）/A-Za-z]{2,}\s*){3,})$")


def remove_consent_noise(text: str) -> str:
    for pat in CONSENT_PATTERNS:
        text = re.sub(pat, " ", text, flags=re.I | re.S)
    return normalize_space(text)


def remove_tail_source(text: str) -> str:
    text = normalize_space(text)
    if not text:
        return ""
    lines = []
    for line in text.splitlines():
        line = normalize_space(line)
        if not line:
            continue
        if any(re.search(pat, line, flags=re.I) for pat in TAIL_LINE_PATTERNS):
            continue
        lines.append(line)
    text = "\n".join(lines).strip()
    changed = True
    while changed:
        old = text
        for pat in TAIL_PATTERNS:
            text = re.sub(pat, "", text, flags=re.I | re.S).strip()
        changed = (text != old)
    return normalize_space(text)


def remove_numeric_tail_noise(text: str) -> str:
    text = normalize_space(text)
    if not text:
        return ""
    changed = True
    while changed:
        changed = False
        new_text = re.sub(r"\s*\[\+\d+\s*chars\]\s*$", "", text, flags=re.I).strip()
        if new_text != text:
            text = new_text
            changed = True
        m = NUMERIC_NOISE_TAIL.search(text)
        if m:
            tail = m.group(1)
            if len(tail) >= 12 and chinese_count(tail) <= 2:
                text = text[:m.start(1)].strip()
                changed = True
        new_text = re.sub(r"\s+\d{1,4}[A-Za-z]{3,}(?:\s+[A-Za-z]{2,}){0,8}\s*$", "", text).strip()
        if new_text != text:
            text = new_text
            changed = True
        new_text = re.sub(r"\s+[0-9,\.%％\-\+\(\)（）/ ]{8,}\s*$", "", text).strip()
        if new_text != text:
            text = new_text
            changed = True
    return normalize_space(text)


def remove_title_prefix(text: str, title: str) -> str:
    text = normalize_space(text)
    title = normalize_space(title)
    if text and title and text.startswith(title):
        text = text[len(title):].strip(" \n\t。-—_丨|：:，,")
    return normalize_space(text)


def clean_text_field(text: Any, title: str = "") -> str:
    text = normalize_space(text)
    title = normalize_space(title)
    if not text:
        return ""
    text = remove_consent_noise(text)
    text = remove_title_prefix(text, title)
    text = remove_tail_source(text)
    text = remove_numeric_tail_noise(text)
    text = remove_tail_source(text)
    return normalize_space(text)


def is_valid_article_text(text: str, title: str = "") -> bool:
    text = clean_text_field(text, title)
    if not text:
        return False
    if is_title_as_text(title, text):
        return False
    if chinese_count(text) < 40 and len(text) < 120:
        return False
    if re.search(r"Accept all|IAB Transparency|store and/or access|consent\.yahoo", text, flags=re.I):
        return False
    if re.search(r"引用元[:：]|転載元[:：]|hayabusa|5ch\.io|それでも動く名無し", text, flags=re.I):
        return False
    return True


def fetch_html(url: str, timeout: int = 12) -> str:
    if not url or requests is None:
        return ""
    if "consent.yahoo.com" in url:
        return ""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en;q=0.6",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code >= 400:
            return ""
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding
        return resp.text or ""
    except Exception:
        return ""


def html_to_text(html: str, title: str = "") -> str:
    if not html:
        return ""
    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe", "svg", "form", "header", "footer", "nav"]):
            tag.decompose()
        selectors = [
            "article", "#artibody", "#article", ".article", ".article-content",
            ".article_body", ".article-body", ".content", ".main-content",
            ".post-content", ".post_body", ".post-body", ".text",
            ".news-content", ".news_txt", ".news-text", ".detail",
            ".detail-content", ".rich_media_content",
        ]
        candidates = []
        for selector in selectors:
            for block in soup.select(selector):
                parts = []
                for p in block.find_all(["p", "div"]):
                    t = normalize_space(p.get_text(" ", strip=True))
                    if t:
                        parts.append(t)
                text = clean_text_field("\n".join(parts), title)
                if text:
                    candidates.append((chinese_count(text) + len(parts) * 20, text))
        parts = []
        for p in soup.find_all("p"):
            t = normalize_space(p.get_text(" ", strip=True))
            if t:
                parts.append(t)
        text = clean_text_field("\n".join(parts), title)
        if text:
            candidates.append((chinese_count(text) + len(parts) * 20, text))
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?is)</p>", "\n", html)
    html = re.sub(r"(?is)<.*?>", " ", html)
    html = html.replace("&nbsp;", " ").replace("&quot;", '"').replace("&amp;", "&")
    return clean_text_field(html, title)


def extract_detail_text(url: str, title: str = "") -> str:
    html = fetch_html(url)
    if not html:
        return ""
    text = html_to_text(html, title)
    if is_valid_article_text(text, title):
        return clean_text_field(text, title)
    return ""


def get_first(item: Dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def repair_item(item: Dict[str, Any], fetch_detail: bool = False, sleep: float = 0.0) -> Dict[str, Any]:
    new_item = dict(item)
    title = get_first(new_item, ["title", "name"])
    url = get_first(new_item, ["url", "link"])
    old_text = get_first(new_item, ["text", "content", "description", "summary", "snippet"])
    cleaned = clean_text_field(old_text, title)
    title_equal_old = is_title_as_text(title, old_text)
    title_equal_cleaned = is_title_as_text(title, cleaned)
    detail_text = ""
    if is_valid_article_text(cleaned, title):
        final_text = cleaned
        has_full_text = True
        text_source = "old_text_cleaned"
    else:
        if fetch_detail and url and "bilibili.com" not in url and "consent.yahoo.com" not in url:
            detail_text = extract_detail_text(url, title)
            if sleep > 0:
                time.sleep(sleep)
        if is_valid_article_text(detail_text, title):
            final_text = detail_text
            has_full_text = True
            text_source = "detail_page"
        else:
            final_text = ""
            has_full_text = False
            if title_equal_old or title_equal_cleaned:
                text_source = "empty_title_as_text"
            elif "consent.yahoo.com" in url or re.search(r"Accept all|IAB Transparency|store and/or access", old_text, flags=re.I):
                text_source = "empty_consent_noise"
            else:
                text_source = "empty_invalid_text"
    new_item["text"] = final_text
    new_item["has_full_text"] = has_full_text
    new_item["text_source"] = text_source
    new_item["text_length"] = len(final_text)
    new_item["title_equals_text"] = is_title_as_text(title, final_text)
    new_item["old_title_equals_text"] = title_equal_old
    return new_item


def main():
    parser = argparse.ArgumentParser(description="清洗 raw_data 正文：去尾部来源、数字噪音、标题冒充正文，可选重新抓正文")
    parser.add_argument("--input", default="data/raw_data.json", help="输入 JSON 文件")
    parser.add_argument("--output", default="data/raw_data_text_fixed.json", help="输出 JSON 文件")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 条，0 表示全量")
    parser.add_argument("--fetch-detail", action="store_true", help="是否根据 url 重新抓详情页正文")
    parser.add_argument("--sleep", type=float, default=0.3, help="抓详情页间隔秒数")
    args = parser.parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        print(f"[ERROR] 找不到输入文件：{input_path}")
        return
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data_to_process = data[:args.limit] if args.limit and args.limit > 0 else data
    fixed = []
    stats = {
        "total": 0,
        "has_full_text": 0,
        "empty_text": 0,
        "old_text_cleaned": 0,
        "detail_page": 0,
        "empty_title_as_text": 0,
        "empty_consent_noise": 0,
        "empty_invalid_text": 0,
    }
    for idx, item in enumerate(data_to_process, start=1):
        repaired = repair_item(item, fetch_detail=args.fetch_detail, sleep=args.sleep)
        fixed.append(repaired)
        stats["total"] += 1
        if repaired.get("has_full_text"):
            stats["has_full_text"] += 1
        else:
            stats["empty_text"] += 1
        source = repaired.get("text_source", "")
        if source in stats:
            stats[source] += 1
        if idx % 100 == 0:
            print(f"[INFO] 已处理 {idx}/{len(data_to_process)} | 有正文 {stats['has_full_text']} | 空正文 {stats['empty_text']} | 详情页 {stats['detail_page']}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False, indent=2)
    print("=" * 60)
    print("正文清洗完成")
    print(f"输入：{input_path}")
    print(f"输出：{output_path}")
    for k, v in stats.items():
        print(f"{k}: {v}")
    print("=" * 60)


if __name__ == "__main__":
    main()
