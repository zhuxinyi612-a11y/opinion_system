import csv
import hashlib
import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .config import START_ID

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def clean_text(value: Any) -> str:
    """清洗 HTML、换行、多余空格。"""
    if value is None:
        return ""
    text = str(value)
    text = html.unescape(text)
    text = TAG_RE.sub(" ", text)
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def normalize_time(value: Any) -> str:
    """把时间统一成后端示例里的 YYYY-mm-dd HH:MM:SS；无法解析就原样返回。"""
    if value is None or value == "":
        return ""

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(int(value)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(value)

    s = str(value).strip()
    if not s:
        return ""

    # 10位时间戳
    if re.fullmatch(r"\d{10}", s):
        try:
            return datetime.fromtimestamp(int(s)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return s

    # 13位毫秒时间戳
    if re.fullmatch(r"\d{13}", s):
        try:
            return datetime.fromtimestamp(int(s) / 1000).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return s

    # GDELT 常见格式：20260701103000
    if re.fullmatch(r"\d{14}", s):
        try:
            return datetime.strptime(s, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return s

    # 有些接口给的是 2026-07-01T10:30:00Z
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    return s


def make_record(
    title: Any,
    text: Any,
    source: Any,
    time_value: Any = "",
    url: Any = "",
    record_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    统一输出后端需要的字段：id/title/text/time/source/url。
    id 在 main.py 里统一分配。
    """
    return {
        "id": record_id,
        "title": clean_text(title),
        "text": clean_text(text),
        "time": normalize_time(time_value),
        "source": clean_text(source),
        "url": clean_text(url),
    }


def record_fingerprint(record: Dict[str, Any]) -> str:
    base = "|".join([
        record.get("title", "")[:80],
        record.get("text", "")[:120],
        record.get("source", ""),
        record.get("url", ""),
    ])
    return hashlib.md5(base.encode("utf-8", errors="ignore")).hexdigest()


def deduplicate(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for r in records:
        title = clean_text(r.get("title", ""))
        text = clean_text(r.get("text", ""))
        if not title and not text:
            continue
        fp = record_fingerprint(r)
        if fp in seen:
            continue
        seen.add(fp)
        result.append(r)
    return result


def assign_ids(records: List[Dict[str, Any]], start_id: int = START_ID) -> List[Dict[str, Any]]:
    for i, record in enumerate(records, start=start_id):
        record["id"] = i
    return records


def save_json(records: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def save_jsonl(records: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def save_csv(records: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["id", "title", "text", "time", "source", "url"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
