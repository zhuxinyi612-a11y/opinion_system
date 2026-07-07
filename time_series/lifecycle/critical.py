"""临界减速预警 (Critical Slowing Down)"""
from __future__ import annotations
from typing import Any

import numpy as np


def detect_critical_slowing_down(composite_index: list[int]) -> dict[str, Any]:
    """复杂系统相变前兆检测：方差比 + AR(1)自相关 + 恢复速度"""
    n = len(composite_index)
    if n < 20:
        return {"warning_level": "none", "reason": "数据不足20点"}

    window = min(12, n // 3)
    recent = composite_index[-window:]
    recent_arr = np.array(recent, dtype=float)

    recent_var = float(np.var(recent_arr))
    if n >= 2 * window:
        baseline_segment = composite_index[-(2 * window):-window]
    else:
        baseline_segment = composite_index[: n - window]
    baseline_var = float(np.var(np.array(baseline_segment, dtype=float))) if baseline_segment else 1.0
    if baseline_var < 0.5:
        baseline_var = 1.0
    variance_ratio = recent_var / baseline_var

    if len(recent_arr) >= 4:
        y_t, y_t1 = recent_arr[1:], recent_arr[:-1]
        y_m = float(np.mean(recent_arr))
        cov = float(np.mean((y_t - y_m) * (y_t1 - y_m)))
        var_y = float(np.var(recent_arr))
        ar1 = cov / var_y if var_y > 0.01 else 0.0
    else:
        ar1 = 0.0

    recovery_lag = 0
    for i in range(len(recent) - 1, max(0, len(recent) - window), -1):
        if i > 0 and abs(composite_index[-1] - composite_index[i]) < 0.3 * recent_arr[-1]:
            recovery_lag += 1
        else:
            break

    if variance_ratio > 3.0 and ar1 > 0.5:
        level, msg = "red", f"CRITICAL: 方差飙升{variance_ratio:.1f}x + 自相关增强{ar1:.2f}。系统高度不稳定。"
    elif variance_ratio > 2.5 or (variance_ratio > 1.5 and ar1 > 0.4):
        level, msg = "orange", f"WARNING: 方差比{variance_ratio:.1f}x，自相关{ar1:.2f}。系统逼近临界点。"
    elif variance_ratio > 1.5 or ar1 > 0.35:
        level, msg = "yellow", f"注意：方差比{variance_ratio:.1f}x，系统开始不稳定。"
    else:
        level, msg = "none", ""

    return {"warning_level": level, "variance_ratio": round(variance_ratio, 2), "ar1_coefficient": round(ar1, 3), "recovery_lag": recovery_lag, "window_size": window, "message": msg, "conditions": {"variance_ratio": {"value": round(variance_ratio, 2), "threshold_orange": 2.0, "threshold_red": 3.0}, "ar1_coefficient": {"value": round(ar1, 3), "threshold_orange": 0.5, "threshold_red": 0.7}}}
