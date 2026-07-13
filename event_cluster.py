"""
事件聚类脚本：
把 raw_data.json / clean_data.json 中的“单条报道/帖子”聚合成“事件层数据”。

输入：
data/clean_data.json  如果存在，优先使用
data/raw_data.json    如果 clean_data 不存在，则使用 raw_data

输出：
data/events_data.json
data/event_reports.json
data/events_multi_source.json
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import parse_qs, unquote, urlparse

from crawler.config import DATA_DIR
from crawler.save_data import clean_text


COMMON_SOURCE_SUFFIX = [
    "人民网", "新华网", "央视新闻", "中国新闻网", "中新网",
    "澎湃新闻", "腾讯新闻", "网易新闻", "新浪新闻", "搜狐新闻",
    "凤凰网", "环球网", "光明网", "央广网", "中国网",
    "参考消息", "财新网", "界面新闻", "观察者网",
    "北京日报", "新京报", "红星新闻", "封面新闻",
    "上游新闻", "极目新闻", "南方都市报", "每日经济新闻",
    "第一财经", "看看新闻", "海外网", "人民资讯",
    "新浪财经", "证券之星", "财联社", "同花顺财经", "东方财富网",
    "天气网", "中国天气网", "澎湃号", "网易", "百度百科精选",
]

STOP_WORDS = {
    "一个", "一种", "这个", "那个", "相关", "消息", "新闻", "报道",
    "视频", "全文", "转载", "来源", "发布", "表示", "回应",
    "网友", "微博", "今日", "近日", "目前", "进行", "出现",
    "中国", "社会", "记者", "情况", "问题", "事件", "最新",
    "发生", "通报", "官方", "多人", "人员", "现场", "发现",
    "造成", "导致", "已致", "死亡", "受伤", "事故", "火灾", "爆炸",
    "袭击", "启动", "提升", "应急", "国家", "管理", "部门",
    "cn", "com", "www", "news", "rss", "google", "sina", "chinanews",
    "官方网站", "官方认证", "售楼处", "楼盘百科", "百科", "热搜", "ai",
}

GENERIC_EVENT_WORDS = set(STOP_WORDS) | {
    "男子", "女子", "老人", "学生", "学校", "医院", "公司", "企业",
    "涉嫌", "调查", "处理", "处置", "救援", "救治", "提醒",
}

BAD_SOURCE_KEYWORDS = [
    "vippers.jp", "newsapi-vippers.jp", "taipeitimes.com", "jamestown.org",
    "kiro7.com", "kgw.com", "dailygalaxy.com", "newsonjapan.com",
    "sportingnews.com", "mediacloud-sportingnews.com",
]

SPORTS_NOISE_WORDS = [
    "プロ野球", "ライブ中継", "テレビ放送", "ネット配信",
    "オリックス", "ソフトバンク", "阪神", "西武", "楽天",
    "sportingnews", "比赛直播", "直播中継", "赛程", "赛事",
    "NBA", "英超", "中超", "欧冠", "比分", "阵容", "赛季",
]

FINANCE_NOISE_WORDS = [
    "股票行情快报", "主力资金", "资金净买入", "资金净卖出",
    "净买入", "净卖出", "主力研究", "证券之星", "东方财富",
    "同花顺", "新浪财经", "finance.sina", "ETF", "etf", "中证",
    "份额", "最新份额", "最新规模", "基金", "净值", "成交额",
    "涨跌幅", "融资融券", "A股", "港股", "股票", "股价", "指数",
    "龙虎榜", "涨停", "跌停", "收盘", "开盘", "市值", "个股",
    "南方", "嘉实", "国泰", "华夏", "易方达",
]

COURSE_OR_AD_NOISE_WORDS = [
    "期末考试答案", "考试答案", "智慧树", "知到", "网课答案",
    "课程答案", "章节测试", "超星", "学习通", "题库", "广告",
    "清洗机", "果蔬清洗机", "守护全家", "妈妈不再担心",
]

DICTIONARY_NOISE_WORDS = [
    "词语解析", "词语解释", "词条", "释义", "拼音", "近义词",
    "反义词", "造句", "成语", "汉语词典", "汉语", "百科",
]

DICTIONARY_NOISE_DOMAINS = [
    "douyinhanyu.com", "m.douyinhanyu.com", "hanyu.baidu.com",
    "baike.baidu.com", "cidian", "zidian",
]


REAL_ESTATE_AD_NOISE_WORDS = [
    "售楼处", "楼盘百科", "官方认证", "官方网站", "百度百科精选",
    "AI热搜", "房天下", "精品房天下", "看房", "置业顾问",
    "营销中心", "售楼中心", "楼盘详情", "楼盘地址", "楼盘价格",
    "户型图", "样板间", "开盘时间", "房产百科", "买房",
]

REAL_ESTATE_AD_DOMAINS = [
    "fang.com", "anjuke.com", "focus.cn", "loupan", "newhouse",
]

BAD_TITLE_KEYWORDS = [
    "CCTV.com", "央视网", "频道", "首页", "专题", "直播",
    "十七大", "十九大", "二十大", "新闻中心", "滚动新闻",
    "图片频道", "视频频道", "法治频道", "English", "About us",
]


# ------------------------- 基础清洗 -------------------------

def remove_source_suffix(text: Any) -> str:
    text = clean_text(text)
    if not text:
        return ""

    source_pattern = "|".join(re.escape(s) for s in COMMON_SOURCE_SUFFIX)

    # 去掉：标题 - 人民网 / 标题_证券之星 / 标题｜新浪财经
    text = re.sub(rf"\s*[-—–_|｜]\s*({source_pattern})\s*$", "", text).strip()

    # 去掉：标题（来源：人民网）
    text = re.sub(rf"\s*[（(]\s*(来源[:：])?\s*({source_pattern})\s*[）)]\s*$", "", text).strip()

    # 去掉：标题 - finance.sina.com.cn / - chinanews.com.cn
    text = re.sub(
        r"\s*[-—–_|｜]\s*([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(\.[a-zA-Z]{2,})?\s*$",
        "",
        text,
    ).strip()

    return text


def normalize_title(title: Any) -> str:
    """统一标题清洗函数，整个脚本只用这个名字。"""
    title = remove_source_suffix(title)
    if not title:
        return ""

    title = re.sub(r"\s+", " ", title).strip()
    title = title.replace("_主力研究", "").strip()
    return title


def parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None

    s = str(value).strip()
    if not s or s in {"0", "1970-01-01 08:00:00", "1970-01-01 00:00:00"}:
        return None

    candidates = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y%m%dT%H%M%SZ",
        "%Y-%m-%d",
    ]

    for fmt in candidates:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass

    # Google RSS: Wed, 08 Jul 2026 12:46:58 GMT
    try:
        return parsedate_to_datetime(s).replace(tzinfo=None)
    except Exception:
        pass

    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def normalize_url_for_dedupe(url: str) -> str:
    """
    URL 去重归一化：
    1. 今日头条 jump?url=xxx 取真实 url
    2. Google News RSS 链接只保留域名 + 路径，去掉 query
    """
    url = clean_text(url)
    if not url:
        return ""

    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "url" in qs and qs["url"]:
            url = unquote(qs["url"][0])
    except Exception:
        pass

    try:
        parsed = urlparse(url)
        return f"{parsed.netloc}{parsed.path}".lower().rstrip("/")
    except Exception:
        return url.lower().strip()


# ------------------------- 质量过滤 -------------------------

def looks_like_finance_noise(content: str, source_url: str) -> bool:
    lower_source = source_url.lower()

    if any(x in lower_source for x in ["finance", "stock", "eastmoney", "10jqka"]):
        return True

    if any(w in content for w in ["证券之星", "股票行情快报", "主力资金", "主力研究"]):
        return True

    if re.search(r"[（(]\d{6}[）)]", content) and any(w in content for w in FINANCE_NOISE_WORDS):
        return True

    if any(w in content for w in FINANCE_NOISE_WORDS) and any(
        x in content for x in ["万元", "亿元", "份额", "规模", "净买入", "净卖出", "涨跌幅", "成交额"]
    ):
        return True

    return False




def looks_like_dictionary_noise(title: str, content: str, source_url: str) -> bool:
    """过滤词典/百科/解释页，这类不是舆情事件。"""
    lower_source = source_url.lower()

    if any(domain in lower_source for domain in DICTIONARY_NOISE_DOMAINS):
        return True

    # 典型标题：消防 -词语解析 / 空气质量 -词语解析
    if re.search(r"[-—–_|｜]?\s*词语解析\s*$", title):
        return True

    if any(w in content for w in DICTIONARY_NOISE_WORDS):
        # 避免误伤正常新闻，只在标题很短、像词条页时过滤
        if len(title) <= 18 or re.search(r"[-—–_|｜]\s*(词语解析|词语解释|释义|百科)\s*$", title):
            return True

    return False
def looks_like_real_estate_ad_noise(title: str, content: str, source_url: str) -> bool:
    """过滤楼盘广告/售楼处官网/AI热搜类页面，这类不是舆情事件。"""
    lower_source = source_url.lower()

    if any(domain in lower_source for domain in REAL_ESTATE_AD_DOMAINS):
        return True

    hit_count = sum(1 for w in REAL_ESTATE_AD_NOISE_WORDS if w in content)

    # 典型噪声：兰香湖二号售楼处-官方网站-楼盘百科-精品房天下✦AI热搜
    if hit_count >= 2 and any(w in content for w in ["售楼处", "楼盘百科", "官方认证", "AI热搜", "房天下"]):
        return True

    if "售楼处" in content and any(w in content for w in ["官方网站", "楼盘百科", "官方认证", "AI热搜", "房天下"]):
        return True

    if "楼盘" in content and any(w in content for w in ["官方网站", "AI热搜", "百度百科精选", "精品房天下"]):
        return True

    return False


def is_valid_event_record(item: Dict[str, Any]) -> bool:
    title = normalize_title(item.get("title", ""))
    text = clean_text(item.get("text", ""))
    source = clean_text(item.get("source", ""))
    url = clean_text(item.get("url", ""))
    time_value = item.get("time", "")

    content = f"{title} {text}"
    source_url = f"{source} {url}".lower()

    if not title and not text:
        return False

    if len(title) < 6:
        return False

    # 金融行情、基金、股票快报不是舆情事件
    if looks_like_finance_noise(content, source_url):
        return False

    # 词典/百科/解释页不是舆情事件，例如：消防 -词语解析
    if looks_like_dictionary_noise(title, content, source_url):
        return False

    # 楼盘广告/售楼处官网/AI热搜不是舆情事件
    if looks_like_real_estate_ad_noise(title, content, source_url):
        return False

    # B站课程答案 / 广告类内容不是舆情事件
    if any(w in content for w in COURSE_OR_AD_NOISE_WORDS):
        return False

    # 日文：平假名 / 片假名较多，基本不是中文舆情数据
    japanese_count = len(re.findall(r"[\u3040-\u30ff]", content))
    if japanese_count >= 3:
        return False

    if any(word.lower() in content.lower() for word in SPORTS_NOISE_WORDS):
        return False

    # 频道页 / 首页 / 历史专题页，只删标题很泛的页面
    if any(k in title for k in BAD_TITLE_KEYWORDS) and len(title) <= 35:
        return False

    dt = parse_time(time_value)
    if dt and dt.year < 2025:
        return False

    if not dt:
        vague_words = ["频道", "首页", "专题", "CCTV.com", "央视网"]
        if any(w in title for w in vague_words) and len(title) <= 35:
            return False

    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", content))
    total_len = max(len(content), 1)
    if chinese_count / total_len < 0.25:
        return False

    if any(bad in source_url for bad in BAD_SOURCE_KEYWORDS):
        return False

    return True


# ------------------------- 聚类判断 -------------------------

def make_tokens(title: str, text: str = "") -> Set[str]:
    content = normalize_title(f"{title} {text}")
    tokens: Set[str] = set()

    chinese_parts = re.findall(r"[\u4e00-\u9fff]{2,}", content)
    for part in chinese_parts:
        if 2 <= len(part) <= 10 and part not in STOP_WORDS:
            tokens.add(part)

        for n in (2, 3, 4):
            if len(part) >= n:
                for i in range(len(part) - n + 1):
                    gram = part[i:i + n]
                    if gram not in STOP_WORDS and gram not in GENERIC_EVENT_WORDS:
                        tokens.add(gram)

    for word in re.findall(r"[A-Za-z0-9]{2,}", content.lower()):
        if word not in STOP_WORDS:
            tokens.add(word)

    return tokens


def title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def token_similarity(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return inter / union


def extract_event_location(title: str) -> str:
    """粗略抽取地点，避免不同地区事故被聚到一起。"""
    title = normalize_title(title)

    patterns = [
        r"(?:针对|在|于|对)([\u4e00-\u9fff]{2,12})(?:启动|提升|发生|发布|造成|导致|遭遇|通报)",
        r"([\u4e00-\u9fff]{2,12})(?:发生|通报|回应|出现|爆发|遭遇|启动|提升)",
        r"([\u4e00-\u9fff]{2,12})(?:火灾|爆炸|事故|中毒|坍塌|地震|袭击|灾害)",
    ]

    for pattern in patterns:
        m = re.search(pattern, title)
        if not m:
            continue
        loc = m.group(1)
        loc = re.sub(r"^(今天|昨日|近日|最新|突发|刚刚|一地|多地|国家|应急管理部)", "", loc)
        loc = loc.strip()
        if 2 <= len(loc) <= 12:
            return loc[:8]

    return ""


def should_merge(
    record: Dict[str, Any],
    cluster: Dict[str, Any],
    threshold: float,
    time_window_days: int,
) -> bool:
    record_time = record.get("_dt")
    cluster_time = cluster.get("_center_dt")

    if record_time and cluster_time:
        day_diff = abs((record_time - cluster_time).days)
        if day_diff > time_window_days:
            return False

    r_title = record["_norm_title"]
    c_title = cluster["_event_norm_title"]

    loc1 = extract_event_location(r_title)
    loc2 = extract_event_location(c_title)
    if loc1 and loc2 and loc1 != loc2:
        return False

    t_sim = title_similarity(r_title, c_title)
    k_sim = token_similarity(record["_tokens"], cluster["_tokens"])

    informative_record_tokens = set(record["_tokens"]) - GENERIC_EVENT_WORDS
    informative_cluster_tokens = set(cluster["_tokens"]) - GENERIC_EVENT_WORDS
    overlap = len(informative_record_tokens & informative_cluster_tokens)

    score = max(t_sim, 0.55 * t_sim + 0.45 * k_sim)

    # 标题几乎一样，允许合并
    if t_sim >= 0.82:
        return True

    # 地点相同，并且有足够信息词重合
    if loc1 and loc2 and loc1 == loc2 and overlap >= 2 and score >= 0.50:
        return True

    # 无法抽取地点时，必须标题相似度更高，不能只靠“火灾/死亡/受伤”
    if not loc1 and not loc2 and t_sim >= 0.72 and overlap >= 2:
        return True

    if score >= threshold and overlap >= 4:
        return True

    return False


# ------------------------- 数据加载与导出 -------------------------

def load_records() -> List[Dict[str, Any]]:
    clean_path = DATA_DIR / "clean_data.json"
    raw_path = DATA_DIR / "raw_data.json"
    input_path = clean_path if clean_path.exists() else raw_path

    if not input_path.exists():
        print(f"[ERROR] 找不到输入文件：{input_path}")
        return []

    print(f"[INFO] 使用输入文件：{input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("[ERROR] 输入数据不是列表")
        return []

    before_count = len(data)
    seen = set()
    unique_records = []

    for item in data:
        if not is_valid_event_record(item):
            continue

        title = normalize_title(item.get("title", ""))
        source = clean_text(item.get("source", ""))
        url = clean_text(item.get("url", ""))

        if title and source:
            key = ("title_source", title, source)
        elif title:
            key = ("title", title)
        elif url:
            key = ("url", normalize_url_for_dedupe(url))
        else:
            continue

        if key in seen:
            continue

        seen.add(key)
        unique_records.append(item)

    after_count = len(unique_records)
    print(f"[INFO] 聚类前去重：{before_count} -> {after_count}，删除重复 {before_count - after_count} 条")
    return unique_records


def build_events(records: List[Dict[str, Any]], threshold: float, time_window_days: int):
    clusters: List[Dict[str, Any]] = []
    inverted_index = defaultdict(set)

    for item in records:
        title = normalize_title(item.get("title", ""))
        text = remove_source_suffix(item.get("text", ""))
        source = clean_text(item.get("source", ""))
        time_value = item.get("time", "")

        if not title and not text:
            continue

        norm_title = normalize_title(title or text[:80])
        tokens = make_tokens(title, text)
        dt = parse_time(time_value)

        if not norm_title or len(tokens) < 2:
            continue

        record = dict(item)
        record["title"] = title
        record["text"] = text
        record["source"] = source
        record["_norm_title"] = norm_title
        record["_tokens"] = tokens
        record["_dt"] = dt

        candidate_cluster_ids = set()
        important_tokens = sorted(tokens - GENERIC_EVENT_WORDS, key=len, reverse=True)[:12]
        if not important_tokens:
            important_tokens = sorted(tokens, key=len, reverse=True)[:8]

        for tok in important_tokens:
            candidate_cluster_ids.update(inverted_index.get(tok, set()))

        best_cluster_id = None
        best_score = 0.0

        for cid in candidate_cluster_ids:
            cluster = clusters[cid]

            if not should_merge(record, cluster, threshold, time_window_days):
                continue

            t_sim = title_similarity(record["_norm_title"], cluster["_event_norm_title"])
            k_sim = token_similarity(record["_tokens"], cluster["_tokens"])
            score = max(t_sim, 0.55 * t_sim + 0.45 * k_sim)

            if score > best_score:
                best_score = score
                best_cluster_id = cid

        if best_cluster_id is None:
            cid = len(clusters)
            cluster = {
                "_event_norm_title": norm_title,
                "_tokens": set(tokens),
                "_center_dt": dt,
                "records": [record],
            }
            clusters.append(cluster)

            for tok in important_tokens:
                inverted_index[tok].add(cid)
        else:
            cluster = clusters[best_cluster_id]
            cluster["records"].append(record)
            cluster["_tokens"].update(tokens)

            if len(norm_title) > len(cluster["_event_norm_title"]):
                cluster["_event_norm_title"] = norm_title

            if dt and not cluster.get("_center_dt"):
                cluster["_center_dt"] = dt

            for tok in important_tokens:
                inverted_index[tok].add(best_cluster_id)

    return clusters


def choose_event_title(records: List[Dict[str, Any]], fallback: str) -> str:
    candidates = [normalize_title(r.get("title", "")) for r in records if r.get("title")]
    candidates = [c for c in candidates if c]
    if not candidates:
        return fallback

    def title_score(t: str) -> int:
        score = 0
        if 10 <= len(t) <= 55:
            score += 20
        score -= abs(len(t) - 28)
        if any(w in t for w in ["快报", "股票", "ETF", "份额", "净买入", "净卖出"]):
            score -= 100
        if any(w in t for w in ["词语解析", "词语解释", "释义", "百科"]):
            score -= 100
        if any(s in t for s in COMMON_SOURCE_SUFFIX):
            score -= 5
        return score

    return max(candidates, key=title_score)


def export_events(clusters: List[Dict[str, Any]], min_reports: int = 1):
    events = []
    event_reports = []

    clusters = sorted(
        clusters,
        key=lambda c: (-len(c["records"]), c["records"][0].get("time", ""))
    )

    event_idx = 1

    for cluster in clusters:
        records = cluster["records"]
        if len(records) < min_reports:
            continue

        event_id = f"E{event_idx:05d}"
        event_idx += 1

        sources = sorted(set(clean_text(r.get("source", "")) for r in records if r.get("source")))
        times = [parse_time(r.get("time")) for r in records if parse_time(r.get("time"))]
        token_counter = Counter()

        for r in records:
            token_counter.update((set(r.get("_tokens", [])) - GENERIC_EVENT_WORDS))

        keywords = [
            word for word, _ in token_counter.most_common(8)
            if len(word) >= 2 and word not in STOP_WORDS and word not in GENERIC_EVENT_WORDS
        ]

        related_reports = []
        for r in records:
            record_id = r.get("id")
            report = {
                "record_id": record_id,
                "title": normalize_title(r.get("title", "")),
                "source": r.get("source", ""),
                "time": r.get("time", ""),
                "url": r.get("url", ""),
            }
            related_reports.append(report)
            event_reports.append({"event_id": event_id, **report})

        event_title = choose_event_title(records, cluster.get("_event_norm_title", ""))

        event = {
            "event_id": event_id,
            "event_title": event_title,
            "keywords": keywords,
            "start_time": min(times).strftime("%Y-%m-%d %H:%M:%S") if times else "",
            "end_time": max(times).strftime("%Y-%m-%d %H:%M:%S") if times else "",
            "sources": sources,
            "source_count": len(sources),
            "report_count": len(records),
            "hot_score": len(records) + len(sources) * 0.5,
            "related_reports": related_reports,
        }
        events.append(event)

    events_path = DATA_DIR / "events_data.json"
    event_reports_path = DATA_DIR / "event_reports.json"
    multi_source_events_path = DATA_DIR / "events_multi_source.json"

    with events_path.open("w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    with event_reports_path.open("w", encoding="utf-8") as f:
        json.dump(event_reports, f, ensure_ascii=False, indent=2)

    multi_source_events = [
        e for e in events
        if e.get("source_count", 0) >= 2 and e.get("report_count", 0) >= 2
    ]

    with multi_source_events_path.open("w", encoding="utf-8") as f:
        json.dump(multi_source_events, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("事件聚类完成")
    print(f"事件数：{len(events)}")
    print(f"事件文件：{events_path}")
    print(f"事件-报道映射文件：{event_reports_path}")
    print(f"多来源事件文件：{multi_source_events_path}")
    print(f"多来源事件数：{len(multi_source_events)}")

    multi_events = [e for e in events if e["report_count"] >= 2]
    print(f"多报道事件数：{len(multi_events)}")

    if events:
        print("第一条事件示例：")
        print(json.dumps(events[0], ensure_ascii=False, indent=2)[:1200])

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="把原始舆情数据聚类成事件层数据")
    parser.add_argument("--threshold", type=float, default=0.62, help="相似度阈值，默认 0.62")
    parser.add_argument("--time-window-days", type=int, default=7, help="同事件最大时间窗口，默认 7 天")
    parser.add_argument("--min-reports", type=int, default=1, help="事件最少报道数，默认 1")
    args = parser.parse_args()

    records = load_records()

    print(f"[INFO] 原始记录数：{len(records)}")
    print(f"[INFO] threshold={args.threshold}, time_window_days={args.time_window_days}")

    clusters = build_events(
        records=records,
        threshold=args.threshold,
        time_window_days=args.time_window_days,
    )

    print(f"[INFO] 初步聚类数：{len(clusters)}")
    export_events(clusters, min_reports=args.min_reports)


if __name__ == "__main__":
    main()
