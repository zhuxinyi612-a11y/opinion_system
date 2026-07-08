"""
模拟数据生成器
==============
在队友（1号爬虫、2号清洗、3号NLP）的数据到位之前，
用这个模块自己生成假数据来开发和测试。

使用方式：
    from time_series.utils import generate_mock_events
    events = generate_mock_events()
"""

import random
from datetime import datetime, timedelta
from typing import Any

# ---- 可调参数 ----
# 模拟的事件数量，每个事件 72 小时（3天）的数据，每小时一条记录
HOURS_PER_EVENT = 72
DATA_INTERVAL_HOURS = 1


def _simulate_lifecycle_curve(hours: int = HOURS_PER_EVENT) -> list[int]:
    """
    模拟一条舆情热度曲线（报道量随时间变化）
    返回长度为 hours 的列表，每个值是该小时的报道量

    曲线形状：低位徘徊 → 快速拉升 → 高位震荡 → 缓慢回落
    叠加昼夜周期：凌晨2-5点自然下降20%~40%，下午2-5点自然上升10%~20%
    """
    import math

    curve: list[int] = []
    for h in range(hours):
        # —— 基础趋势分量 ——
        if h < 8:
            trend = random.randint(0, 5)
        elif h < 20:
            trend = random.randint(5, 15) + (h - 8) * 3
        elif h < 45:
            trend = 40 + random.randint(-10, 15)
        else:
            decay = (h - 45) * 0.8
            trend = max(0, int(40 - decay + random.randint(-5, 5)))

        # —— 昼夜周期分量 ——
        # 模拟"人醒了才发帖"的规律：
        #   凌晨 0-6点：产出只有正常的 50%~70%
        #   上午 6-10点：逐渐恢复到正常
        #   下午 10-18点：高峰期，正常 110%~130%
        #   晚上 18-24点：逐渐回落到正常
        hour_of_day = h % 24
        # 用 sin 波模拟：相位偏移使得凌晨4点最低，下午4点最高
        circadian_factor = 1.0 + 0.25 * math.sin((hour_of_day - 4) * math.pi / 12)

        count = int(round(trend * circadian_factor))
        count = max(0, count)
        curve.append(count)
    return curve


def _simulate_resurgence_curve(hours: int = HOURS_PER_EVENT) -> list[int]:
    """
    模拟一条带"二次爆发"的热度曲线

    典型场景：某事件热度下降→新证据/官方回应出现→热度二次飙升
    曲线形状：潜伏→拉升→高潮→下降→低谷→反转拉升→二次高潮→下降
    """
    import math

    curve: list[int] = []
    for h in range(hours):
        # 双峰趋势分量
        if h < 8:
            trend = random.randint(0, 5)
        elif h < 18:
            trend = random.randint(5, 15) + (h - 8) * 3
        elif h < 30:
            trend = 35 + random.randint(-8, 12)
        elif h < 40:
            decay = (h - 30) * 2.0
            trend = max(0, int(35 - decay + random.randint(-3, 3)))
        elif h < 48:
            ramp = (h - 40) * 4
            trend = int(15 + ramp + random.randint(-5, 5))
        elif h < 58:
            trend = 45 + random.randint(-10, 10)
        else:
            decay2 = (h - 58) * 2.5
            trend = max(0, int(45 - decay2 + random.randint(-5, 5)))

        hour_of_day = h % 24
        circadian_factor = 1.0 + 0.25 * math.sin((hour_of_day - 4) * math.pi / 12)

        count = int(round(trend * circadian_factor))
        count = max(0, count)
        curve.append(count)
    return curve


def generate_mock_events(num_events: int = 3) -> list[dict[str, Any]]:
    """
    生成模拟舆情事件数据

    返回格式（就是和队友约定好的数据格式）：
    [
      {
        "event_id": "EVT_001",
        "event_title": "...",
        "category": "社会/科技/娱乐",
        "start_time": datetime对象,
        "timeseries": [
          {
            "time": datetime对象,
            "news_count": 该小时报道量,
            "positive_ratio": 正面比例 0~1,
            "negative_ratio": 负面比例 0~1,
            "neutral_ratio": 中性比例 0~1,
            "hot_score": 平均热度分 0~100
          },
          ...
        ]
      },
      ...
    ]
    """
    categories = ["社会民生", "科技互联网", "娱乐八卦", "财经商业", "国际时政"]
    titles_pool = [
        "某地突发公共卫生事件引关注",
        "某科技公司发布新品引发争议",
        "某明星言论引发网友热议",
        "某地政策调整影响广泛讨论",
        "某企业财报造假传闻扩散",
    ]

    events: list[dict[str, Any]] = []
    base_time = datetime(2026, 7, 4, 0, 0, 0)  # 模拟起始时间

    for i in range(num_events):
        # 最后一个是二次爆发事件，其余是正常生命周期
        if i == num_events - 1 and num_events >= 1:
            curve = _simulate_resurgence_curve()
        else:
            curve = _simulate_lifecycle_curve()

        records: list[dict[str, Any]] = []
        for h, count in enumerate(curve):
            t = base_time + timedelta(hours=h)

            # 情感比例：随热度升高，负面比例和分歧都会增加
            # count高→争议大→负面和正面都高（中性低），分歧大
            heat_ratio = min(count / 50.0, 1.0)
            neg = round(random.uniform(0.1 + 0.15 * heat_ratio, 0.25 + 0.3 * heat_ratio), 2)
            pos = round(random.uniform(0.1 + 0.1 * heat_ratio, 0.25 + 0.2 * heat_ratio), 2)
            neu = round(max(0.15, 1.0 - pos - neg), 2)

            # 平台扩散度：热度高时更多平台参与
            if count < 5:
                active_platforms = ["微博"]
            elif count < 20:
                active_platforms = random.choice([["微博", "知乎"], ["微博", "今日头条"]])
            else:
                active_platforms = ["微博", "知乎", "今日头条", "微信公众号"]

            plat_dist = {"微博": 0, "知乎": 0, "今日头条": 0, "微信公众号": 0}
            for plat in active_platforms:
                plat_dist[plat] = random.randint(0, count)

            records.append({
                "time": t,
                "news_count": count,
                "positive_ratio": pos,
                "negative_ratio": neg,
                "neutral_ratio": neu,
                "hot_score": round(min(count * 2.5 + random.uniform(-5, 5), 100), 1),
                "platform_distribution": plat_dist,
            })

        events.append({
            "event_id": f"EVT_{i+1:03d}",
            "event_title": titles_pool[i % len(titles_pool)],
            "category": categories[i % len(categories)],
            "start_time": base_time,
            "timeseries": records,
        })

    return events


def generate_mock_propagation_data() -> list[dict[str, Any]]:
    """
    生成模拟传播链路数据

    返回格式：
    [
      {
        "node_id": "N001",
        "account_name": "用户A",
        "follower_count": 粉丝数,
        "is_verified": 是否认证,
        "post_time": 发布时间,
        "source": "新浪新闻",           // 2号命名：来源媒体
        "parent_node_id": "N000" 或 null（源头节点为 null）,
        "forward_count": 被转发数,
        "title": "文章标题"             // 2号命名：标题
      },
      ...
    ]

    传播树结构示意：
      N001(原始爆料) → N002(转发) → N004(大V转发，引爆)
                   → N003(转发) → N005(官方媒体介入)
    """
    base_time = datetime(2026, 7, 4, 8, 0, 0)

    # 预定义传播树
    tree_definition = [
        # (node_id, account, followers, verified, offset_min, platform, parent_id, forwards)
        ("N001", "普通网友小王", 200, False, 0, "新浪新闻", None, 15),
        ("N002", "资讯搬运工", 5000, False, 30, "澎湃新闻", "N001", 80),
        ("N003", "深度观察员", 3000, False, 45, "央视新闻", "N001", 25),
        ("N004", "大V李教授", 500000, True, 90, "新浪新闻", "N002", 5000),
        ("N005", "新华网官方", 5000000, True, 120, "新浪新闻", "N004", 10000),
        ("N006", "财经频道", 200000, True, 150, "澎湃新闻", "N005", 3000),
        ("N007", "地方发布", 50000, True, 100, "央视新闻", "N004", 800),
    ]

    nodes: list[dict[str, Any]] = []
    for (nid, name, followers, verified, offset_min, source, parent, forwards) in tree_definition:
        nodes.append({
            "node_id": nid,
            "account_name": name,
            "follower_count": followers,
            "is_verified": verified,
            "post_time": base_time + timedelta(minutes=offset_min),
            "source": source,
            "parent_node_id": parent,
            "forward_count": forwards,
            "title": f"【{name}】对事件的" + ("首次曝光" if parent is None else "转发评论"),
        })

    return nodes


# ====== 自测 ======
if __name__ == "__main__":
    print("=" * 60)
    print("测试1：生成模拟舆情事件数据")
    print("=" * 60)
    events = generate_mock_events(num_events=1)
    evt = events[0]
    print(f"事件ID: {evt['event_id']}")
    print(f"标题: {evt['event_title']}")
    print(f"分类: {evt['category']}")
    print(f"数据记录数: {len(evt['records'])} 条（每小时一条）")
    print(f"时间范围: {evt['records'][0]['time']} ~ {evt['records'][-1]['time']}")
    print()
    print("每小时报道量（折线图预览）:")
    for r in evt["timeseries"][::4]:  # 每4小时打印一次
        bar = "█" * (r["news_count"] // 2)
        print(f"  {r['time'].strftime('%m/%d %H:%M')} | {r['article_count']:3d} 篇 {bar}")

    print()
    print("=" * 60)
    print("测试2：生成模拟传播链路数据")
    print("=" * 60)
    nodes = generate_mock_propagation_data()
    for n in nodes:
        indent = "  " * (0 if n["parent_node_id"] is None else 1)
        verified = "✓认证" if n["is_verified"] else ""
        parent_info = f"← 转发自 {n['parent_node_id']}" if n["parent_node_id"] else "（源头）"
        print(f"{indent}[{n['node_id']}] {n['account_name']} "
              f"粉丝:{n['follower_count']:,} {verified} "
              f"被转发:{n['forward_count']}次 {parent_info}")
