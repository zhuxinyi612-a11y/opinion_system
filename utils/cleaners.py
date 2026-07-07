"""
数据清洗工具函数
包含：Emoji清理、HTML实体修复、URL删除、敏感词替换、繁简体转换等
"""

import re
import html
import unicodedata
import emoji
from opencc import OpenCC

# ==========================================
# 1. Emoji 清理
# ==========================================
def remove_emoji(text: str) -> str:
    """移除所有 Emoji 表情符号"""
    if not text:
        return text
    try:
        return emoji.replace_emoji(text, '')
    except:
        # 降级方案：正则匹配
        emoji_pattern = re.compile(
            "["
            u"\U0001F600-\U0001F64F"  # 表情
            u"\U0001F300-\U0001F5FF"  # 符号
            u"\U0001F680-\U0001F6FF"  # 交通
            u"\U0001F1E0-\U0001F1FF"  # 国旗
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub('', text)


# ==========================================
# 2. HTML 实体修复
# ==========================================
def unescape_html(text: str) -> str:
    """将 &nbsp; &amp; &lt; &gt; 等转为正常字符"""
    if not text:
        return text
    return html.unescape(text)


# ==========================================
# 3. 异常字符修复（零宽字符等）
# ==========================================
def remove_invisible_chars(text: str) -> str:
    """移除零宽字符、不可见控制字符等"""
    if not text:
        return text
    # 移除零宽字符
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e\u2060-\u206f]', '', text)
    # 移除控制字符（保留换行和制表符）
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text


# ==========================================
# 4. URL 删除
# ==========================================
def remove_urls(text: str) -> str:
    """删除所有 URL 链接"""
    if not text:
        return text
    return re.sub(r'http\S+|www\S+|https\S+', '', text)


# ==========================================
# 5. 繁简体转换（台湾→大陆）
# ==========================================
def traditional_to_simplified(text: str) -> str:
    """繁体中文转简体中文"""
    if not text:
        return text
    try:
        cc = OpenCC('t2s')
        return cc.convert(text)
    except:
        return text


# ==========================================
# 6. 广告/版权声明清洗
# ==========================================
def remove_ads(text: str) -> str:
    """删除常见的广告、版权声明、责任编辑等"""
    if not text:
        return text
    
    patterns = [
        r'责任编辑[：:]\s*\S+',
        r'点击阅读[：:]\s*\S+',
        r'版权(所有|声明)[：:]\s*\S*',
        r'免责声明[：:]\s*\S*',
        r'猜你喜欢[：:]\s*\S*',
        r'相关阅读[：:]\s*\S*',
        r'来源[：:]\s*\S+',
        r'记者[：:]\s*\S+',
        r'通讯员[：:]\s*\S+',
        r'编辑[：:]\s*\S+',
        r'（责任编辑[：:]\s*\S+）',
        r'【[^】]*?广告[^】]*?】',
        r'本文系.*?原创',
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # 删除多余的空行
    text = re.sub(r'\n\s*\n', '\n', text)
    return text


# ==========================================
# 7. 敏感词替换（统一术语）
# ==========================================
def normalize_keywords(text: str) -> str:
    """统一关键词表述（如 AI → 人工智能）"""
    if not text:
        return text
    
    keyword_map = {
        'AI': '人工智能',
        'A.I.': '人工智能',
        'Artificial Intelligence': '人工智能',
        'ML': '机器学习',
        'Machine Learning': '机器学习',
        'DL': '深度学习',
        'Deep Learning': '深度学习',
        'NLP': '自然语言处理',
        'ChatGPT': '大语言模型',
        'GPT': '大语言模型',
        'covid-19': '新冠病毒',
        'COVID-19': '新冠病毒',
        'coronavirus': '新冠病毒',
    }
    
    for old, new in keyword_map.items():
        text = re.sub(old, new, text, flags=re.IGNORECASE)
    
    return text


# ==========================================
# 8. 中文数字统一
# ==========================================
def normalize_chinese_number(text: str) -> str:
    """将中文数字转为阿拉伯数字（简单版）"""
    if not text:
        return text
    
    num_map = {
        '零': '0', '一': '1', '二': '2', '三': '3', '四': '4',
        '五': '5', '六': '6', '七': '7', '八': '8', '九': '9',
        '十': '10', '百': '100', '千': '1000', '万': '10000', '亿': '100000000'
    }
    
    # 简单替换（复杂转换需要用 cn2an 库）
    for cn, num in num_map.items():
        text = text.replace(cn, num)
    
    return text


# ==========================================
# 9. 重复句删除
# ==========================================
def remove_duplicate_sentences(text: str) -> str:
    """删除文本中重复的句子"""
    if not text:
        return text
    
    # 按标点切分句子
    sentences = re.split(r'[。！？；]', text)
    # 去重（保留顺序）
    seen = set()
    unique_sentences = []
    for s in sentences:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            unique_sentences.append(s)
    
    return '。'.join(unique_sentences)


# ==========================================
# 10. 组合清洗函数（一键执行所有清洗）
# ==========================================
def clean_all(text: str) -> str:
    """执行所有清洗步骤"""
    if not text:
        return ""
    
    text = remove_emoji(text)              # 1. 移除emoji
    text = unescape_html(text)             # 2. HTML实体修复
    text = remove_invisible_chars(text)    # 3. 移除不可见字符
    text = remove_urls(text)               # 4. 删除URL
    text = traditional_to_simplified(text) # 5. 繁转简
    text = remove_ads(text)                # 6. 删除广告/版权
    text = normalize_keywords(text)        # 7. 关键词统一
    text = normalize_chinese_number(text)  # 8. 数字统一
    text = remove_duplicate_sentences(text)# 9. 删除重复句
    text = re.sub(r'\s+', ' ', text).strip() # 清理空白
    
    return text