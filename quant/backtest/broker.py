"""模拟 A 股券商：T+1、涨跌停、印花税、佣金、手数取整。"""

import uuid
import math

from config import config


class SimBroker:
    """
    模拟 A 股交易券商。
    - T+1：当天买的次日才能卖
    - 涨跌停：主板 ±10%，创业板/科创板 ±20%
    - 印花税：卖出 0.05%
    - 佣金：万2.5，最低 5 元
    - 委托数量：100 股整数倍
    """

    def __init__(self, portfolio):
        self.portfolio = portfolio
        self.trades = []  # 已成交记录
        self.current_bar = None   # 当前 K 线（由引擎设置）
        self.current_date = None  # 当前日期

    def buy(self, symbol, volume, price=None):
        """买入委托 → 即时撮合。"""
        order = self._submit(symbol, "BUY", volume, price)
        if order is None:
            return None
        return self.execute(order)

    def sell(self, symbol, volume, price=None):
        """卖出委托 → 即时撮合。"""
        order = self._submit(symbol, "SELL", volume, price)
        if order is None:
            return None
        return self.execute(order)

    def _submit(self, symbol, direction, volume, price):
        volume = (volume // 100) * 100
        if volume <= 0:
            return None
        return {"symbol": symbol, "direction": direction, "volume": volume, "price": price}

    def execute(self, order):
        """即时撮合，使用 current_bar 的价格信息。"""
        if self.current_bar is None:
            return None

        symbol = order["symbol"]
        direction = order["direction"]
        volume = order["volume"]
        order_price = order["price"]
        close = self.current_bar.get("close", 0)
        pre_close = self.current_bar.get("pre_close", close)

        if close <= 0 or pre_close <= 0:
            return None

        # 1. 计算涨跌停价
        limit_pct = 0.2 if (symbol.startswith("3") or symbol.startswith("68")) else 0.1
        limit_up = round(pre_close * (1 + limit_pct), 2)
        limit_down = round(pre_close * (1 - limit_pct), 2)

        # 2. 确定成交价
        if order_price is None:
            fill_price = close
        elif direction == "BUY":
            if order_price < limit_down:
                return None
            fill_price = min(order_price, close)
        else:
            if order_price > limit_up:
                return None
            fill_price = max(order_price, close)

        # 3. 涨跌停封板检查
        if direction == "BUY" and close >= limit_up:
            return None
        if direction == "SELL" and close <= limit_down:
            return None

        # 4. T+1 卖出检查
        if direction == "SELL":
            pos = self.portfolio.get_position(symbol)
            if pos is None or pos["sellable_volume"] <= 0:
                return None
            volume = min(volume, pos["sellable_volume"])
            if volume <= 0:
                return None

        # 5. 资金检查（买入）
        if direction == "BUY":
            commission = max(config.MIN_COMMISSION, fill_price * volume * config.COMMISSION_RATE)
            estimated_cost = fill_price * volume + commission
            if estimated_cost > self.portfolio.cash:
                max_vol = int(self.portfolio.cash / (fill_price * (1 + config.COMMISSION_RATE)) / 100) * 100
                volume = min(volume, max_vol)
                if volume <= 0:
                    return None

        # 6. 计算手续费
        commission = max(config.MIN_COMMISSION, fill_price * volume * config.COMMISSION_RATE)
        stamp_duty = fill_price * volume * config.STAMP_DUTY_RATE if direction == "SELL" else 0.0

        # 再次资金检查（含手续费）
        if direction == "BUY" and fill_price * volume + commission > self.portfolio.cash:
            return None

        # 7. 生成成交
        fill = {
            "symbol": symbol,
            "direction": direction,
            "volume": volume,
            "price": fill_price,
            "commission": round(commission, 2),
            "stamp_duty": round(stamp_duty, 2),
            "trade_date": self.current_date or "",
            "order_id": str(uuid.uuid4())[:8],
        }
        self.portfolio.apply_fill(fill)
        self.trades.append(fill)
        return fill
