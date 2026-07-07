"""
一键运行整个预处理流程
支持全部7个脚本，包含高级分析模块
支持跳过、从指定步骤开始、超时控制
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import subprocess
from datetime import datetime
import argparse
import time

from config import LOG_DIR, OUTPUT_DIR
from utils.logger import setup_logger

# 创建带时间戳的日志文件
run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f'run_all_{run_timestamp}.log'
logger = setup_logger(LOG_FILE)

# ==========================================
# 所有脚本列表（按依赖顺序排列）
# ==========================================
ALL_SCRIPTS = [
    ('01_load_data.py', '数据加载'),
    ('02_extract_body.py', '正文提取'),
    ('03_clean_deduplicate.py', '清洗去重'),
    ('04_segment.py', '中文分词'),
    ('05_feature_extract.py', 'TF-IDF特征提取'),
    ('06_generate_report.py', '生成统计报告'),
    ('07_advanced_analysis.py', '高级分析（情感/摘要/实体）'),
]

def run_script(script_name: str, description: str, timeout: int = 300) -> tuple[bool, str]:
    logger.info(f"\n{'='*60}")
    logger.info(f"▶️  [{description}] 运行: {script_name}")
    logger.info(f"{'='*60}")

    script_path = Path(__file__).parent / script_name
    if not script_path.exists():
        return False, f"脚本不存在: {script_path}"

    start_time = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout
        )

        lines = result.stdout.split('\n')
        if len(lines) > 30:
            print('\n'.join(lines[:30]))
            print(f"... (省略 {len(lines)-30} 行)")
        else:
            print(result.stdout)

        if result.stderr:
            warnings = [line for line in result.stderr.split('\n')
                       if line and 'warning' not in line.lower()]
            if warnings:
                logger.warning('\n'.join(warnings))

        elapsed = time.time() - start_time
        success = result.returncode == 0
        if success:
            logger.info(f"✅ {script_name} 执行成功！耗时: {elapsed:.2f} 秒")
            return True, ""
        else:
            error_msg = f"返回码 {result.returncode}"
            logger.error(f"❌ {script_name} 失败，{error_msg}，耗时 {elapsed:.2f} 秒")
            return False, error_msg

    except subprocess.TimeoutExpired:
        return False, f"超时（>{timeout}秒）"
    except Exception as e:
        return False, str(e)

def main():
    parser = argparse.ArgumentParser(description='舆情数据预处理 - 一键运行全流程')
    parser.add_argument(
        '--skip',
        nargs='+',
        choices=[f'0{i}' for i in range(1, 8)] + [f'{i}' for i in range(1, 8)],
        help='跳过的步骤编号，例如 --skip 05 07'
    )
    parser.add_argument(
        '--from',
        dest='from_step',
        choices=[f'0{i}' for i in range(1, 8)] + [f'{i}' for i in range(1, 8)],
        help='从指定步骤开始执行，例如 --from 04'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=600,
        help='单个脚本超时时间（秒），默认600'
    )
    args = parser.parse_args()

    skip_steps = set()
    if args.skip:
        for s in args.skip:
            skip_steps.add(int(s))

    start_idx = 0
    if args.from_step:
        start_idx = int(args.from_step) - 1
        if start_idx < 0:
            start_idx = 0

    scripts_to_run = []
    for idx, (script, desc) in enumerate(ALL_SCRIPTS):
        step_num = idx + 1
        if step_num < start_idx + 1:
            logger.info(f"⏭️  跳过步骤 {step_num:02d}: {desc} (--from {args.from_step})")
            continue
        if step_num in skip_steps:
            logger.info(f"⏭️  跳过步骤 {step_num:02d}: {desc} (--skip)")
            continue
        scripts_to_run.append((step_num, script, desc))

    if not scripts_to_run:
        logger.error("❌ 没有需要执行的步骤，请检查参数")
        return

    logger.info("=" * 60)
    logger.info("🚀 舆情数据预处理流水线启动")
    logger.info(f"📅 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📋 将执行 {len(scripts_to_run)} 个步骤:")
    for step_num, script, desc in scripts_to_run:
        logger.info(f"   {step_num:02d}. {desc} ({script})")
    logger.info("=" * 60)

    overall_start = time.time()
    success_steps = []
    failed_steps = []

    for step_num, script, desc in scripts_to_run:
        ok, err = run_script(script, desc, args.timeout)
        if ok:
            success_steps.append(step_num)
        else:
            failed_steps.append((step_num, desc, err))
            logger.error(f"❌ 步骤 {step_num:02d} 执行失败，流水线中断")
            break

    total_time = time.time() - overall_start

    logger.info("\n" + "=" * 60)
    logger.info("📊 执行总结")
    logger.info("=" * 60)
    logger.info(f"✅ 成功步骤: {len(success_steps)}/{len(scripts_to_run)}")
    if failed_steps:
        logger.info(f"❌ 失败步骤:")
        for step, desc, err in failed_steps:
            logger.info(f"   {step:02d}. {desc} - {err}")
    logger.info(f"⏱️  总耗时: {total_time:.2f} 秒")
    logger.info(f"📁 输出目录: {OUTPUT_DIR}")

    if OUTPUT_DIR.exists():
        files = list(OUTPUT_DIR.glob('*'))
        logger.info(f"\n📂 输出文件列表 ({len(files)} 个):")
        for f in sorted(files):
            size = f.stat().st_size / 1024
            logger.info(f"   📄 {f.name} ({size:.1f} KB)")

    logger.info("=" * 60)

    if not failed_steps:
        logger.info("🎉 恭喜！所有步骤执行成功！")
    else:
        logger.info("⚠️ 部分步骤执行失败，请检查日志")

if __name__ == '__main__':
    main()