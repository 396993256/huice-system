"""双均线交叉策略 — 示例。"""

from strategy.base import Strategy
from strategy.indicators import sma


class MACrossover(Strategy):
    """
    双均线金叉/死叉策略：
    - 快线上穿慢线 → 买入
    - 快线下穿慢线 → 卖出
    """

    def on_init(self, data, portfolio):
        super().on_init(data, portfolio)
        self.fast = self.params.get("fast", 5)
        self.slow = self.params.get("slow", 20)
        self.buy_pct_val = self.params.get("buy_pct", 0.8)

    def on_bar(self, symbol, portfolio):
        df = self.data.get(symbol)
        if df is None or len(df) < self.slow + 1:
            return

        close = df["close"]
        ma_f = sma(close, self.fast)
        ma_s = sma(close, self.slow)

        if ma_f is None or ma_s is None or len(ma_f) < 2 or len(ma_s) < 2:
            return

        # 取最近两根
        prev_f, curr_f = ma_f.iloc[-2], ma_f.iloc[-1]
        prev_s, curr_s = ma_s.iloc[-2], ma_s.iloc[-1]

        # 金叉：快线从下上穿
        if prev_f <= prev_s and curr_f > curr_s:
            self.buy_pct(symbol, self.buy_pct_val, close.iloc[-1])

        # 死叉：快线从上下穿
        elif prev_f >= prev_s and curr_f < curr_s:
            self.sell_all(symbol)
