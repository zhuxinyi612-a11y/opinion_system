"""
时序算法模块 (4号工程师)
========================
三个子模块：
  lifecycle/      — 舆情生命周期预测
  propagation/    — 事件传播溯源
  fake_detection/ — 虚假文本检测
  utils/          — 模拟数据生成
"""
from .lifecycle import LifecycleDetector
from .propagation import PropagationTracer
from .fake_detection import FakeDetector, FakeDetectorTrainer

__version__ = "0.2.0"
__all__ = ["LifecycleDetector", "PropagationTracer", "FakeDetector", "FakeDetectorTrainer"]
