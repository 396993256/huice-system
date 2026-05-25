"""资金和仓位管理（含 T+1 规则）。"""


class Portfolio:
    """管理现金、持仓、净值。"""

    def __init__(self, initial_cash=100000.0):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions = {}       # symbol -> {total_volume, sellable_volume, avg_cost}
        self._last_prices = {}    # 最近收盘价
        self.nav_series = []      # [(datetime, nav), ...]
        self._today_buys = set()  # 当日买入的股票（T+1 约束）

    def get_position(self, symbol):
        return self.positions.get(symbol)

    @property
    def nav(self):
        """当前总资产 = 现金 + 持仓市值。"""
        pos_value = 0
        for code, pos in self.positions.items():
            price = self._last_prices.get(code, pos["avg_cost"])
            pos_value += pos["total_volume"] * price
        return self.cash + pos_value

    @property
    def positions_value(self):
        """持仓总市值。"""
        v = 0
        for code, pos in self.positions.items():
            price = self._last_prices.get(code, pos["avg_cost"])
            v += pos["total_volume"] * price
        return v

    def update_price(self, symbol, price):
        """更新最新价格（用于计算 NAV）。"""
        self._last_prices[symbol] = price

    def snapshot(self, dt):
        """记录净值快照。"""
        self.nav_series.append({
            "date": dt,
            "nav": self.nav,
            "cash": self.cash,
            "positions_value": self.positions_value,
        })

    # ── 成交处理 ──

    def apply_fill(self, fill):
        """
        处理成交。fill 为 dict:
        {symbol, direction, volume, price, commission, stamp_duty}
        """
        symbol = fill["symbol"]
        direction = fill["direction"]
        volume = fill["volume"]
        price = fill["price"]
        commission = fill.get("commission", 0)
        stamp_duty = fill.get("stamp_duty", 0)

        if direction == "BUY":
            cost = price * volume + commission
            self.cash -= cost

            if symbol not in self.positions:
                self.positions[symbol] = {
                    "total_volume": 0,
                    "sellable_volume": 0,
                    "avg_cost": 0,
                }
            pos = self.positions[symbol]
            total_cost = pos["avg_cost"] * pos["total_volume"] + price * volume
            pos["total_volume"] += volume
            pos["avg_cost"] = total_cost / pos["total_volume"] if pos["total_volume"] > 0 else 0
            # 当天买入的不能卖
            self._today_buys.add(symbol)

        else:  # SELL
            revenue = price * volume - commission - stamp_duty
            self.cash += revenue

            if symbol in self.positions:
                pos = self.positions[symbol]
                pos["total_volume"] -= volume
                pos["sellable_volume"] -= volume
                if pos["total_volume"] <= 0:
                    del self.positions[symbol]

    def end_of_day(self):
        """收市后：当日买入的变为可卖。"""
        self._today_buys = set()
        for pos in self.positions.values():
            pos["sellable_volume"] = pos["total_volume"]
