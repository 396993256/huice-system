"""RSI 超买超卖策略。"""

from strategy.base import Strategy
from strategy.indicators import rsi


class RSIStrategy(Strategy):
    """
    RSI 策略：
    - RSI 低于超卖线 → 买入
    - RSI 高于超买线 → 卖出
    """

    def on_init(self, data, portfolio):
        super().on_init(data, portfolio)
        self.period = self.params.get("period", 14)
        self.oversold = self.params.get("oversold", 30)
        self.overbought = self.params.get("overbought", 70)
        self.buy_pct_val = self.params.get("buy_pct", 0.5)

    def on_bar(self, symbol, portfolio):
        df = self.data.get(symbol)
        if df is None or len(df) < self.period + 1:
            return

        close = df["close"]
        rsi_val = rsi(close, self.period)

        if rsi_val is None or len(rsi_val) < 1:
            return

        curr_rsi = rsi_val.iloc[-1]
        pos = portfolio.get_position(symbol)

        # 超卖 → 买入
        if curr_rsi < self.oversold and (pos is None or pos["total_volume"] == 0):
            self.buy_pct(symbol, self.buy_pct_val, close.iloc[-1])
        # 超买 → 卖出
        elif curr_rsi > self.overbought:
            self.sell_all(symbol)
