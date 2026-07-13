"""检查 data/raw_data.json 是否符合后端字段。运行：python -m crawler.check_output"""
import json
from collections import Counter
from pathlib import Path

from .config import DATA_DIR

path = DATA_DIR / "raw_data.json"
if not path.exists():
    print(f"没有找到 {path}，请先运行 python -m crawler.main")
    raise SystemExit(1)

records = json.loads(path.read_text(encoding="utf-8"))
print(f"总数据量：{len(records)}")
print("字段检查：", "通过" if all(set(["id", "title", "text", "time", "source", "url"]).issubset(r.keys()) for r in records) else "不通过")
print("来源统计：")
for source, count in Counter((r.get("source") or "未知").split("-")[0] for r in records).most_common(20):
    print(f"  {source}: {count}")
print("\n前三条示例：")
for r in records[:3]:
    print(r)
