"""实盘交易入口脚本。

用法:
    # 模拟交易（paper）
    python live_main.py --strategy ma_crossover --symbols 000001,600519

    # 实盘交易（需先在 .env 中设置 TRADE_MODE=live）
    python live_main.py --strategy ma_crossover --symbols 000001,600519
"""

import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger

from config import config
from data.models import init_db
from live.trader import run_live


def main():
    parser = argparse.ArgumentParser(description="A股量化实盘交易")
    parser.add_argument("--strategy", type=str, required=True,
                        help="策略名称，如 ma_crossover")
    parser.add_argument("--symbols", type=str, required=True,
                        help="股票代码，逗号分隔，如: 000001,600519")
    parser.add_argument("--params", type=str, default="",
                        help="策略参数，如: fast=5,slow=20")
    args = parser.parse_args()

    symbol_list = [s.strip() for s in args.symbols.split(",") if s.strip()]

    # 解析参数
    params = {}
    if args.params:
        for pair in args.params.split(","):
            k, v = pair.split("=")
            k, v = k.strip(), v.strip()
            try:
                params[k] = float(v) if "." in v else int(v)
            except ValueError:
                params[k] = v

    init_db()

    logger.info(f"交易模式: {config.TRADE_MODE}")
    logger.info(f"券商: {config.BROKER}")

    if config.TRADE_MODE == "live":
        print("\n" + "!" * 50)
        print("  ⚠  实盘模式！将产生真实交易！")
        print("  确认券商客户端已打开并登录")
        print("!" * 50)
        confirm = input("\n输入 'yes' 确认继续: ")
        if confirm.lower() != "yes":
            logger.info("已取消")
            return

    run_live(args.strategy, symbol_list, params)


if __name__ == "__main__":
    main()
