"""
第一步：数据加载模块
功能：读取 1号（爬虫）放在 input/ 目录下的原始数据
支持格式：JSON、CSV、Excel
"""

import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径（为了能导入 config）
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import json
from config import INPUT_DIR, OUTPUT_DIR, TEST_DIR, LOG_DIR
from utils import setup_logger

# 配置日志
logger = setup_logger(LOG_DIR / '01_load_data.log')

print("=" * 60)
print("[第一步] 数据加载（读取1号爬虫的数据）")
print("=" * 60)


def find_input_file():
    """
    智能查找输入文件：
    1. 优先读取 input/ 目录下 1号放的数据（任意 json/csv/xlsx）
    2. 如果没有，则使用 test/sample_data.json（自己测试用）
    """
    # 先看 input 文件夹
    input_files = list(INPUT_DIR.glob('*'))
    # 过滤出常见数据文件格式
    valid_suffix = ['.json', '.csv', '.xlsx', '.xls']
    data_files = [f for f in input_files if f.suffix.lower() in valid_suffix]
    
    if data_files:
        # 如果有多个，默认取第一个（建议1号只放一个，或命名为 raw_data.json）
        file_path = data_files[0]
        logger.info(f"[INFO] 发现输入文件: {file_path.name}")
        return file_path
    
    # 如果 input 为空，使用测试数据
    test_file = TEST_DIR / 'sample_data.json'
    if test_file.exists():
        logger.warning("[WARN] input/ 目录为空，使用测试数据 test/sample_data.json")
        return test_file
    
    # 啥都没有，报错
    logger.error("[ERROR] 没有找到任何输入数据！请让1号把数据放到 input/ 目录下")
    return None


def load_data(file_path: Path):
    """
    根据文件后缀自动加载数据
    """
    suffix = file_path.suffix.lower()
    
    try:
        if suffix == '.json':
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
        
        elif suffix == '.csv':
            df = pd.read_csv(file_path, encoding='utf-8-sig')
        
        elif suffix in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")
        
        logger.info(f"[OK] 成功加载数据！共 {len(df)} 条记录")
        logger.info(f"[INFO] 字段列表: {df.columns.tolist()}")
        return df
    
    except Exception as e:
        logger.error(f"[ERROR] 数据加载失败: {e}")
        return None


def main():
    # 1. 查找文件
    file_path = find_input_file()
    if not file_path:
        return
    
    # 2. 加载数据
    df = load_data(file_path)
    if df is None:
        return
    
    # 3. 验证必要字段（检查是否有 html_content，这是你后续处理必需的）
    if 'html_content' not in df.columns:
        logger.warning("[WARN] 数据中缺少 'html_content' 字段，请确认1号的数据格式")
        logger.info(f"[INFO] 当前字段: {df.columns.tolist()}")
    else:
        # 显示数据概况
        non_null = df['html_content'].notna().sum()
        logger.info(f"[INFO] 有效 html_content 记录: {non_null}/{len(df)}")
    
    # 4. 保存一份备份到 output（方便后续直接使用）
    backup_path = OUTPUT_DIR / 'loaded_data.csv'
    df.to_csv(backup_path, index=False, encoding='utf-8-sig')
    logger.info(f"[OK] 数据已缓存到: {backup_path}")
    
    print("\n[数据预览（前3条）]")
    for idx, row in df.head(3).iterrows():
        title = row.get('title', '无标题')[:30]
        print(f"  {idx+1}. {title}...")
    
    print("\n[SUCCESS] 数据加载完成，可以运行下一步（02_extract_body.py）了！")
    return df


if __name__ == '__main__':
    main()