"""阶段判定：信号合成 + softmax 分类"""
from __future__ import annotations
import math
from typing import Any

STAGE_LATENT = "潜伏期"
STAGE_GROWING = "成长期"
STAGE_PEAK = "高潮期"
STAGE_DECLINING = "衰退期"
STAGE_RESURGENCE = "二次爆发"
STAGE_UNKNOWN = "未知"


def _softmax(raw: dict[str, float], temperature: float = 0.15) -> dict[str, float]:
    scores = {k: v / temperature for k, v in raw.items()}
    max_score = max(scores.values())
    exp_scores = {k: math.exp(v - max_score) for k, v in scores.items()}
    total = sum(exp_scores.values())
    if total == 0:
        return {k: 0.25 for k in raw}
    return {k: round(v / total, 4) for k, v in exp_scores.items()}


def classify_stage(
    counts: list[int],
    trend_direction: str,
    current_level: float,
    detector: Any,  # LifecycleDetector instance
) -> tuple[str, dict[str, float]]:
    """三个统计信号 → softmax → 四阶段概率"""
    peak_count = max(counts)
    level_ratio = current_level / peak_count if peak_count > 0 else 0.0
    trend_slope, _ = detector._calc_trend(counts)
    normalized_trend = math.tanh(trend_slope * 2)
    time_ratio = min(1.0, len(counts) / max(72, len(counts)))

    raw_latent = (1 - level_ratio) * (1 - abs(normalized_trend)) * max(0, 1 - time_ratio)
    raw_growing = max(0, normalized_trend) * level_ratio * (1 - min(time_ratio, 0.5))
    raw_peak = level_ratio * (1 - abs(normalized_trend)) * min(time_ratio, 1 - time_ratio + 0.2)
    raw_declining = max(0, -normalized_trend) * (0.3 + 0.7 * time_ratio)

    if max(raw_latent, raw_growing, raw_peak, raw_declining) < 1e-6:
        raw_latent = 1.0

    raw_scores = {"潜伏期": raw_latent, "成长期": raw_growing, "高潮期": raw_peak, "衰退期": raw_declining}
    probs = _softmax(raw_scores)
    stage = max(probs, key=lambda k: probs[k])
    return stage, probs
