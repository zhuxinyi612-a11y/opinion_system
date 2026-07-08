"""阶段判定：信号合成 + EMA 平滑 + softmax 分类"""
from __future__ import annotations
import math
from typing import Any

STAGE_LATENT = "潜伏期"
STAGE_GROWING = "成长期"
STAGE_PEAK = "高潮期"
STAGE_DECLINING = "衰退期"
STAGE_RESURGENCE = "二次爆发"
STAGE_UNKNOWN = "未知"

# —— EMA 可调参数 ——
_EMA_ALPHA = 0.30       # 新数据权重（0=完全平滑不更新，1=不平滑）
_SOFTMAX_TEMP = 0.50    # softmax 温度（越小越尖锐，越大越均匀）


def _softmax(raw: dict[str, float], temperature: float = _SOFTMAX_TEMP) -> dict[str, float]:
    """温度缩放 softmax：temperature ↑ → 概率分布更均匀 → 阶段判定更稳定"""
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
    """三个统计信号 → raw score → EMA 平滑 → softmax → 四阶段概率

    和旧版的核心区别：
      - 旧：raw score 直接 softmax(temperature=0.15) → 极度尖锐，一小时波动就翻脸
      - 新：raw score 先 EMA 平滑(alpha=0.30) → softmax(temperature=0.50)
             → 阶段判定有"惯性"，不会因为一小时噪声横跳

    EMA 状态存储在 detector._ema_raw 中，按 event_id 分组避免不同事件互相污染。
    """
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

    # —— EMA 平滑 ——
    # 同一个事件连续调用 detect() 时（如按小时轮询），EMA 让阶段判定平滑过渡。
    # 事件 ID 变化时自动重置。
    event_id = getattr(detector, "_current_event_id", "")
    if not hasattr(detector, "_ema_raw"):
        detector._ema_raw = {}
    if event_id not in detector._ema_raw:
        detector._ema_raw[event_id] = {}

    ema_state = detector._ema_raw[event_id]
    alpha = getattr(detector, "ema_alpha", _EMA_ALPHA)
    smoothed = {}
    for stage_name in raw_scores:
        prev = ema_state.get(stage_name, raw_scores[stage_name])
        smoothed[stage_name] = alpha * raw_scores[stage_name] + (1 - alpha) * prev
    ema_state.update(smoothed)

    probs = _softmax(smoothed, temperature=_SOFTMAX_TEMP)
    stage = max(probs, key=lambda k: probs[k])
    return stage, probs
