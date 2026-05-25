"""风控检查：下单前必过此模块。"""

from loguru import logger

from config import config


class RiskManager:
    """实盘风控管理器。"""

    def __init__(self):
        self.daily_pnl = 0.0          # 当日盈亏
        self.consecutive_losses = 0   # 连续亏损笔数
        self.trade_count_today = 0    # 当日交易次数
        self.blocked = False
        self.block_reason = ""

    def check_buy(self, symbol, volume, price, portfolio):
        """
        买入前检查。
        portfolio: {cash, positions, nav}
        返回 (allowed, msg)
        """
        if self.blocked:
            return False, f"交易已暂停: {self.block_reason}"

        if price is None or price <= 0:
            return False, "无效价格"

        cost = volume * price

        # 资金不足
        if cost > portfolio["cash"]:
            return False, f"资金不足: 需要 {cost:.2f}, 可用 {portfolio['cash']:.2f}"

        # 单只股票仓位限制
        nav = portfolio["nav"]
        current_pos_value = 0
        if symbol in portfolio["positions"]:
            pos = portfolio["positions"][symbol]
            current_pos_value = pos["total_volume"] * price

        new_pos_pct = (current_pos_value + cost) / nav if nav > 0 else 1
        if new_pos_pct > config.MAX_SINGLE_STOCK_PCT:
            return False, f"超出单票仓位限制 ({new_pos_pct*100:.1f}% > {config.MAX_SINGLE_STOCK_PCT*100:.0f}%)"

        # 可用现金校验（预留 5% 现金）
        if cost > portfolio["cash"] * 0.95:
            return False, "现金不足（需预留 5%）"

        return True, "OK"

    def check_sell(self, symbol, volume, price, portfolio):
        """卖出前检查。"""
        if self.blocked:
            return False, f"交易已暂停: {self.block_reason}"

        pos = portfolio["positions"].get(symbol)
        if not pos or pos["total_volume"] <= 0:
            return False, f"无 {symbol} 持仓"

        if volume > pos["total_volume"]:
            return False, f"卖出量({volume})超过持仓({pos['total_volume']})"

        return True, "OK"

    def record_trade(self, pnl):
        """记录交易结果。"""
        self.trade_count_today += 1
        self.daily_pnl += pnl

        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        # 单日亏损检查
        if self.daily_pnl < 0:
            initial_asset = 100000  # 从外部传入更好，此处简化
            if abs(self.daily_pnl) / initial_asset > config.MAX_DAILY_LOSS_PCT:
                self.blocked = True
                self.block_reason = f"单日亏损超过 {config.MAX_DAILY_LOSS_PCT*100}%"
                logger.warning(f"风控：{self.block_reason}，暂停交易")

        # 连续亏损检查
        if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
            self.blocked = True
            self.block_reason = f"连续亏损 {self.consecutive_losses} 笔"
            logger.warning(f"风控：{self.block_reason}，暂停交易")

    def reset_daily(self):
        """每日重置。"""
        self.daily_pnl = 0.0
        self.trade_count_today = 0
        self.blocked = False
        self.block_reason = ""
