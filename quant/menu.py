"""新手菜单 — 选择功能直接运行。"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    while True:
        print("\n" + "=" * 45)
        print("  A股量化交易系统")
        print("=" * 45)
        print("  1. 获取股票数据")
        print("  2. 回测策略")
        print("  3. 模拟交易 (paper)")
        print("  4. 实盘交易 (live)")
        print("  5. 退出")
        print("-" * 45)

        choice = input("请选择 [1-5]: ").strip()

        if choice == "1":
            symbols = input("股票代码 (逗号分隔, 如 000001,600519): ").strip()
            start = input("起始日期 (如 20240101): ").strip() or "20240101"
            end = input("结束日期 (如 20251231): ").strip() or "20251231"
            print(f"\n正在获取 {symbols} 的数据...")
            from data.models import init_db
            init_db()
            from data.fetch_daily import fetch_daily
            fetch_daily([s.strip() for s in symbols.split(",") if s.strip()], start, end)

        elif choice == "2":
            strategy = input("策略名 (ma_crossover / mean_reversion): ").strip() or "ma_crossover"
            symbols = input("股票代码: ").strip() or "000001"
            start = input("起始日期 (如 2024-01-01): ").strip() or "2024-01-01"
            end = input("结束日期 (如 2024-12-31): ").strip() or "2024-12-31"
            cash = float(input("初始资金 (默认 100000): ").strip() or "100000")
            print("\n正在回测，请稍候...\n")
            from data.models import init_db
            init_db()
            from data.manager import get_bars
            import importlib
            from strategy.base import Strategy
            mod = importlib.import_module(f"strategy.{strategy}")
            strategy_cls = None
            for name in dir(mod):
                attr = getattr(mod, name)
                if isinstance(attr, type) and issubclass(attr, Strategy) and attr is not Strategy:
                    strategy_cls = attr
                    break
            data = get_bars([s.strip() for s in symbols.split(",")], start, end)
            from backtest.engine import BacktestEngine
            from backtest.report import print_report
            engine = BacktestEngine(initial_cash=cash)
            result = engine.run(strategy_cls, data, progress=False)
            print_report(result)

        elif choice == "3":
            strategy = input("策略名: ").strip() or "ma_crossover"
            symbols = input("股票代码: ").strip() or "000001"
            print("\n模拟交易模式（不会实际下单）\n")
            from live.trader import run_live
            run_live(strategy, [s.strip() for s in symbols.split(",")])

        elif choice == "4":
            from config import config
            if config.TRADE_MODE != "live":
                print("\n⚠  请在 .env 文件中设置 TRADE_MODE=live 并填入券商账号")
                input("按回车返回...")
                continue
            print("\n" + "!" * 45)
            print("  ⚠  实盘模式！将产生真实交易！")
            print("  确认券商客户端已打开并登录")
            print("!" * 45)
            confirm = input("\n输入 YES 确认: ").strip()
            if confirm != "YES":
                print("已取消")
                continue
            strategy = input("策略名: ").strip() or "ma_crossover"
            symbols = input("股票代码: ").strip() or "000001"
            from live.trader import run_live
            run_live(strategy, [s.strip() for s in symbols.split(",")])

        elif choice == "5":
            print("再见！")
            break


if __name__ == "__main__":
    main()
