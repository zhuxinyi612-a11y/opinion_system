# 舆情数据预处理模块 - 项目结构文档

**项目名称**：网络舆情事件智能分析系统 - 数据预处理模块  
**负责人员**：2号 - 数据清洗与文本预处理  
**最后更新**：2026-07-07  
**版本**：v1.0


## 📁 完整目录结构
yuqing_project/
│
├── config.py # 🔧 全局配置文件
├── requirements.txt # 📦 Python 依赖清单
├── .gitignore # 🚫 Git 忽略文件
├── PROJECT_STRUCTURE.md # 📄 本文档
│
├── input/ # 📥 数据输入（1号爬虫放置数据）
│ └── raw_data.json
│
├── output/ # 📤 数据输出
│ ├── loaded_data.csv
│ ├── extracted_data.csv
│ ├── cleaned_data.csv
│ ├── segmented_data.csv
│ ├── advanced_analysis.csv
│ ├── tfidf_matrix.npz
│ ├── tfidf_vectorizer.joblib
│ ├── feature_names.txt
│ ├── logs/ # 📋 日志目录
│ └── reports/ # 📊 质量报告目录
│
├── scripts/ # 📜 可执行脚本
│ ├── run_all.py # 🚀 一键运行全流程
│ ├── 01_load_data.py
│ ├── 02_extract_body.py
│ ├── 03_clean_deduplicate.py
│ ├── 04_segment.py
│ ├── 05_feature_extract.py
│ ├── 06_generate_report.py
│ └── 07_advanced_analysis.py
│
├── stopwords/ # 📚 停用词与自定义词典
│ ├── hit_stopwords.txt
│ ├── extra_stopwords.txt
│ └── user_dict.txt
│
├── test/ # 🧪 测试数据
│ └── sample_data.json
│
└── utils/ # 🛠️ 工具函数库
├── init.py
├── cleaners.py # 18项清洗函数
├── deduplicators.py # 去重（MD5 + SimHash）
├── tokenizers.py # 分词增强
├── reporters.py # 报告生成
├── validators.py # 数据验证
├── progress.py # 进度条
└── logger.py # 日志配置



## 🔄 数据流转链路
input/raw_data.json
↓
01_load_data.py（加载）
↓
02_extract_body.py（正文提取）
↓
03_clean_deduplicate.py（清洗去重，18项功能）
↓
04_segment.py（分词 + 停用词过滤）
↓
05_feature_extract.py（TF-IDF特征提取）
↓
06_generate_report.py（质量报告）
↓
07_advanced_analysis.py（情感/摘要/实体）
↓
output/advanced_analysis.csv



## 🔌 接口说明

### 输入接口（1号 → 2号）
| 项目 | 说明 |
|------|------|
| 文件路径 | `input/raw_data.json` |
| 文件格式 | JSON 数组 |
| 必填字段 | `html_content`, `title`, `publish_time`, `source` |

### 输出接口（2号 → 3/4/5号）
| 文件 | 用途 | 使用方 |
|------|------|--------|
| `segmented_data.csv` | 分词后的文本 | 3号（NLP） |
| `tfidf_matrix.npz` | TF-IDF特征矩阵 | 3号（NLP） |
| `advanced_analysis.csv` | 情感+摘要+实体 | 4号（时序）+ 5号（前端） |
| `reports/*.html` | 数据质量报告 | 设计报告 |


## 🚀 使用方式

```bash
# 一键运行全流程
python scripts/run_all.py

# 从指定步骤开始
python scripts/run_all.py --from 03

# 跳过某些步骤
python scripts/run_all.py --skip 05 07