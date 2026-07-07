import pandas as pd
import json
from pathlib import Path
from bs4 import BeautifulSoup
from readability import Document
import re

# ==========================================
# 1. 定位项目根目录和文件路径
# ==========================================
project_root = Path(__file__).parent.parent
json_file_path = project_root / 'test' / 'sample_data.json'
output_file_path = project_root / 'output' / 'extracted_data.csv'

print("=" * 60)
print("[第二步] 网页正文内容提取（去除HTML标签）")
print("=" * 60)

# ==========================================
# 2. 加载原始数据（复用上一步的加载逻辑）
# ==========================================
print(f"[INFO] 正在读取: {json_file_path}")

if not json_file_path.exists():
    print(f"[ERROR] 找不到文件！请确认 test/sample_data.json 存在。")
    exit()

with open(json_file_path, 'r', encoding='utf-8-sig') as f:
    raw_data = json.load(f)

df = pd.DataFrame(raw_data)
print(f"[DATA] 共加载 {len(df)} 条原始记录")

# ==========================================
# 3. 定义正文提取函数（核心算法）
# ==========================================
def extract_article_body(html_content, url=''):
    """
    从原始HTML中提取干净的标题和正文
    优先使用 readability-lxml，失败时降级为 BeautifulSoup
    """
    if not html_content or not isinstance(html_content, str):
        return {'title': '', 'body': ''}
    
    try:
        # 方案A：使用 Readability 算法（专门为新闻正文设计）
        doc = Document(html_content, url=url)
        
        # 提取标题
        title = doc.title() or ''
        
        # 提取正文HTML（Readability会自动去除广告、侧边栏）
        article_html = doc.summary()
        
        # 再用BeautifulSoup把提取结果中的残留标签去掉，转为纯文本
        soup = BeautifulSoup(article_html, 'lxml')
        body_text = soup.get_text()
        
        # 清洗多余换行和空格
        body_text = re.sub(r'\s+', ' ', body_text).strip()
        
        return {'title': title, 'body': body_text}
        
    except Exception as e:
        # 方案B：如果Readability失败，使用BeautifulSoup暴力去除所有标签
        print(f"   [WARN] Readability提取失败，使用备用方案: {str(e)[:50]}...")
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            # 移除 script 和 style 标签
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            text = re.sub(r'\s+', ' ', text).strip()
            return {'title': '', 'body': text}
        except:
            return {'title': '', 'body': ''}

# ==========================================
# 4. 对DataFrame的每一行执行提取
# ==========================================
print("\n[PROCESS] 开始提取正文（请稍候）...")

# 记录提取前后的长度，用于观察效果
df['html_length'] = df['html_content'].str.len()

# 应用提取函数
extracted = df['html_content'].apply(
    lambda html: extract_article_body(html, url='')
)

# 将提取结果拆分为两列
df['extracted_title'] = extracted.apply(lambda x: x['title'])
df['extracted_body'] = extracted.apply(lambda x: x['body'])

# 计算提取后的正文长度
df['body_length'] = df['extracted_body'].str.len()

# ==========================================
# 5. 打印提取效果对比
# ==========================================
print("\n[提取效果预览]")
for index, row in df.iterrows():
    print(f"\n--- 第 {index+1} 条: {row['title']} ---")
    print(f"  原始HTML长度: {row['html_length']} 字符")
    print(f"  提取后正文长度: {row['body_length']} 字符")
    # 提取后的内容预览（前60个字）
    preview = row['extracted_body'][:60] + "..." if len(row['extracted_body']) > 60 else row['extracted_body']
    print(f"  正文预览: {preview}")

# ==========================================
# 6. 保存提取结果到 output 文件夹
# ==========================================
# 确保 output 文件夹存在
output_file_path.parent.mkdir(parents=True, exist_ok=True)

# 保存为CSV（供后续3号和4号同事使用）
df.to_csv(output_file_path, index=False, encoding='utf-8-sig')
print(f"\n[OK] 提取完成！结果已保存至: {output_file_path}")

# 统计成功率
success_count = df[df['body_length'] > 10].shape[0]
print(f"[DATA] 提取成功率: {success_count}/{len(df)} 条 (正文长度 > 10 字符视为成功)")