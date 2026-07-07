"""
舆情生命周期检测
================
根据时间序列数据，自动判断舆情事件处于哪个阶段：潜伏期 / 成长期 / 高潮期 / 衰退期

使用方式：
    from time_series.lifecycle import LifecycleDetector
    detector = LifecycleDetector()
    result = detector.detect(event_data)
"""
from .stage import STAGE_LATENT, STAGE_GROWING, STAGE_PEAK, STAGE_DECLINING, STAGE_RESURGENCE, STAGE_UNKNOWN
from .detector import LifecycleDetector

__all__ = [
    "LifecycleDetector",
    "STAGE_LATENT", "STAGE_GROWING", "STAGE_PEAK", "STAGE_DECLINING",
    "STAGE_RESURGENCE", "STAGE_UNKNOWN",
]
