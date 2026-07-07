"""多信号融合 & 日周期剥离"""
from __future__ import annotations
from typing import Any


def remove_diurnal_cycle(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """剥离24小时昼夜波动，返回 (decycled_records, diurnal_info)"""
    n = len(records)
    if n < 24:
        return records, {"has_cycle": False, "reason": "数据不足24小时", "peak_hour": None, "trough_hour": None, "amplitude": 0.0}

    hourly_sum = [0.0] * 24
    hourly_count = [0] * 24
    for r in records:
        h = r["time"].hour
        hourly_sum[h] += r.get("article_count", 0)
        hourly_count[h] += 1

    hourly_avg = [hourly_sum[h] / hourly_count[h] if hourly_count[h] > 0 else 0.0 for h in range(24)]
    overall_avg = sum(hourly_avg) / 24.0
    if overall_avg < 0.5:
        return records, {"has_cycle": False, "reason": "报道量极低", "peak_hour": None, "trough_hour": None, "amplitude": 0.0}

    hourly_factor = [hourly_avg[h] / overall_avg if overall_avg > 0 else 1.0 for h in range(24)]
    peak_hour = max(range(24), key=lambda h: hourly_factor[h])
    trough_hour = min(range(24), key=lambda h: hourly_factor[h])
    amplitude = hourly_factor[peak_hour] - hourly_factor[trough_hour]

    if amplitude < 0.15:
        return records, {"has_cycle": False, "reason": f"日周期振幅仅 {amplitude:.2f}", "peak_hour": peak_hour, "trough_hour": trough_hour, "amplitude": round(amplitude, 3), "hourly_factors": [round(f, 3) for f in hourly_factor]}

    decycled = []
    for r in records:
        factor = hourly_factor[r["time"].hour] if hourly_factor[r["time"].hour] > 0.1 else 1.0
        rec = dict(r)
        rec["article_count"] = int(round(r.get("article_count", 0) / factor))
        rec["_raw_article_count"] = r.get("article_count", 0)
        rec["_diurnal_factor"] = round(factor, 3)
        decycled.append(rec)

    return decycled, {"has_cycle": True, "peak_hour": peak_hour, "peak_factor": round(hourly_factor[peak_hour], 3), "trough_hour": trough_hour, "trough_factor": round(hourly_factor[trough_hour], 3), "amplitude": round(amplitude, 3), "hourly_factors": [round(f, 3) for f in hourly_factor]}


def compute_heat_index(records: list[dict[str, Any]], detector: Any) -> list[int]:
    """四维信号融合为综合热度指数 (0~100)，结果存入 detector._last_index_breakdown"""
    n = len(records)
    if n == 0:
        return []

    raw_volume = [r.get("article_count", 0) for r in records]
    raw_sentiment = []
    for r in records:
        pos = r.get("sentiment_positive_ratio", 0.33)
        neg = r.get("sentiment_negative_ratio", 0.33)
        raw_sentiment.append(1.0 - abs(pos - neg))
    raw_spread = []
    for r in records:
        pdist = r.get("platform_distribution", {})
        raw_spread.append(sum(1 for v in pdist.values() if v > 0) if isinstance(pdist, dict) else 1)
    raw_engagement = [r.get("avg_heat_score", 0) for r in records]

    def _norm(vals, default_max=1.0):
        vmax = max(max(vals), default_max)
        return [min(v / vmax * 100, 100) for v in vals] if vmax > 0 else [0.0] * len(vals)

    nv = _norm(raw_volume, 50)
    ns = [v * 100 for v in raw_sentiment]
    np_ = _norm(raw_spread, 4)
    ne = [min(v, 100) for v in raw_engagement]

    w = {"volume": 0.40, "sentiment_volatility": 0.25, "platform_spread": 0.20, "engagement": 0.15}
    composite = [int(round(w["volume"] * nv[i] + w["sentiment_volatility"] * ns[i] + w["platform_spread"] * np_[i] + w["engagement"] * ne[i])) for i in range(n)]

    detector._last_index_breakdown = {"volume": round(nv[-1], 1), "sentiment_volatility": round(ns[-1], 1), "platform_spread": round(np_[-1], 1), "engagement": round(ne[-1], 1), "composite": composite[-1]}
    return composite
