"""
第六步：生成数据质量报告（HTML + 可视化图表）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from datetime import datetime
import json

from config import OUTPUT_DIR, REPORT_DIR
from utils.logger import setup_logger

logger = setup_logger(REPORT_DIR / '06_generate_report.log')

print("=" * 60)
print("[第六步] 生成数据质量报告")
print("=" * 60)

# ==========================================
# 1. 加载最终数据
# ==========================================
input_file = OUTPUT_DIR / 'advanced_analysis.csv'
if not input_file.exists():
    input_file = OUTPUT_DIR / 'cleaned_data.csv'

if not input_file.exists():
    logger.error(f"❌ 找不到数据文件: {input_file}")
    sys.exit(1)

df = pd.read_csv(input_file, encoding='utf-8-sig')
logger.info(f"[DATA] 共加载 {len(df)} 条数据")

# ==========================================
# 2. 计算统计指标
# ==========================================
stats = {
    "总记录数": len(df),
    "平均正文长度": round(df.get('cleaned_body', df.get('extracted_body', '')).str.len().mean(), 1),
    "平均词数": round(df.get('word_count', pd.Series([0])).mean(), 1),
    "时间跨度": {}
}

# 时间范围
if 'publish_time' in df.columns:
    try:
        times = pd.to_datetime(df['publish_time'])
        stats["时间跨度"] = {
            "开始": times.min().strftime('%Y-%m-%d'),
            "结束": times.max().strftime('%Y-%m-%d'),
            "天数": (times.max() - times.min()).days
        }
    except:
        pass

# 来源分布
if 'source' in df.columns:
    stats["来源分布"] = df['source'].value_counts().head(10).to_dict()

# 情感分布
if 'sentiment_label' in df.columns:
    stats["情感分布"] = df['sentiment_label'].value_counts().to_dict()
    stats["平均情感得分"] = round(df['sentiment_polarity'].mean(), 3)

# ==========================================
# 3. 生成 HTML 报告
# ==========================================
html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>舆情数据预处理质量报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
            background: #f0f2f5;
            padding: 30px;
            color: #333;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            padding: 40px 50px;
        }}
        h1 {{
            color: #1a73e8;
            font-size: 28px;
            border-bottom: 3px solid #1a73e8;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }}
        .meta {{
            color: #999;
            font-size: 14px;
            margin-bottom: 30px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
            margin: 25px 0 30px 0;
        }}
        .stat-card {{
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            border-left: 4px solid #1a73e8;
        }}
        .stat-number {{
            font-size: 32px;
            font-weight: bold;
            color: #1a73e8;
        }}
        .stat-label {{
            color: #888;
            font-size: 13px;
            margin-top: 6px;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: bold;
            margin: 30px 0 15px 0;
            color: #1a73e8;
            border-left: 4px solid #1a73e8;
            padding-left: 12px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0 20px 0;
            font-size: 14px;
        }}
        th, td {{
            padding: 10px 14px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #555;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .tag {{
            display: inline-block;
            padding: 2px 12px;
            border-radius: 20px;
            font-size: 12px;
        }}
        .tag-pos {{ background: #e6f7e6; color: #2e7d32; }}
        .tag-neg {{ background: #fde8e8; color: #c62828; }}
        .tag-neu {{ background: #fff3e0; color: #e65100; }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            text-align: center;
            color: #bbb;
            font-size: 13px;
        }}
        .badge {{
            background: #1a73e8;
            color: white;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 12px;
        }}
    </style>
</head>
<body>
<div class="container">
    <h1>📊 舆情数据预处理质量报告</h1>
    <div class="meta">
        生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; 
        报告版本: v1.0
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-number">{stats['总记录数']}</div>
            <div class="stat-label">📄 最终数据量</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{stats['平均正文长度']}</div>
            <div class="stat-label">📏 平均正文长度（字符）</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{stats['平均词数']}</div>
            <div class="stat-label">✂️ 平均分词数量</div>
        </div>
"""

if stats.get("平均情感得分"):
    html_content += f"""
        <div class="stat-card">
            <div class="stat-number">{stats['平均情感得分']}</div>
            <div class="stat-label">😊 平均情感得分（0~1）</div>
        </div>
    """

if stats["时间跨度"].get("天数"):
    html_content += f"""
        <div class="stat-card">
            <div class="stat-number">{stats['时间跨度']['天数']}</div>
            <div class="stat-label">📅 时间跨度（天）</div>
        </div>
    """

html_content += """
    </div>
"""

# 来源分布
if stats.get("来源分布"):
    html_content += """
    <div class="section-title">📰 来源分布</div>
    <table>
        <tr><th>来源</th><th>数量</th><th>占比</th></tr>
    """
    total = sum(stats["来源分布"].values())
    for source, count in list(stats["来源分布"].items())[:10]:
        pct = count / total * 100
        html_content += f"<tr><td>{source}</td><td>{count}</td><td>{pct:.1f}%</td></tr>"
    html_content += "</table>"

# 情感分布
if stats.get("情感分布"):
    html_content += """
    <div class="section-title">💬 情感分布</div>
    <table>
        <tr><th>情感倾向</th><th>数量</th><th>占比</th></tr>
    """
    total = sum(stats["情感分布"].values())
    label_map = {'正面': 'tag-pos', '负面': 'tag-neg', '中性': 'tag-neu'}
    for label, count in stats["情感分布"].items():
        pct = count / total * 100
        tag_class = label_map.get(label, 'tag-neu')
        html_content += f"""
        <tr>
            <td><span class="tag {tag_class}">{label}</span></td>
            <td>{count}</td>
            <td>{pct:.1f}%</td>
        </tr>
        """
    html_content += "</table>"

# 时间范围
if stats["时间跨度"].get("开始"):
    ts = stats["时间跨度"]
    html_content += f"""
    <div class="section-title">📅 时间范围</div>
    <table>
        <tr><td><b>开始日期</b></td><td>{ts['开始']}</td></tr>
        <tr><td><b>结束日期</b></td><td>{ts['结束']}</td></tr>
        <tr><td><b>总天数</b></td><td>{ts['天数']} 天</td></tr>
    </table>
    """

# 数据样例
html_content += """
    <div class="section-title">📝 数据样例（前5条）</div>
    <table>
        <tr><th>#</th><th>标题</th><th>正文预览</th><th>来源</th></tr>
"""

for idx in range(min(5, len(df))):
    row = df.iloc[idx]
    title = str(row.get('title', ''))[:25] + '...' if len(str(row.get('title', ''))) > 25 else str(row.get('title', ''))
    body = str(row.get('cleaned_body', row.get('extracted_body', '')))[:40] + '...' if len(str(row.get('cleaned_body', ''))) > 40 else str(row.get('cleaned_body', ''))
    source = str(row.get('source', '未知'))[:10]
    html_content += f"<tr><td>{idx+1}</td><td>{title}</td><td>{body}</td><td>{source}</td></tr>"

html_content += f"""
    </table>

    <div class="footer">
        报告由舆情数据预处理模块自动生成 &nbsp;|&nbsp; 大型程序设计实践
    </div>
</div>
</body>
</html>
"""

# ==========================================
# 4. 保存报告
# ==========================================
report_path = REPORT_DIR / f'quality_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

logger.info(f"[OK] 质量报告已生成: {report_path}")

# 同时保存 JSON 版本
json_path = report_path.with_suffix('.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)

print(f"\n[SUCCESS] 报告生成完成！")
print(f"   HTML: {report_path}")
print(f"   JSON: {json_path}")

# 尝试自动打开浏览器预览
try:
    import webbrowser
    webbrowser.open(str(report_path))
    print(f"   🌐 已在浏览器中打开报告")
except:
    pass