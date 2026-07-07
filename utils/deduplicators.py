"""
去重工具：普通去重 + SimHash 近重复检测
"""

import hashlib
import re
from typing import List, Tuple

try:
    from simhash import Simhash
    SIMHASH_AVAILABLE = True
except ImportError:
    SIMHASH_AVAILABLE = False


def compute_md5(text: str) -> str:
    """计算 MD5 值"""
    if not text:
        return ''
    return hashlib.md5(text.encode('utf-8')).hexdigest()


class SimHashDeduplicator:
    """
    SimHash 近重复检测器
    阈值 < threshold 视为重复
    """
    
    def __init__(self, threshold: int = 5):
        self.threshold = threshold
        self.hashes = []
    
    def get_hash(self, text: str):
        """计算文本的 SimHash 值"""
        if not SIMHASH_AVAILABLE:
            return None
        try:
            clean = re.sub(r'\s+', ' ', text).strip()
            return Simhash(clean).value
        except:
            return None
    
    def is_duplicate(self, text: str) -> bool:
        """判断是否与已有文本近重复"""
        if not SIMHASH_AVAILABLE:
            return False
        
        hash_val = self.get_hash(text)
        if hash_val is None:
            return False
        
        for existing_hash in self.hashes:
            distance = bin(hash_val ^ existing_hash).count('1')
            if distance < self.threshold:
                return True
        
        self.hashes.append(hash_val)
        return False


def deduplicate(df, text_column: str = 'cleaned_body', use_simhash: bool = True, threshold: int = 5):
    """
    组合去重：先 MD5 精确去重，再 SimHash 近重复检测
    """
    if text_column not in df.columns:
        return df
    
    # 1. MD5 精确去重
    df['md5'] = df[text_column].apply(compute_md5)
    df = df.drop_duplicates(subset=['md5'], keep='first')
    
    # 2. SimHash 近重复检测
    if use_simhash and SIMHASH_AVAILABLE:
        deduper = SimHashDeduplicator(threshold=threshold)
        mask = []
        for text in df[text_column]:
            is_dup = deduper.is_duplicate(text)
            mask.append(not is_dup)
        df = df[mask]
    
    df = df.drop(columns=['md5'])
    return df