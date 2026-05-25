"""定时执行交易策略。

用法:
    python live/scheduler.py --strategy ma_crossover --time 14:55
"""

import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from datetime import datetime

import schedule
from loguru import logger


def run_job(strategy_name, symbols, params):
    """定时触发的交易任务。"""
    from live.trader import run_live

    now = datetime.now()
    weekday = now.weekday()
    if weekday >= 5:
        logger.info(f"周末跳过: {now}")
        return

    logger.info(f"定时交易触发: {now}")
    try:
        run_live(strategy_name, symbols, params)
    except Exception as e:
        logger.error(f"交易异常: {e}")


def main():
    parser = argparse.ArgumentParser(description="定时交易调度器")
    parser.add_argument("--strategy", type=str, required=True, help="策略名称")
    parser.add_argument("--symbols", type=str, required=True,
                        help="股票池，逗号分隔")
    parser.add_argument("--time", type=str, default="14:55",
                        help="每日执行时间，默认 14:55")
    parser.add_argument("--interval", type=int, default=0,
                        help="循环间隔（分钟），0 表示仅在指定时间执行一次")
    args = parser.parse_args()

    symbol_list = [s.strip() for s in args.symbols.split(",") if s.strip()]

    logger.info(f"调度器启动: 策略={args.strategy}, 品种={symbol_list}")

    if args.interval > 0:
        # 间隔模式
        logger.info(f"每 {args.interval} 分钟执行一次")
        schedule.every(args.interval).minutes.do(
            run_job, args.strategy, symbol_list, None
        )
    else:
        # 固定时间模式
        logger.info(f"每日 {args.time} 执行")
        schedule.every().day.at(args.time).do(
            run_job, args.strategy, symbol_list, None
        )

    # 显示下次执行时间
    jobs = schedule.get_jobs()
    if jobs:
        logger.info(f"下次执行: {jobs[0].next_run}")

    # 主循环
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
