"""二次爆发检测"""
from __future__ import annotations
from datetime import datetime
from typing import Any

from .stage import STAGE_DECLINING, STAGE_LATENT


def detect_resurgence(
    composite_index: list[int], times: list[datetime], current_stage: str,
) -> dict[str, Any]:
    """检测衰退后的二次爆发（反转/续集/新料导致热度重新飙升）"""
    n = len(composite_index)
    if n < 12:
        return {"is_resurgence": False, "reason": "数据不足12个点"}
    if current_stage not in (STAGE_DECLINING, STAGE_LATENT):
        return {"is_resurgence": False, "reason": f"当前为{current_stage}"}

    first_half_end = int(n * 0.65)
    first_half = composite_index[:first_half_end]
    if not first_half:
        return {"is_resurgence": False, "reason": "数据不足以找第一轮峰值"}
    first_peak_idx = max(range(len(first_half)), key=lambda i: first_half[i])
    first_peak_value = first_half[first_peak_idx]

    if n - first_peak_idx < 12:
        return {"is_resurgence": False, "reason": "第一峰后数据不足"}

    post_first_peak = composite_index[first_peak_idx:]
    trough_rel_idx = min(range(len(post_first_peak)), key=lambda i: post_first_peak[i])
    trough_value = post_first_peak[trough_rel_idx]
    trough_idx = first_peak_idx + trough_rel_idx

    post_trough = composite_index[trough_idx:]
    post_trough_peak = max(post_trough)
    post_trough_peak_idx = trough_idx + post_trough.index(post_trough_peak)

    rebound_ratio = post_trough_peak / trough_value if trough_value > 0 else 99.0
    absolute_gain = post_trough_peak - trough_value
    is_significant = rebound_ratio >= 1.35
    is_meaningful = absolute_gain >= 8

    conditions = {"first_peak_in_front_half": first_peak_idx < n * 0.65, "significant_rebound": is_significant, "meaningful_absolute_gain": is_meaningful}

    if all(conditions.values()):
        rebound_score = min(1.0, (rebound_ratio - 1.0) / 3.0)
        gain_score = min(1.0, absolute_gain / 30.0)
        confidence = round(0.55 + 0.25 * rebound_score + 0.20 * gain_score, 3)
        return {
            "is_resurgence": True, "confidence": min(confidence, 0.95),
            "first_peak_time": times[first_peak_idx].strftime("%Y-%m-%d %H:%M"),
            "first_peak_value": first_peak_value,
            "trough_time": times[trough_idx].strftime("%Y-%m-%d %H:%M") if trough_idx < len(times) else "",
            "trough_value": trough_value,
            "second_peak_value": post_trough_peak,
            "second_peak_time": times[post_trough_peak_idx].strftime("%Y-%m-%d %H:%M") if post_trough_peak_idx < len(times) else "",
            "rebound_ratio": round(rebound_ratio, 2), "absolute_gain": round(absolute_gain, 1),
            "conditions": conditions,
            "interpretation": f"事件谷底({trough_value})后反弹至{post_trough_peak}，反弹倍率{rebound_ratio:.1f}x。",
        }

    return {"is_resurgence": False, "reason": f"条件不满足: {conditions}", "rebound_ratio": round(rebound_ratio, 2), "conditions": conditions}
