"""
数据验证模块 - 在关键步骤后检查数据质量
"""

import pandas as pd
from typing import Tuple, Optional


def validate_dataframe(
    df: pd.DataFrame,
    expected_columns: list,
    min_rows: int = 1,
    name: str = "数据"
) -> Tuple[bool, str]:
    """
    验证 DataFrame 是否满足基本要求
    
    返回: (是否通过, 错误信息)
    """
    if df is None:
        return False, f"{name} 为空"
    
    if len(df) == 0:
        return False, f"{name} 为空（0 行）"
    
    if min_rows > 0 and len(df) < min_rows:
        return False, f"{name} 行数过少: {len(df)} < {min_rows}"
    
    missing_cols = [col for col in expected_columns if col not in df.columns]
    if missing_cols:
        return False, f"{name} 缺少必要列: {missing_cols}"
    
    return True, "验证通过"


def check_text_quality(
    df: pd.DataFrame,
    text_column: str = 'cleaned_body',
    min_length: int = 10
) -> dict:
    """
    检查文本质量，返回统计信息
    """
    if text_column not in df.columns:
        return {"error": f"列 '{text_column}' 不存在"}
    
    texts = df[text_column].fillna('').astype(str)
    
    return {
        "总记录数": len(df),
        "空文本数": (texts == '').sum(),
        "短文本数": (texts.str.len() < min_length).sum(),
        "平均长度": texts.str.len().mean(),
        "最大长度": texts.str.len().max(),
        "最小长度": texts.str.len().min(),
    }


def assert_data_quality(
    df: pd.DataFrame,
    text_column: str = 'cleaned_body',
    min_length: int = 10,
    min_non_empty_ratio: float = 0.5
) -> None:
    """
    断言数据质量，不满足条件时抛出异常
    """
    if text_column not in df.columns:
        raise ValueError(f"列 '{text_column}' 不存在")
    
    texts = df[text_column].fillna('').astype(str)
    non_empty = (texts != '').sum()
    ratio = non_empty / len(df) if len(df) > 0 else 0
    
    if ratio < min_non_empty_ratio:
        raise ValueError(
            f"数据质量不合格: 非空文本比例 {ratio:.1%} < {min_non_empty_ratio:.1%}"
        )
    
    valid_texts = texts[texts.str.len() >= min_length]
    if len(valid_texts) < len(df) * min_non_empty_ratio:
        raise ValueError(
            f"数据质量不合格: 有效文本比例 {len(valid_texts)/len(df):.1%} < {min_non_empty_ratio:.1%}"
        )