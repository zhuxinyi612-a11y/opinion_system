"""
全局配置文件 - 所有参数集中管理
"""

from pathlib import Path

# ==========================================
# 1. 路径配置
# ==========================================
PROJECT_ROOT = Path(__file__).parent

INPUT_DIR = PROJECT_ROOT / 'input'
OUTPUT_DIR = PROJECT_ROOT / 'output'
TEST_DIR = PROJECT_ROOT / 'test'
STOPWORDS_DIR = PROJECT_ROOT / 'stopwords'
LOG_DIR = OUTPUT_DIR / 'logs'
REPORT_DIR = OUTPUT_DIR / 'reports'

# 确保所有目录存在
for dir_path in [INPUT_DIR, OUTPUT_DIR, LOG_DIR, REPORT_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ==========================================
# 2. 数据清洗配置
# ==========================================
MIN_TEXT_LENGTH = 30          # 正文最短长度（字符），低于此值视为无效
MAX_TEXT_LENGTH = 100000      # 正文最长长度（字符），超过此值可能含噪声

# ==========================================
# 3. 去重配置
# ==========================================
USE_SIMHASH = True            # 是否启用 SimHash 近重复检测
SIMHASH_THRESHOLD = 5         # SimHash 汉明距离阈值，<5 视为重复

# ==========================================
# 4. 分词配置
# ==========================================
MIN_WORD_LENGTH = 2           # 词语最短长度，过滤单字词
USE_POS_FILTER = False        # 是否启用词性过滤（只保留名词/动词/形容词）

# ==========================================
# 5. TF-IDF 配置
# ==========================================
TFIDF_MAX_FEATURES = 5000     # 最大特征数量
TFIDF_NGRAM_RANGE = (1, 2)    # n-gram 范围
TFIDF_MIN_DF = 2              # 词至少在几篇文档中出现才保留
TFIDF_MAX_DF = 0.95           # 词在多少比例文档中出现时忽略

# ==========================================
# 6. 情感分析配置
# ==========================================
SENTIMENT_THRESHOLD_POS = 0.65   # 情感得分 >= 此值视为正面
SENTIMENT_THRESHOLD_NEG = 0.35   # 情感得分 <= 此值视为负面

# ==========================================
# 7. 日志配置
# ==========================================
LOG_LEVEL = 'INFO'            # DEBUG / INFO / WARNING / ERROR
LOG_FILE = LOG_DIR / 'preprocess.log'

# ==========================================
# 8. 运行模式配置
# ==========================================
ENABLE_ADVANCED_ANALYSIS = True   # 是否启用高级分析（情感/摘要/实体）
ENABLE_REPORT = True              # 是否生成质量报告
ENABLE_PROGRESS_BAR = True        # 是否显示进度条

# ==========================================
# 9. 文件命名配置
# ==========================================
RAW_DATA_FILE = INPUT_DIR / 'raw_data.json'
LOADED_DATA_FILE = OUTPUT_DIR / 'loaded_data.csv'
EXTRACTED_DATA_FILE = OUTPUT_DIR / 'extracted_data.csv'
CLEANED_DATA_FILE = OUTPUT_DIR / 'cleaned_data.csv'
SEGMENTED_DATA_FILE = OUTPUT_DIR / 'segmented_data.csv'
ADVANCED_DATA_FILE = OUTPUT_DIR / 'advanced_analysis.csv'