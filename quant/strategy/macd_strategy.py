"""MACD 金叉死叉策略。"""

from strategy.base import Strategy
from strategy.indicators import macd


class MACDStrategy(Strategy):
    """
    MACD 策略：
    - MACD 线上穿信号线（金叉）→ 买入
    - MACD 线下穿信号线（死叉）→ 卖出
    """

    def on_init(self, data, portfolio):
        super().on_init(data, portfolio)
        self.fast = self.params.get("fast", 12)
        self.slow = self.params.get("slow", 26)
        self.signal = self.params.get("signal", 9)
        self.buy_pct_val = self.params.get("buy_pct", 0.8)

    def on_bar(self, symbol, portfolio):
        df = self.data.get(symbol)
        if df is None or len(df) < self.slow + self.signal + 1:
            return

        close = df["close"]
        macd_line, signal_line, _ = macd(close, self.fast, self.slow, self.signal)

        if macd_line is None or len(macd_line) < 2:
            return

        prev_m, curr_m = macd_line.iloc[-2], macd_line.iloc[-1]
        prev_s, curr_s = signal_line.iloc[-2], signal_line.iloc[-1]

        # 金叉
        if prev_m <= prev_s and curr_m > curr_s:
            self.buy_pct(symbol, self.buy_pct_val, close.iloc[-1])
        # 死叉
        elif prev_m >= prev_s and curr_m < curr_s:
            self.sell_all(symbol)
