"""
高级分析模块：情感强度打分 + 自动摘要 + 命名实体识别
用于提升数据质量，为3号、4号提供更丰富的特征
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import jieba.posseg as pseg
from textrank4zh import TextRank4Sentence
from snownlp import SnowNLP
import re
from collections import Counter

from config import OUTPUT_DIR, LOG_DIR
from utils import setup_logger

logger = setup_logger(LOG_DIR / '07_advanced_analysis.log')

# ==========================================
# 1. 情感强度打分（细粒度）
# ==========================================
def compute_sentiment_score(text: str) -> dict:
    """
    使用 SnowNLP 计算情感极性得分
    返回: {
        'polarity': 0~1 之间的浮点数（0最负面，1最正面），
        'sentiment_label': '正面' / '中性' / '负面'
    }
    """
    if not text or len(text) < 10:
        return {'polarity': 0.5, 'label': '中性'}
    
    try:
        # SnowNLP 返回 0~1 的值，0.5为中性阈值
        polarity = SnowNLP(text).sentiments
        
        # 映射为三分类标签
        if polarity >= 0.65:
            label = '正面'
        elif polarity <= 0.35:
            label = '负面'
        else:
            label = '中性'
        
        return {'polarity': polarity, 'label': label}
    except Exception as e:
        logger.warning(f"情感分析失败: {e}")
        return {'polarity': 0.5, 'label': '中性'}


# ==========================================
# 2. TextRank 自动摘要（抽取式）
# ==========================================
def generate_summary(text: str, max_sentences: int = 3) -> str:
    """
    使用 TextRank 算法提取关键句子作为摘要
    """
    if not text or len(text) < 20:
        return text[:50] if text else ''
    
    try:
        tr4s = TextRank4Sentence()
        tr4s.analyze(text, lower=True, source='all_filters')
        
        # 提取最重要的 max_sentences 个句子
        summary_sentences = tr4s.get_key_sentences(num=max_sentences)
        summary = '。'.join([item.sentence for item in summary_sentences])
        
        # 如果摘要太短或为空，降级为截取前50字
        if len(summary) < 20:
            return text[:50] + '...'
        
        return summary
    except Exception as e:
        logger.warning(f"摘要生成失败: {e}")
        return text[:50] + '...' if len(text) > 50 else text


# ==========================================
# 3. 命名实体识别（人物 / 地点 / 组织）
# ==========================================
def extract_entities(text: str) -> dict:
    """
    基于词性标注提取命名实体
    返回: {'persons': [], 'locations': [], 'orgs': []}
    """
    entities = {'persons': [], 'locations': [], 'orgs': []}
    
    if not text:
        return entities
    
    try:
        # 词性标注：nr=人名, ns=地名, nt=机构名, nz=专有名词
        for word, flag in pseg.cut(text):
            if flag == 'nr' and len(word) > 1:
                entities['persons'].append(word)
            elif flag == 'ns' and len(word) > 1:
                entities['locations'].append(word)
            elif flag in ['nt', 'nz'] and len(word) > 1:
                entities['orgs'].append(word)
        
        # 去重并统计高频实体（保留前5个）
        for key in entities:
            entities[key] = [item for item, _ in Counter(entities[key]).most_common(5)]
        
        return entities
    except Exception as e:
        logger.warning(f"实体提取失败: {e}")
        return entities


# ==========================================
# 4. 主处理流程
# ==========================================
def main():
    logger.info("=" * 60)
    logger.info("【高级分析模块】情感打分 + 摘要 + 实体识别")
    logger.info("=" * 60)
    
    # 加载上一步分词后的数据（包含 cleaned_body）
    input_file = OUTPUT_DIR / 'segmented_data.csv'
    
    if not input_file.exists():
        # 降级：如果 segmented_data.csv 不存在，尝试使用 cleaned_data.csv
        input_file = OUTPUT_DIR / 'cleaned_data.csv'
    
    if not input_file.exists():
        logger.error("❌ 未找到输入文件，请先运行 01-04 步骤")
        return
    
    df = pd.read_csv(input_file, encoding='utf-8-sig')
    logger.info(f"📊 共加载 {len(df)} 条数据")
    
    # 确定使用哪一列作为文本源
    text_col = 'cleaned_body' if 'cleaned_body' in df.columns else 'extracted_body'
    
    if text_col not in df.columns:
        logger.error(f"❌ 未找到文本列: {text_col}")
        return
    
    # ==========================================
    # 批量处理（显示进度条）
    # ==========================================
    logger.info("\n🔄 正在计算高级特征（可能需要几秒钟）...")
    
    sentiments = []
    summaries = []
    entities_list = []
    
    for idx, row in df.iterrows():
        text = row[text_col]
        
        # 1. 情感分析
        sentiment = compute_sentiment_score(text)
        sentiments.append(sentiment)
        
        # 2. 自动摘要
        summary = generate_summary(text, max_sentences=3)
        summaries.append(summary)
        
        # 3. 实体识别
        entities = extract_entities(text)
        entities_list.append(entities)
        
        # 每处理10条打印一次进度
        if (idx + 1) % 10 == 0:
            logger.info(f"   已处理 {idx+1}/{len(df)} 条")
    
    # ==========================================
    # 将结果添加到 DataFrame
    # ==========================================
    df['sentiment_polarity'] = [s['polarity'] for s in sentiments]
    df['sentiment_label'] = [s['label'] for s in sentiments]
    df['summary'] = summaries
    df['persons'] = [e['persons'] for e in entities_list]
    df['locations'] = [e['locations'] for e in entities_list]
    df['orgs'] = [e['orgs'] for e in entities_list]
    
    # ==========================================
    # 统计信息
    # ==========================================
    avg_polarity = df['sentiment_polarity'].mean()
    label_counts = df['sentiment_label'].value_counts()
    
    logger.info("\n【情感分布统计】")
    logger.info(f"   平均情感得分: {avg_polarity:.3f} (0~1, 越接近1越正面)")
    for label, count in label_counts.items():
        pct = count / len(df) * 100
        logger.info(f"   {label}: {count} 条 ({pct:.1f}%)")
    
    # 实体统计
    all_persons = [p for sublist in df['persons'] for p in sublist]
    all_locations = [l for sublist in df['locations'] for l in sublist]
    all_orgs = [o for sublist in df['orgs'] for o in sublist]
    
    logger.info("\n【高频实体 Top 5】")
    logger.info(f"   人物: {Counter(all_persons).most_common(5)}")
    logger.info(f"   地点: {Counter(all_locations).most_common(5)}")
    logger.info(f"   机构: {Counter(all_orgs).most_common(5)}")
    
    # ==========================================
    # 预览效果
    # ==========================================
    logger.info("\n【高级特征预览（前3条）】")
    for idx in range(min(3, len(df))):
        row = df.iloc[idx]
        logger.info(f"\n--- 第 {idx+1} 条: {row.get('title', '无标题')} ---")
        logger.info(f"   😊 情感得分: {row['sentiment_polarity']:.3f} ({row['sentiment_label']})")
        logger.info(f"   📝 摘要: {row['summary'][:60]}...")
        logger.info(f"   👤 人物: {row['persons']}")
        logger.info(f"   📍 地点: {row['locations']}")
        logger.info(f"   🏛️  机构: {row['orgs']}")
    
    # ==========================================
    # 保存增强后的数据
    # ==========================================
    output_file = OUTPUT_DIR / 'advanced_analysis.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    logger.info(f"\n✅ 高级分析完成！结果已保存至: {output_file}")
    
    logger.info(f"\n📋 新增字段: {['sentiment_polarity', 'sentiment_label', 'summary', 'persons', 'locations', 'orgs']}")


if __name__ == '__main__':
    main()