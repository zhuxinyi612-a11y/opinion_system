import pandas as pd
import jieba
from pathlib import Path
# ==========================================
# 1. 定位项目根目录和文件路径
# ==========================================
project_root = Path(__file__).parent.parent
# 加载自定义词典（提高分词准确率）
user_dict_path = project_root / 'stopwords' / 'user_dict.txt'
if user_dict_path.exists():
    jieba.load_userdict(str(user_dict_path))
    print(f"[OK] 已加载自定义词典: {user_dict_path}")
# 输入：上一步清洗去重后的数据
input_file = project_root / 'output' / 'cleaned_data.csv'
# 停用词表路径
stopwords_file = project_root / 'stopwords' / 'hit_stopwords.txt'
# 输出：分词后的数据
output_file = project_root / 'output' / 'segmented_data.csv'

print("=" * 60)
print("[第四步] 中文分词与停用词过滤")
print("=" * 60)

# ==========================================
# 2. 加载清洗后的数据
# ==========================================
if not input_file.exists():
    print(f"[ERROR] 找不到文件: {input_file}")
    print("请先运行 03_clean_deduplicate.py 生成 cleaned_data.csv")
    exit()

df = pd.read_csv(input_file, encoding='utf-8-sig')
print(f"[DATA] 共加载 {len(df)} 条清洗后的数据")

# ==========================================
# 3. 加载停用词表
# ==========================================
print(f"\n[INFO] 正在加载停用词表: {stopwords_file}")

stopwords = set()
if stopwords_file.exists():
    with open(stopwords_file, 'r', encoding='utf-8') as f:
        for line in f:
            word = line.strip()
            if word:
                stopwords.add(word)
    print(f"[OK] 成功加载 {len(stopwords)} 个停用词")
else:
    print("[WARN] 停用词文件不存在！使用内置默认停用词列表（仅作演示）")
    stopwords = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都',
                 '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你',
                 '会', '着', '没有', '看', '好', '自己', '这', '那', '它', '他', '她'}

# ==========================================
# 4. 定义分词与过滤函数
# ==========================================
def segment_and_filter(text):
    if not isinstance(text, str) or len(text) == 0:
        return ""
    words = jieba.cut(text, cut_all=False)
    filtered_words = []
    for word in words:
        word = word.strip()
        if word and word not in stopwords and len(word) > 1:
            filtered_words.append(word)
    return ' '.join(filtered_words)

# ==========================================
# 5. 应用分词
# ==========================================
print("\n[PROCESS] 正在进行中文分词（可能需要几秒钟）...")
df['segmented'] = df['cleaned_body'].apply(segment_and_filter)
df['word_count'] = df['segmented'].str.split().str.len()
avg_word_count = df['word_count'].mean()
print(f"[OK] 分词完成！平均每条新闻提取 {avg_word_count:.1f} 个有效词语")

# ==========================================
# 6. 预览分词效果
# ==========================================
print("\n[分词效果预览]")
for index in range(min(3, len(df))):
    row = df.iloc[index]
    print(f"\n--- 第 {index+1} 条: {row.get('title', '无标题')} ---")
    print(f"  原文预览: {row['cleaned_body'][:30]}...")
    seg_preview = row['segmented'][:80] + "..." if len(row['segmented']) > 80 else row['segmented']
    print(f"  分词结果: {seg_preview}")
    print(f"  词语数量: {row['word_count']} 个")

# ==========================================
# 7. 保存分词结果
# ==========================================
df.to_csv(output_file, index=False, encoding='utf-8-sig')
print(f"\n[OK] 分词完成！结果已保存至: {output_file}")
print(f"\n[LIST] 输出文件包含字段: {df.columns.tolist()}")