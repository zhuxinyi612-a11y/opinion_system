# 舆情数据预处理模块

> 网络舆情事件智能分析系统 - 数据清洗与文本预处理模块

---

## 📖 模块简介

本模块是**网络舆情事件智能分析系统**的核心预处理部分，负责将原始网页数据转化为高质量的结构化文本数据，为后续的舆情分类、情感分析、趋势预测等任务提供可靠的数据基础。

**核心职责**：
- 从原始 HTML 中提取纯净正文
- 执行 18 项数据清洗操作
- 中文分词 + 停用词过滤
- TF-IDF 特征提取
- 情感分析、自动摘要、实体识别

---

## ✨ 功能特性

### 基础功能
- ✅ 多格式数据加载（JSON / CSV / Excel）
- ✅ 网页正文抽取（基于 readability-lxml）
- ✅ 空值处理与缺失值过滤
- ✅ 精确去重（MD5）
- ✅ 近重复检测（SimHash）
- ✅ 中文分词（jieba）
- ✅ 停用词过滤（自定义词表）
- ✅ 时间格式标准化
- ✅ TF-IDF 特征提取

### 高级功能
- ✅ 情感强度打分（0~1 连续值）
- ✅ 自动摘要生成（TextRank）
- ✅ 命名实体识别（人物/地点/机构）
- ✅ Emoji 清理
- ✅ 繁简体转换（OpenCC）
- ✅ 广告/版权声明清洗
- ✅ 自定义词典加载
- ✅ 低频词过滤
- ✅ 数据质量报告（HTML / JSON / TXT）
- ✅ 完整日志系统
- ✅ 进度条显示
- ✅ 一键运行全流程

---

## 📁 目录结构
yuqing_project/
├── config.py # 全局配置文件
├── requirements.txt # 依赖清单
├── .gitignore # Git 忽略规则
├── PROJECT_STRUCTURE.md # 详细项目结构文档
│
├── scripts/ # 可执行脚本
│ ├── run_all.py # 一键运行入口
│ ├── 01_load_data.py
│ ├── 02_extract_body.py
│ ├── 03_clean_deduplicate.py
│ ├── 04_segment.py
│ ├── 05_feature_extract.py
│ ├── 06_generate_report.py
│ └── 07_advanced_analysis.py
│
├── utils/ # 工具函数库
│ ├── cleaners.py # 18项清洗函数
│ ├── deduplicators.py # 去重工具
│ ├── tokenizers.py # 分词增强
│ ├── reporters.py # 报告生成
│ ├── validators.py # 数据验证
│ ├── progress.py # 进度条
│ └── logger.py # 日志配置
│
├── stopwords/ # 停用词与自定义词典
│ ├── hit_stopwords.txt
│ ├── extra_stopwords.txt
│ └── user_dict.txt
│
├── test/ # 测试数据
│ └── sample_data.json
│
├── input/ # 数据输入目录
└── output/ # 数据输出目录
├── logs/ # 日志
└── reports/ # 质量报告


> 详细结构说明请见 [`PROJECT_STRUCTURE.md`](./PROJECT_STRUCTURE.md)

---

## 🚀 快速开始

### 环境准备

```bash
# 激活 Conda 环境（推荐）
conda activate base

# 安装所有依赖
pip install -r requirements.txt

input/raw_data.json
        ↓
01_load_data.py     ← 加载原始数据
        ↓
02_extract_body.py  ← 正文提取（去HTML）
        ↓
03_clean_deduplicate.py ← 清洗去重（18项功能）
        ↓
04_segment.py       ← 中文分词 + 停用词过滤
        ↓
05_feature_extract.py ← TF-IDF 特征提取
        ↓
06_generate_report.py ← 生成质量报告
        ↓
07_advanced_analysis.py ← 情感/摘要/实体
        ↓
output/advanced_analysis.csv

🔌 接口说明
输入接口（来自 1号爬虫）
项目	说明
路径	input/raw_data.json
格式	JSON 数组
必填字段	html_content, title, publish_time, source

输出接口（供 3/4/5号 使用）
文件	用途	使用方
segmented_data.csv	分词后的文本	3号（NLP）
tfidf_matrix.npz	TF-IDF 特征矩阵	3号（NLP）
advanced_analysis.csv	情感+摘要+实体	4号（时序）+ 5号（前端）
reports/*.html	数据质量报告	课程设计报告
