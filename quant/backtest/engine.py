"""事件驱动回测引擎。"""

from datetime import datetime

import pandas as pd
from loguru import logger

from backtest.portfolio import Portfolio
from backtest.broker import SimBroker
from backtest.report import compute, print_report


class BacktestEngine:
    """事件驱动回测引擎。"""

    def __init__(self, initial_cash=100000.0):
        self.portfolio = Portfolio(initial_cash)
        self.broker = SimBroker(self.portfolio)
        self.strategy = None

    def run(self, strategy_cls, data, params=None, progress=True):
        """
        运行回测。

        strategy_cls: Strategy 子类
        data: {symbol: DataFrame} DataFrame 需包含 trade_date, open, high, low, close, volume 列
        params: 策略参数字典

        返回回测结果 dict
        """
        # 保留原始完整数据的引用（迭代用，不修改）
        full_data = data

        # 1. 初始化策略（策略用一份独立的 sliced data）
        sliced_data = {}
        self.strategy = strategy_cls(params=params or {})
        self.strategy.broker = self.broker
        self.strategy.data = sliced_data
        self.strategy.on_init(sliced_data, self.portfolio)

        # 2. 构建时间线：合并所有股票的交易日，按时间排序
        all_dates = set()
        for df in full_data.values():
            if "trade_date" in df.columns:
                all_dates.update(df["trade_date"].tolist())
        all_dates = sorted(all_dates)

        if not all_dates:
            logger.warning("无交易日数据")
            return {}

        # 3. 逐日遍历
        total_dates = len(all_dates)
        for i, dt in enumerate(all_dates):
            date_str = dt if isinstance(dt, str) else dt.strftime("%Y-%m-%d")

            # 收市后处理 T+1 解锁
            self.portfolio.end_of_day()

            # 遍历每只股票当天数据
            for symbol, df_full in full_data.items():
                bar_row = df_full[df_full["trade_date"] == dt]
                if bar_row.empty:
                    continue

                bar = bar_row.iloc[0].to_dict()

                # 更新价格
                self.portfolio.update_price(symbol, bar["close"])

                # 设置当前 bar 到 broker（供撮合使用）
                self.broker.current_bar = bar
                self.broker.current_date = date_str

                # 切片数据到当前日期（避免未来数据泄露）
                idx = bar_row.index[0]
                sliced_data[symbol] = df_full.iloc[:idx + 1].reset_index(drop=True)

                # 调用策略
                try:
                    self.strategy.on_bar(symbol, self.portfolio)
                except Exception as e:
                    logger.error(f"策略异常 {symbol} {date_str}: {e}")

            # 日终快照
            self.portfolio.snapshot(dt)

            if progress and (i + 1) % 50 == 0:
                logger.info(f"回测进度: {i+1}/{total_dates}")

        # 4. 计算交易 PnL
        self._compute_trade_pnl(full_data)

        # 5. 输出报告
        result = compute(self.portfolio.nav_series, self.broker.trades)
        return result

    def _compute_trade_pnl(self, data):
        """为每笔卖出计算盈亏。用先进先出简化计算。"""
        # 按时间排序交易
        trades = sorted(self.broker.trades, key=lambda t: t["trade_date"])

        # 用队列跟踪每只股票的买入成本
        buy_queues = {}  # symbol -> [(volume, price, commission), ...]

        for t in trades:
            sym = t["symbol"]
            if t["direction"] == "BUY":
                buy_queues.setdefault(sym, []).append(
                    (t["volume"], t["price"], t.get("commission", 0))
                )
                t["pnl"] = 0
            else:
                # 卖出：用 FIFO 计算盈亏
                sell_vol = t["volume"]
                sell_price = t["price"]
                sell_commission = t.get("commission", 0)
                stamp = t.get("stamp_duty", 0)
                pnl = 0
                queue = buy_queues.get(sym, [])

                while sell_vol > 0 and queue:
                    buy_vol, buy_price, buy_comm = queue[0]
                    matched_vol = min(sell_vol, buy_vol)
                    # 每股买入成本（含佣金）
                    buy_cost_per_share = buy_price + buy_comm / buy_vol if buy_vol > 0 else buy_price
                    sell_rev_per_share = sell_price - (sell_commission + stamp) / sell_vol if sell_vol > 0 else sell_price
                    pnl += (sell_rev_per_share - buy_cost_per_share) * matched_vol

                    if matched_vol >= buy_vol:
                        queue.pop(0)
                    else:
                        queue[0] = (buy_vol - matched_vol, buy_price, buy_comm)

                    sell_vol -= matched_vol

                t["pnl"] = round(pnl, 2)
