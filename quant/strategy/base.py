"""策略基类 — 所有策略继承此类。"""


class Strategy:
    """策略基类。回测和实盘共用同一套策略代码。"""

    def __init__(self, params=None):
        self.params = params or {}
        self.broker = None  # 由引擎注入（回测或实盘）

    def on_init(self, data, portfolio):
        """策略初始化时调用一次。data 为 {symbol: DataFrame}。"""
        self.data = data

    # ── 必须实现 ──

    def on_bar(self, symbol, portfolio):
        """
        每收到一根 K 线调用一次。
        在此方法中通过 self.buy() / self.sell() 下单。
        """
        raise NotImplementedError

    # ── 下单方法 ──

    def buy(self, symbol, volume, price=None):
        """买入指定数量（股）。price=None 表示市价。"""
        return self.broker.buy(symbol, volume, price)

    def sell(self, symbol, volume, price=None):
        """卖出指定数量（股）。"""
        return self.broker.sell(symbol, volume, price)

    def buy_pct(self, symbol, pct, current_price):
        """
        按照当前净值的一定比例买入。
        pct: 0~1，如 0.3 表示用 30% 资金买入。
        """
        nav = self.broker.portfolio.nav
        target_value = nav * pct
        volume = int(target_value / current_price / 100) * 100
        if volume > 0:
            return self.buy(symbol, volume)
        return None

    def sell_all(self, symbol):
        """全部卖出某只股票的可用仓位。"""
        pos = self.broker.portfolio.get_position(symbol)
        if pos and pos["sellable_volume"] > 0:
            return self.sell(symbol, pos["sellable_volume"])
        return None

    # ── 回调（可选） ──

    def on_fill(self, fill):
        """成交后回调。"""
        pass

    def on_order(self, order):
        """下单后回调。"""
        pass
