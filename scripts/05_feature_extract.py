"""
第五步：TF-IDF 特征提取
增强版：自动检测语料质量，提供详细错误信息
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
import scipy.sparse
import joblib

from config import OUTPUT_DIR
from utils import setup_logger

logger = setup_logger(OUTPUT_DIR / 'logs' / '05_feature_extract.log')

print("=" * 60)
print("[第五步] TF-IDF 特征提取（文本向量化）")
print("=" * 60)

# ==========================================
# 1. 加载分词后的数据
# ==========================================
input_file = OUTPUT_DIR / 'segmented_data.csv'

if not input_file.exists():
    print(f"[ERROR] 找不到文件: {input_file}")
    print("请先运行 04_segment.py 生成 segmented_data.csv")
    sys.exit(1)

df = pd.read_csv(input_file, encoding='utf-8-sig')
print(f"[DATA] 共加载 {len(df)} 条分词后的数据")

# ==========================================
# 2. 检查 segmented 列是否存在
# ==========================================
if 'segmented' not in df.columns:
    print("[ERROR] DataFrame 中缺少 'segmented' 列")
    print(f"[INFO] 当前列: {df.columns.tolist()}")
    sys.exit(1)

# ==========================================
# 3. 准备语料库
# ==========================================
corpus = df['segmented'].fillna('').tolist()

# 检查语料是否为空
empty_count = sum(1 for text in corpus if len(text.strip()) == 0)
print(f"[INFO] 空文本数量: {empty_count}/{len(corpus)}")

if empty_count == len(corpus):
    print("[ERROR] 所有文本分词结果都为空！")
    print("请检查 04_segment.py 是否正确运行，或检查 cleaned_body 列是否有内容")
    sys.exit(1)

# ==========================================
# 4. 显示语料样例
# ==========================================
print("\n[语料样例（前3条）]")
for i, text in enumerate(corpus[:3]):
    preview = text[:80] + "..." if len(text) > 80 else text
    print(f"  {i+1}. {preview}")

# ==========================================
# 5. 创建 TF-IDF 向量化器
# ==========================================
print("\n[PROCESS] 正在计算 TF-IDF 特征...")

vectorizer = TfidfVectorizer(
    max_features=5000,
    ngram_range=(1, 2),
    min_df=1,
    max_df=0.95
)

try:
    tfidf_matrix = vectorizer.fit_transform(corpus)
except Exception as e:
    print(f"[ERROR] TF-IDF 计算失败: {e}")
    sys.exit(1)

# ==========================================
# 6. 统计信息
# ==========================================
print(f"\n[OK] TF-IDF 矩阵生成成功！")
print(f"   [DATA] 矩阵形状: {tfidf_matrix.shape}")
print(f"   [DATA] 文档数量: {tfidf_matrix.shape[0]} 篇")
print(f"   [DATA] 特征数量: {tfidf_matrix.shape[1]} 个")

# ==========================================
# 7. 保存文件
# ==========================================
# 保存稀疏矩阵
matrix_path = OUTPUT_DIR / 'tfidf_matrix.npz'
scipy.sparse.save_npz(matrix_path, tfidf_matrix)
print(f"[OK] TF-IDF 矩阵已保存至: {matrix_path}")

# 保存向量化器
vectorizer_path = OUTPUT_DIR / 'tfidf_vectorizer.joblib'
joblib.dump(vectorizer, vectorizer_path)
print(f"[OK] 向量化器已保存至: {vectorizer_path}")

# 保存特征名称
feature_names = vectorizer.get_feature_names_out()
feature_path = OUTPUT_DIR / 'feature_names.txt'
with open(feature_path, 'w', encoding='utf-8') as f:
    for name in feature_names:
        f.write(name + '\n')
print(f"[OK] 特征名称已保存至: {feature_path}")

print("\n[SUCCESS] TF-IDF 特征提取完成！")