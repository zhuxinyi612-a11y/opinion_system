"""
数据质量报告生成器
自动生成清洗前后的统计报告，可用于课程设计报告
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import pandas as pd


def generate_quality_report(
    df_original: pd.DataFrame,
    df_cleaned: pd.DataFrame,
    stats: Dict[str, int],
    output_path: Path
) -> str:
    """
    生成数据质量报告（JSON + 文本 双格式）
    """
    
    report = {
        "report_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "summary": {
            "原始数据": len(df_original),
            "清洗后数据": len(df_cleaned),
            "删除总数": len(df_original) - len(df_cleaned),
            "删除率": f"{(len(df_original) - len(df_cleaned)) / len(df_original) * 100:.1f}%"
        },
        "清洗详情": stats,
        "数据质量": {
            "平均正文长度": round(df_cleaned['cleaned_body'].str.len().mean(), 1),
            "平均分词数量": round(df_cleaned.get('word_count', pd.Series([0])).mean(), 1),
            "时间跨度": {}
        }
    }
    
    # 时间跨度
    if 'publish_time' in df_cleaned.columns:
        try:
            times = pd.to_datetime(df_cleaned['publish_time'])
            report["数据质量"]["时间跨度"] = {
                "开始": times.min().strftime('%Y-%m-%d'),
                "结束": times.max().strftime('%Y-%m-%d'),
                "天数": (times.max() - times.min()).days
            }
        except:
            pass
    
    # 来源分布（如果有）
    if 'source' in df_cleaned.columns:
        sources = df_cleaned['source'].value_counts().head(10)
        report["来源分布"] = {str(k): int(v) for k, v in sources.items()}
    
    # ==========================================
    # 保存 JSON 格式
    # ==========================================
    json_path = output_path.with_suffix('.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # ==========================================
    # 保存 TXT 格式（人类可读）
    # ==========================================
    txt_path = output_path.with_suffix('.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("数据清洗质量报告\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"报告生成时间: {report['report_time']}\n\n")
        
        f.write("【数据量统计】\n")
        f.write(f"  原始数据: {report['summary']['原始数据']} 条\n")
        f.write(f"  清洗后数据: {report['summary']['清洗后数据']} 条\n")
        f.write(f"  删除总数: {report['summary']['删除总数']} 条\n")
        f.write(f"  删除率: {report['summary']['删除率']}\n\n")
        
        f.write("【清洗详情】\n")
        for key, value in report["清洗详情"].items():
            f.write(f"  {key}: {value} 条\n")
        
        f.write("\n【数据质量】\n")
        f.write(f"  平均正文长度: {report['数据质量']['平均正文长度']} 字符\n")
        f.write(f"  平均分词数量: {report['数据质量']['平均分词数量']} 个\n")
        
        if report["数据质量"]["时间跨度"]:
            ts = report["数据质量"]["时间跨度"]
            f.write(f"  时间范围: {ts['开始']} ~ {ts['结束']} ({ts['天数']} 天)\n")
        
        f.write("\n【来源分布】\n")
        for source, count in report.get("来源分布", {}).items():
            f.write(f"  {source}: {count} 条\n")
        
        f.write("\n" + "=" * 60 + "\n")
    
    print(f"[OK] 质量报告已生成: {txt_path}")
    return str(txt_path)