"""
第三步：数据清洗与预处理（完整版）
涵盖 18 项高级功能，配置化、带验证和进度显示
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import logging
from datetime import datetime

from config import (
    OUTPUT_DIR, LOG_DIR, STOPWORDS_DIR, REPORT_DIR,
    MIN_TEXT_LENGTH, USE_SIMHASH, SIMHASH_THRESHOLD,
    ENABLE_ADVANCED_ANALYSIS, ENABLE_REPORT, ENABLE_PROGRESS_BAR
)
from utils.cleaners import clean_all, remove_ads, normalize_keywords
from utils.deduplicators import deduplicate
from utils.tokenizers import EnhancedTokenizer, filter_low_freq_terms
from utils.reporters import generate_quality_report
from utils.validators import validate_dataframe, assert_data_quality, check_text_quality
from utils.progress import process_with_progress, ProgressTracker

# ==========================================
# 配置日志
# ==========================================
LOG_FILE = LOG_DIR / '03_clean_deduplicate.log'
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def log_info(msg):
    print(msg)
    logging.info(msg)

print("=" * 60)
print("[第三步] 数据清洗与预处理（完整版）")
print("=" * 60)

# ==========================================
# 1. 加载数据
# ==========================================
input_file = OUTPUT_DIR / 'extracted_data.csv'
if not input_file.exists():
    log_info(f"[ERROR] 找不到文件: {input_file}")
    sys.exit(1)

df = pd.read_csv(input_file, encoding='utf-8-sig')
log_info(f"[DATA] 共加载 {len(df)} 条数据")

original_count = len(df)
stats = {}

# ==========================================
# 2. 验证数据
# ==========================================
valid, msg = validate_dataframe(df, ['title', 'extracted_body'], min_rows=1, name="原始数据")
if not valid:
    log_info(f"[ERROR] {msg}")
    sys.exit(1)

# ==========================================
# 3. 删除空数据
# ==========================================
before = len(df)
df = df.dropna(subset=['title', 'extracted_body'])
df = df[df['extracted_body'].str.strip() != '']
stats['删除空值'] = before - len(df)
log_info(f"[OK] 删除空值: {stats['删除空值']} 条")

# ==========================================
# 4. 时间标准化
# ==========================================
if 'publish_time' in df.columns:
    df['publish_time'] = pd.to_datetime(df['publish_time'], errors='coerce')
    df = df.dropna(subset=['publish_time'])
    df['publish_time'] = df['publish_time'].dt.strftime('%Y-%m-%d %H:%M:%S')

# ==========================================
# 5. 执行综合清洗
# ==========================================
log_info("[PROCESS] 执行综合清洗...")
# 可选用进度条
if ENABLE_PROGRESS_BAR:
    results = process_with_progress(
        df['extracted_body'].tolist(),
        clean_all,
        desc="清洗文本"
    )
    df['cleaned_body'] = results
else:
    df['cleaned_body'] = df['extracted_body'].apply(clean_all)

stats['清洗后'] = len(df)

# ==========================================
# 6. 文本长度过滤
# ==========================================
before = len(df)
df = df[df['cleaned_body'].str.len() >= MIN_TEXT_LENGTH]
stats['删除过短文本'] = before - len(df)

# ==========================================
# 7. 数据质量验证（清洗后）
# ==========================================
try:
    assert_data_quality(df, 'cleaned_body', min_length=MIN_TEXT_LENGTH)
    log_info("[OK] 数据质量验证通过")
except ValueError as e:
    log_info(f"[ERROR] 数据质量验证失败: {e}")
    sys.exit(1)

# ==========================================
# 8. 组合去重（MD5 + SimHash）
# ==========================================
before = len(df)
df = deduplicate(df, 'cleaned_body', use_simhash=USE_SIMHASH, threshold=SIMHASH_THRESHOLD)
stats['删除重复'] = before - len(df)

# ==========================================
# 9. 加载停用词
# ==========================================
stopwords = set()
stopwords_file = STOPWORDS_DIR / 'hit_stopwords.txt'
if stopwords_file.exists():
    with open(stopwords_file, 'r', encoding='utf-8') as f:
        stopwords = set(f.read().splitlines())
    log_info(f"[OK] 加载 {len(stopwords)} 个停用词")

# 扩展停用词
extra_file = STOPWORDS_DIR / 'extra_stopwords.txt'
if extra_file.exists():
    with open(extra_file, 'r', encoding='utf-8') as f:
        extra = set(f.read().splitlines())
        stopwords.update(extra)
        log_info(f"[OK] 扩展停用词 {len(extra)} 个，总计 {len(stopwords)} 个")

# ==========================================
# 10. 分词（带自定义词典）
# ==========================================
user_dict = STOPWORDS_DIR / 'user_dict.txt'
tokenizer = EnhancedTokenizer(stopwords, user_dict)

log_info("[PROCESS] 开始分词...")
if ENABLE_PROGRESS_BAR:
    seg_results = process_with_progress(
        df['cleaned_body'].tolist(),
        lambda x: ' '.join(tokenizer.segment(x, pos_filter=False)),
        desc="分词"
    )
    df['segmented'] = seg_results
else:
    df['segmented'] = df['cleaned_body'].apply(
        lambda x: ' '.join(tokenizer.segment(x, pos_filter=False))
    )

df['word_count'] = df['segmented'].str.split().str.len()

# ==========================================
# 11. 低频词过滤
# ==========================================
df = filter_low_freq_terms(df, 'segmented', min_df=2)

# ==========================================
# 12. 保存结果
# ==========================================
output_file = OUTPUT_DIR / 'cleaned_data.csv'
df.to_csv(output_file, index=False, encoding='utf-8-sig')
log_info(f"[OK] 清洗完成！保存至: {output_file}")

# ==========================================
# 13. 生成质量报告
# ==========================================
if ENABLE_REPORT:
    report_path = REPORT_DIR / 'quality_report'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    generate_quality_report(
        pd.DataFrame({'count': [original_count]}),
        df,
        stats,
        report_path
    )
    log_info(f"[OK] 质量报告已生成: {report_path}")

# ==========================================
# 14. 最终统计
# ==========================================
log_info(f"\n[最终统计]")
log_info(f"  原始数据: {original_count} 条")
log_info(f"  清洗后: {len(df)} 条")
log_info(f"  删除率: {(original_count - len(df)) / original_count * 100:.1f}%")
log_info(f"  平均词数: {df['word_count'].mean():.1f}")
log_info(f"  日志文件: {LOG_FILE}")

# 打印前3条预览
print("\n[预览前3条]")
for idx in range(min(3, len(df))):
    row = df.iloc[idx]
    print(f"  {idx+1}. {row.get('title', '无标题')[:30]}...")