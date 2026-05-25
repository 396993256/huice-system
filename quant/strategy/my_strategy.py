"""在这里编写你自己的策略。"""

from strategy.base import Strategy


class MyStrategy(Strategy):
    """自定义策略模板。"""

    def on_init(self, data, portfolio):
        super().on_init(data, portfolio)
        # 初始化参数

    def on_bar(self, symbol, portfolio):
        # 你的交易逻辑写在这里
        # self.buy(symbol, volume=100, price=None)
        # self.sell(symbol, volume=100, price=None)
        pass
