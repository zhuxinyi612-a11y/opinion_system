"""
事件传播溯源 & 传播路径构建
=========================
根据转发/引用关系，找出源头、关键节点、传播链路图。

使用方式：
    from time_series.propagation import PropagationTracer
    tracer = PropagationTracer()
    result = tracer.analyze(propagation_nodes)
"""
from .tracer import PropagationTracer

__all__ = ["PropagationTracer"]
