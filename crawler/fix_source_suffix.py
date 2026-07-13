import json
import re
from pathlib import Path

from crawler.config import DATA_DIR


def remove_source_suffix(text: str, source: str = "") -> str:
    if not text:
        return ""

    text = str(text).strip()
    source = str(source or "").strip()

    if source:
        pattern = rf"\s*[-—–_|｜]\s*{re.escape(source)}\s*$"
        text = re.sub(pattern, "", text).strip()

    common_sources = [
        "人民网", "新华网", "央视新闻", "中国新闻网", "中新网",
        "澎湃新闻", "腾讯新闻", "网易新闻", "新浪新闻", "搜狐新闻",
        "凤凰网", "环球网", "光明网", "央广网", "中国网",
        "参考消息", "财新网", "界面新闻", "观察者网",
        "北京日报", "新京报", "红星新闻", "封面新闻",
        "上游新闻", "极目新闻", "南方都市报", "每日经济新闻",
        "第一财经", "看看新闻", "海外网"
    ]

    source_pattern = "|".join(re.escape(s) for s in common_sources)
    text = re.sub(rf"\s*[-—–_|｜]\s*({source_pattern})\s*$", "", text).strip()

    return text


def fix_file(path: Path):
    if not path.exists():
        print(f"[WARN] 文件不存在：{path}")
        return

    backup_path = path.with_name(path.stem + "_backup_before_fix_source_suffix" + path.suffix)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    changed = 0

    for item in data:
        source = item.get("source", "")

        old_title = item.get("title", "")
        old_text = item.get("text", "")

        new_title = remove_source_suffix(old_title, source)
        new_text = remove_source_suffix(old_text, source)

        if new_title != old_title or new_text != old_text:
            changed += 1

        item["title"] = new_title
        item["text"] = new_text

    with backup_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"已处理文件：{path}")
    print(f"修改记录数：{changed}")
    print(f"备份文件：{backup_path}")
    print("=" * 60)


def main():
    fix_file(DATA_DIR / "raw_data.json")

    clean_path = DATA_DIR / "clean_data.json"
    if clean_path.exists():
        fix_file(clean_path)


if __name__ == "__main__":
    main()