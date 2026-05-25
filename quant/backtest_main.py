"""回测入口脚本。

用法:
    python backtest_main.py --strategy ma_crossover --symbols 000001,600519 --start 2024-01-01 --end 2024-12-31 --cash 100000
"""

import argparse
import importlib
import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger

from data.models import init_db
from data.manager import get_bars
from strategy.base import Strategy
from backtest.engine import BacktestEngine
from backtest.report import print_report


def main():
    parser = argparse.ArgumentParser(description="A股量化回测")
    parser.add_argument("--strategy", type=str, required=True,
                        help="策略名称，如 ma_crossover（对应 strategy/ma_crossover.py 中的类）")
    parser.add_argument("--symbols", type=str, required=True,
                        help="股票代码，逗号分隔，如: 000001,600519,000858")
    parser.add_argument("--start", type=str, required=True,
                        help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", type=str, required=True,
                        help="结束日期 YYYY-MM-DD")
    parser.add_argument("--cash", type=float, default=100000.0,
                        help="初始资金，默认 10万")
    parser.add_argument("--params", type=str, default="",
                        help="策略参数，格式: fast=5,slow=20 或 param1=val1,param2=val2")
    args = parser.parse_args()

    symbol_list = [s.strip() for s in args.symbols.split(",") if s.strip()]

    # 解析策略参数
    params = {}
    if args.params:
        for pair in args.params.split(","):
            k, v = pair.split("=")
            k, v = k.strip(), v.strip()
            # 尝试转数字
            try:
                params[k] = float(v) if "." in v else int(v)
            except ValueError:
                params[k] = v

    # 初始化数据库
    init_db()

    # 加载数据
    logger.info(f"加载数据: {symbol_list}, {args.start} ~ {args.end}")
    data = get_bars(symbol_list, args.start, args.end)

    if not data:
        logger.error("无数据！请先运行 python data/fetch_daily.py 获取数据")
        sys.exit(1)

    for code, df in data.items():
        logger.info(f"  {code}: {len(df)} 条记录")

    # 加载策略类
    try:
        mod = importlib.import_module(f"strategy.{args.strategy}")
        strategy_cls = None
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and issubclass(attr, Strategy) and attr is not Strategy:
                strategy_cls = attr
                break
        if strategy_cls is None:
            logger.error(f"模块 strategy/{args.strategy}.py 中未找到 Strategy 子类")
            sys.exit(1)
    except ImportError:
        logger.error(f"策略模块 strategy/{args.strategy}.py 不存在")
        sys.exit(1)

    # 运行回测
    logger.info(f"开始回测: {strategy_cls.__name__}, 初始资金 {args.cash:,.0f}")
    engine = BacktestEngine(initial_cash=args.cash)
    result = engine.run(strategy_cls, data, params=params)

    # 输出报告
    print_report(result)

    return result


if __name__ == "__main__":
    main()
