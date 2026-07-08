# 网络舆情事件智能分析系统 — 时序算法模块

4号工程师 | 舆情生命周期预测 + 传播溯源 + 虚假文本检测

## 项目结构

```
opinion_system/
├── time_series/
│   ├── lifecycle/                  # 舆情生命周期预测
│   │   ├── detector.py             #   主类 LifecycleDetector
│   │   ├── stage.py                #   阶段判定 + softmax
│   │   ├── fusion.py               #   多信号融合 + 日周期剥离
│   │   ├── forecast.py             #   Holt 指数平滑预测
│   │   ├── changepoint.py          #   PELT 变点检测
│   │   ├── resurgence.py           #   二次爆发检测
│   │   └── critical.py             #   临界减速预警
│   ├── propagation/                # 事件传播溯源
│   │   └── tracer.py               #   networkx + PageRank + 反事实推演
│   ├── fake_detection/             # 虚假文本检测
│   │   ├── __init__.py             #   FakeDetector + FakeDetectorTrainer
│   │   ├── ced_loader.py           #   CED 数据集加载器
│   │   └── graph_features.py       #   传播图拓扑特征提取
│   └── utils/
│       └── mock_data.py            # 模拟数据生成
├── docs/                           # 需求文档 & 分工方案
├── data/                           # 数据集 (gitignore)
├── demo.py                         # 一键演示
├── requirements.txt
└── .gitignore
```

## 快速开始

```bash
pip install -r requirements.txt
python demo.py
```

## 四个模块

| 模块 | 类 | 输入 | 输出 |
|------|-----|------|------|
| 生命周期 | `LifecycleDetector` | 按小时聚合的事件数据 | 阶段 + 概率 + 预测 + 预警 |
| 传播溯源 | `PropagationTracer` | 转发关系节点列表 | 传播图 + PageRank + 反事实 |
| 虚假检测 | `FakeDetector` | 文本 + 元数据 | 可信/待验证/疑似虚假 |
| 跨事件因果 | `CrossEventAnalyzer` | 多个事件的时间序列 | 格兰杰因果图 + p值 |

## 数据集

CED Dataset (清华大学 THUNLP), 3381条微博数据 (1533谣言 + 1848非谣言)

```bibtex
@article{song2018ced,
  title={CED: Credible Early Detection of Social Media Rumors},
  author={Song, Changhe and Tu, Cunchao and Yang, Cheng and Liu, Zhiyuan and Sun, Maosong},
  journal={arXiv preprint arXiv:1811.04175},
  year={2018}
}
```
