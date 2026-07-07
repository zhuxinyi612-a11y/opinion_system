"""PELT 变点检测"""
from __future__ import annotations
from datetime import datetime
from typing import Any

import numpy as np


def find_turning_points(counts: list[int], times: list[datetime], detector: Any) -> list[dict[str, Any]]:
    """PELT算法检测阶段切换点，<10点回退差分法"""
    n = len(counts)
    if n < 3:
        return []
    if n < 10:
        return _find_turning_points_legacy(counts, times)

    try:
        import ruptures as rpt
        signal = np.array(counts, dtype=float)
        std_est = max(float(np.std(signal)), 1.0)
        pen = 1.5 * np.log(n) * (std_est ** 2)
        algo = rpt.Pelt(model="l2").fit(signal)
        change_points = [cp for cp in algo.predict(pen=pen) if cp < n]
        if not change_points:
            return []

        result = []
        for cp in change_points:
            if cp == 0:
                continue
            idx = cp - 1
            before = signal[max(0, idx - 3):idx + 1]
            after = signal[idx:min(n, idx + 4)]
            bm = float(np.mean(before)) if len(before) > 0 else signal[idx]
            am = float(np.mean(after)) if len(after) > 0 else signal[idx]
            if bm > am + 2: pt_type = "峰值（转入下降）"
            elif am > bm + 2: pt_type = "谷底（转入上升）"
            else: pt_type = "拐点"
            result.append({"time": times[idx].strftime("%Y-%m-%d %H:%M") if idx < len(times) else "", "count": int(signal[idx]), "type": pt_type, "method": "PELT"})
        return result[-5:]
    except ImportError:
        return _find_turning_points_legacy(counts, times)


def _find_turning_points_legacy(counts: list[int], times: list[datetime]) -> list[dict[str, Any]]:
    result = []
    prev_diff = counts[1] - counts[0]
    for i in range(2, len(counts)):
        curr_diff = counts[i] - counts[i - 1]
        if (prev_diff > 2 and curr_diff < -2) or (prev_diff < -2 and curr_diff > 2):
            result.append({"time": times[i].strftime("%Y-%m-%d %H:%M"), "count": counts[i], "type": "峰值" if prev_diff > 0 else "谷底", "method": "legacy"})
        prev_diff = curr_diff
    return result[-5:]
