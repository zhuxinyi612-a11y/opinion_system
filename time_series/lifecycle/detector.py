"""舆情生命周期检测器 — 主类"""
from __future__ import annotations
import math
from datetime import datetime
from typing import Any

from .stage import STAGE_DECLINING, STAGE_LATENT, STAGE_RESURGENCE, STAGE_UNKNOWN, classify_stage
from .fusion import remove_diurnal_cycle, compute_heat_index
from .forecast import forecast_holt
from .changepoint import find_turning_points
from .resurgence import detect_resurgence
from .critical import detect_critical_slowing_down


class LifecycleDetector:
    def __init__(self, window_size=6, growth_threshold=0.15,
                 decline_threshold=-0.10, peak_count_threshold=30, latent_count_threshold=5):
        self.window_size = window_size
        self.growth_threshold = growth_threshold
        self.decline_threshold = decline_threshold
        self.peak_count_threshold = peak_count_threshold
        self.latent_count_threshold = latent_count_threshold
        self._last_index_breakdown = {}

    def detect(self, event_data):
        records = event_data["records"]
        if not records:
            return {"event_id": event_data.get("event_id"), "current_stage": STAGE_UNKNOWN, "error": "没有数据"}

        counts = [r["article_count"] for r in records]
        times = [r["time"] for r in records]
        decycled_records, diurnal_info = remove_diurnal_cycle(records)
        composite_index = compute_heat_index(decycled_records, self)
        trend_slope, trend_direction = self._calc_trend(composite_index)
        current_level = self._calc_current_level(composite_index)
        critical_warning = detect_critical_slowing_down(composite_index)
        stage, probabilities = classify_stage(composite_index, trend_direction, current_level, self)
        resurgence_info = detect_resurgence(composite_index, times, stage)
        if resurgence_info["is_resurgence"]:
            stage = STAGE_RESURGENCE
            probs = probabilities.copy()
            probs["二次爆发"] = resurgence_info["confidence"]
            probs["衰退期"] = max(0, probs.get("衰退期", 0) - resurgence_info["confidence"])
            probabilities = probs
        turning_points = find_turning_points(composite_index, times, self)
        predicted = forecast_holt(composite_index, hours=24)

        return {
            "event_id": event_data.get("event_id", ""), "current_stage": stage,
            "stage_probabilities": probabilities, "trend_direction": trend_direction,
            "trend_slope": round(trend_slope, 2),
            "current_avg_count": round(self._calc_current_level(counts), 1),
            "current_heat_index": round(current_level, 1),
            "composite_index_breakdown": self._last_index_breakdown,
            "turning_points": turning_points, "predicted_next_24h": predicted,
            "total_duration_hours": len(records), "peak_count": max(counts),
            "peak_time": times[counts.index(max(counts))].strftime("%Y-%m-%d %H:%M"),
            "diurnal_cycle": diurnal_info, "resurgence": resurgence_info,
            "critical_early_warning": critical_warning,
        }

    def _calc_trend(self, counts):
        n = len(counts)
        if n < 2: return 0.0, "平稳"
        if n < self.window_size * 2:
            half = max(2, n // 2)
            recent, early = counts[-half:], counts[:half]
        else:
            recent = counts[-self.window_size:]
            early = counts[-(self.window_size * 2):-self.window_size]
        recent_avg = sum(recent) / len(recent)
        early_avg = sum(early) / len(early)
        denominator = max(early_avg, 0.5)
        if early_avg == 0 and recent_avg == 0: slope = 0.0
        elif early_avg == 0 and recent_avg > 0: slope = 2.0
        else: slope = (recent_avg - early_avg) / denominator
        if slope > self.growth_threshold: direction = "上升"
        elif slope < self.decline_threshold: direction = "下降"
        else: direction = "平稳"
        return slope, direction

    def _calc_current_level(self, counts):
        window = counts[-self.window_size:] if len(counts) >= self.window_size else counts
        return sum(window) / len(window)
