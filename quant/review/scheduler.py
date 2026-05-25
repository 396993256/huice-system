#!/usr/bin/env python3
"""复盘数据每日自动采集调度器。

用法:
    python -m review.scheduler                  # 常驻进程，每日 15:30 采集
    python -m review.scheduler --time 16:00     # 自定义采集时间
    python -m review.scheduler --now            # 立即采集一次后退出（适合 Windows 计划任务）

Windows 计划任务（推荐）:
    schtasks /create /tn "慧策复盘采集" /tr "python -m review.scheduler --now" /sc daily /st 15:30
"""

import argparse
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <level>{message}</level>")


def collect_today(max_retries=3, retry_delay=300):
    """采集今日复盘数据，失败时自动重试。

    max_retries: 最大重试次数（默认 3 次）
    retry_delay: 重试间隔秒数（默认 300 秒 = 5 分钟）
    """
    from review.store import init_review_db, save_review
    from data.fetch_calendar import is_trading_day

    now = datetime.now()
    weekday = now.weekday()

    if weekday >= 5:
        logger.info(f"周末跳过 ({now.strftime('%Y-%m-%d')})")
        return False, None

    if not is_trading_day():
        logger.info(f"非交易日，跳过")
        return False, None

    init_review_db()

    for attempt in range(max_retries + 1):
        try:
            trade_date = save_review()
            logger.info(f"入库成功: {trade_date}" + (f" (第{attempt+1}次)" if attempt > 0 else ""))
            return True, trade_date
        except Exception as e:
            logger.error(f"入库失败 (第{attempt+1}/{max_retries+1}次): {e}")
            if attempt < max_retries:
                logger.info(f"  {retry_delay}秒后重试...")
                time.sleep(retry_delay)
            else:
                logger.error(f"  {max_retries+1}次尝试全部失败，放弃今日采集")

    return False, None


def main():
    p = argparse.ArgumentParser(description="复盘数据每日自动采集")
    p.add_argument("--time", default="15:30", help="每日采集时间 (默认 15:30)")
    p.add_argument("--now", action="store_true", help="立即采集一次后退出")
    args = p.parse_args()

    if args.now:
        success, date = collect_today()
        sys.exit(0 if success else 1)

    import schedule

    logger.info(f"复盘自动采集启动: 每日 {args.time}")
    schedule.every().day.at(args.time).do(collect_today)

    jobs = schedule.get_jobs()
    logger.info(f"下次执行: {jobs[0].next_run}")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
