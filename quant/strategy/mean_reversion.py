"""布林带均值回归策略 — 示例。"""

from strategy.base import Strategy
from strategy.indicators import bollinger


class MeanReversion(Strategy):
    """
    布林带回归策略：
    - 价格触及下轨 → 买入（超卖回归）
    - 价格触及上轨 → 卖出（超买回归）
    """

    def on_init(self, data, portfolio):
        super().on_init(data, portfolio)
        self.period = self.params.get("period", 20)
        self.std = self.params.get("std", 2)
        self.buy_pct_val = self.params.get("buy_pct", 0.5)

    def on_bar(self, symbol, portfolio):
        df = self.data.get(symbol)
        if df is None or len(df) < self.period + 1:
            return

        close = df["close"]
        upper, mid, lower = bollinger(close, self.period, self.std)

        if upper is None or len(upper) < 1:
            return

        price = close.iloc[-1]
        up = upper.iloc[-1]
        lo = lower.iloc[-1]

        pos = portfolio.get_position(symbol)

        # 价格跌破下轨 → 买入
        if price <= lo and (pos is None or pos["total_volume"] == 0):
            self.buy_pct(symbol, self.buy_pct_val, price)

        # 价格突破上轨 → 卖出
        elif price >= up:
            self.sell_all(symbol)
