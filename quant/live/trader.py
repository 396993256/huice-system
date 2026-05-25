"""实盘交易主脚本 — 通过 xtquant 对接 MiniQMT。"""

import importlib
from datetime import datetime, time as dtime

from loguru import logger

from config import config
from data.manager import get_bars, get_today_bars
from live.risk import RiskManager


def run_live(strategy_name, symbols, params=None):
    """
    执行一次实盘/模拟交易。

    strategy_name: 策略模块名，如 "ma_crossover"
    symbols: 股票代码列表
    params: 策略参数字典
    """
    mode = config.TRADE_MODE
    logger.info(f"=== 慧策系统 开始交易，模式: {mode} ===")
    logger.info(f"策略: {strategy_name}, 股票池: {symbols}")

    # 1. 检查交易时间
    now = datetime.now()
    if now.weekday() >= 5:
        logger.info("周末不交易")
        return
    t = now.time()
    morning = dtime(9, 30) <= t <= dtime(11, 30)
    afternoon = dtime(13, 0) <= t <= dtime(15, 0)
    if not (morning or afternoon):
        logger.info("非交易时间")
        if mode != "live":
            return

    # 2. 获取行情数据
    logger.info("获取行情数据...")
    today_bars = get_today_bars(symbols)
    if not today_bars:
        logger.warning("未获取到今日行情")
        return

    # 3. 初始化风控
    risk = RiskManager()

    # 4. 连接券商
    qmt_broker = None
    if mode == "live":
        from live.broker import QmtBroker
        qmt_broker = QmtBroker()
        if not qmt_broker.connect():
            logger.error("券商连接失败，退出")
            return

    # 5. 加载策略类
    try:
        mod = importlib.import_module(f"strategy.{strategy_name}")
        from strategy.base import Strategy
        strategy_cls = None
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and issubclass(attr, Strategy) and attr is not Strategy:
                strategy_cls = attr
                break
        if strategy_cls is None:
            logger.error(f"策略模块 {strategy_name} 中未找到 Strategy 子类")
            return
    except ImportError:
        logger.error(f"策略模块 {strategy_name} 不存在")
        return

    # 6. 获取历史数据（用于计算指标）
    data = get_bars(symbols)
    if not data:
        logger.warning("无历史数据")
        return

    # 7. 获取账户信息（实盘模式从 QMT 查询）
    balance = None
    positions_raw = None
    if mode == "live" and qmt_broker:
        try:
            balance = qmt_broker.get_asset()
            positions_raw = qmt_broker.get_positions()
            logger.info(f"账户资产: {balance}")
        except Exception as e:
            logger.error(f"获取账户信息失败: {e}")

    # 8. 构建 LivePortfolio
    portfolio = _build_portfolio(balance, positions_raw, today_bars)

    # 9. 创建 broker 桥接（策略 → 风控 → 券商）
    broker_bridge = _LiveBrokerBridge(portfolio, risk, qmt_broker)

    # 10. 初始化策略
    strategy = strategy_cls(params=params or {})
    strategy.data = data
    strategy.broker = broker_bridge
    strategy.on_init(data, portfolio)

    # 11. 遍历股票池
    for symbol in symbols:
        bar = today_bars.get(symbol)
        if bar is None:
            logger.debug(f"{symbol}: 无今日行情")
            continue
        try:
            strategy.on_bar(symbol, portfolio)
        except Exception as e:
            logger.error(f"策略执行异常 {symbol}: {e}")

    # 12. 收尾
    logger.info(f"=== 交易结束，资产: {portfolio.nav:.2f} ===")
    logger.info(f"持仓: {len(portfolio.positions)} 只，现金: {portfolio.cash:.2f}")

    risk.reset_daily()
    if broker_bridge.trades_today:
        logger.info(f"当日成交 {len(broker_bridge.trades_today)} 笔")
        for t in broker_bridge.trades_today:
            logger.info(f"  {t['direction']} {t['symbol']} {t['volume']}股 @ {t['price']}")

    # 清理
    if qmt_broker:
        qmt_broker.disconnect()

    return risk


def _build_portfolio(balance, positions_raw, today_bars):
    """构建 LivePortfolio 对象。"""

    class LivePortfolio:
        def __init__(self):
            if isinstance(balance, dict):
                self.cash = float(balance.get("cash", 100000))
            else:
                self.cash = 100000.0

            self.positions = {}
            if positions_raw:
                for p in positions_raw:
                    code = p.get("code", "")
                    if not code:
                        continue
                    self.positions[code] = {
                        "total_volume": int(p.get("volume", 0)),
                        "sellable_volume": int(p.get("can_use_volume", 0)),
                        "avg_cost": float(p.get("cost", 0)),
                    }
            self._today_bars = today_bars

        @property
        def nav(self):
            pos_value = 0
            for code, pos in self.positions.items():
                bar = self._today_bars.get(code, {})
                price = bar.get("close", pos["avg_cost"])
                pos_value += pos["total_volume"] * price
            return self.cash + pos_value

        def get_position(self, symbol):
            return self.positions.get(symbol)

    return LivePortfolio()


class _LiveBrokerBridge:
    """策略下单 → 风控 → QMT / 模拟。"""

    def __init__(self, portfolio, risk, qmt_broker=None):
        self.portfolio = portfolio
        self.risk = risk
        self.qmt = qmt_broker
        self.trades_today = []

    def buy(self, symbol, volume, price=None):
        if price is None:
            bar = get_today_bars([symbol]).get(symbol, {})
            price = bar.get("close", 0)

        ok, msg = self.risk.check_buy(symbol, volume, price, {
            "cash": self.portfolio.cash,
            "nav": self.portfolio.nav,
            "positions": self.portfolio.positions,
        })
        if not ok:
            logger.warning(f"风控拦截买入 {symbol}: {msg}")
            return None

        volume = (volume // 100) * 100
        if volume <= 0:
            return None

        if config.TRADE_MODE == "live" and self.qmt:
            order_id = self.qmt.buy(symbol, volume, price)
            if order_id is None:
                logger.error(f"实盘买入失败 {symbol}")
                return None
        else:
            logger.info(f"【模拟】买入 {symbol} {volume}股 @ {price}")

        trade = {
            "symbol": symbol, "direction": "BUY",
            "volume": volume, "price": price, "time": datetime.now(),
        }
        self.trades_today.append(trade)
        return trade

    def sell(self, symbol, volume, price=None):
        if price is None:
            bar = get_today_bars([symbol]).get(symbol, {})
            price = bar.get("close", 0)

        ok, msg = self.risk.check_sell(symbol, volume, price, {
            "positions": self.portfolio.positions,
        })
        if not ok:
            logger.warning(f"风控拦截卖出 {symbol}: {msg}")
            return None

        volume = (volume // 100) * 100
        if volume <= 0:
            return None

        if config.TRADE_MODE == "live" and self.qmt:
            order_id = self.qmt.sell(symbol, volume, price)
            if order_id is None:
                logger.error(f"实盘卖出失败 {symbol}")
                return None
        else:
            logger.info(f"【模拟】卖出 {symbol} {volume}股 @ {price}")

        trade = {
            "symbol": symbol, "direction": "SELL",
            "volume": volume, "price": price, "time": datetime.now(),
        }
        self.trades_today.append(trade)
        return trade
