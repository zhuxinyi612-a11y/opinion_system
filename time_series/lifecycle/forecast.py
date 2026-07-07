"""Holt 双指数平滑预测"""
from __future__ import annotations
import math
from typing import Any


def forecast_holt(counts: list[int], hours: int = 24, alpha: float = 0.3, beta: float = 0.1) -> list[dict[str, Any]]:
    """Holt双指数平滑，返回未来N小时预测 + 95%置信区间"""
    n = len(counts)
    if n < 2:
        return []

    level = float(counts[0])
    trend = float(counts[1] - counts[0])
    levels = [level]

    for t in range(1, n):
        y = float(counts[t])
        prev = level
        level = alpha * y + (1 - alpha) * (level + trend)
        trend = beta * (level - prev) + (1 - beta) * trend
        levels.append(level)

    residuals = [float(counts[i]) - levels[i] for i in range(n)]
    residual_std = math.sqrt(sum(r * r for r in residuals) / (n - 1)) if n > 1 else 0.0

    predicted = []
    for h in range(1, hours + 1):
        val = max(0, level + h * trend)
        pred_std = residual_std * math.sqrt(1 + h / n)
        predicted.append({
            "hours_from_now": h,
            "predicted_count": round(val, 1),
            "lower_bound": round(max(0, val - 1.96 * pred_std), 1),
            "upper_bound": round(max(0, val + 1.96 * pred_std), 1),
        })
    return predicted
