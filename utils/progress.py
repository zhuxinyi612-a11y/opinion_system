"""
进度条工具 - 显示处理进度（无 emoji，兼容 Windows GBK）
"""

import time
from typing import Iterable, Callable, Optional


def process_with_progress(
    items: Iterable,
    func: Callable,
    desc: str = "处理中",
    total: Optional[int] = None,
    show_time: bool = True
) -> list:
    """
    带进度条的处理函数
    """
    items_list = list(items)
    total = total or len(items_list)
    
    results = []
    start_time = time.time()
    
    for i, item in enumerate(items_list, 1):
        result = func(item)
        results.append(result)
        
        # 打印进度
        if i % max(1, total // 20) == 0 or i == total:
            pct = i / total * 100
            if show_time:
                elapsed = time.time() - start_time
                speed = i / elapsed if elapsed > 0 else 0
                remaining = (total - i) / speed if speed > 0 else 0
                print(f"\r  {desc}: {i}/{total} ({pct:.1f}%) | "
                      f"速度: {speed:.1f} 条/秒 | "
                      f"剩余: {remaining:.1f} 秒", end='')
            else:
                print(f"\r  {desc}: {i}/{total} ({pct:.1f}%)", end='')
    
    print()  # 换行
    elapsed = time.time() - start_time
    print(f"  [OK] {desc}完成，耗时 {elapsed:.2f} 秒")
    
    return results


class ProgressTracker:
    """简单进度跟踪器"""
    
    def __init__(self, total: int, desc: str = "处理中"):
        self.total = total
        self.desc = desc
        self.current = 0
        self.start_time = time.time()
        self.last_update = 0
    
    def update(self, n: int = 1):
        self.current += n
        current_time = time.time()
        
        # 每秒最多更新一次，避免刷屏
        if current_time - self.last_update >= 1 or self.current >= self.total:
            self.last_update = current_time
            pct = self.current / self.total * 100
            elapsed = current_time - self.start_time
            speed = self.current / elapsed if elapsed > 0 else 0
            remaining = (self.total - self.current) / speed if speed > 0 else 0
            
            print(f"\r  {self.desc}: {self.current}/{self.total} ({pct:.1f}%) "
                  f"| 速度: {speed:.1f} 条/秒 | 剩余: {remaining:.1f} 秒", end='')
            
            if self.current >= self.total:
                print()  # 完成时换行