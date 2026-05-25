"""实盘券商接口 — xtquant 对接国金 MiniQMT。

启动条件：
1. MiniQMT 客户端已运行 (XtItClient.exe)
2. 已在 MiniQMT 中登录资金账号
"""

import sys
import time
from loguru import logger

from config import config


def _ensure_xtquant():
    """将 QMT 自带的 xtquant 加入 Python 搜索路径。"""
    qmt_lib = getattr(config, 'QMT_LIB_PATH',
                      r"D:\国金QMT交易端模拟\bin.x64\Lib\site-packages")
    if qmt_lib not in sys.path:
        sys.path.insert(0, qmt_lib)


def stock_suffix(code):
    """根据代码判断交易所后缀: 6→SH, 0/3→SZ, 8/4→BJ"""
    if code.startswith("6"):
        return "SH"
    elif code.startswith(("0", "3")):
        return "SZ"
    elif code.startswith(("8", "4")):
        return "BJ"
    return "SZ"


def to_xtcode(code):
    """纯数字代码 → xtquant 格式，如 '000001' → '000001.SZ'"""
    if "." in code:
        return code
    return f"{code}.{stock_suffix(code)}"


def from_xtcode(xtcode):
    """xtquant 格式 → 纯数字代码，如 '000001.SZ' → '000001'"""
    return xtcode.split(".")[0] if "." in xtcode else xtcode


class XtBrokerCallback:
    """xtquant 回调，桥接到日志系统。"""

    def __init__(self):
        self.connected = False

    def on_connected(self):
        self.connected = True
        logger.info("MiniQMT 已连接")

    def on_disconnected(self):
        self.connected = False
        logger.warning("MiniQMT 断开连接")

    def on_account_status(self, status):
        logger.debug(f"账号状态: {status.account_id} status={status.status}")

    def on_stock_asset(self, asset):
        logger.debug(f"资产推送: 可用={asset.cash:.0f} 总={asset.total_asset:.0f}")

    def on_stock_order(self, order):
        logger.info(f"委托更新: {order.stock_code} "
                    f"{'买' if order.order_type == 23 else '卖'} "
                    f"{order.order_volume}股 状态={order.order_status}")

    def on_stock_trade(self, trade):
        logger.info(f"成交: {trade.stock_code} {trade.traded_volume}股 "
                    f"@{trade.traded_price:.2f}")

    def on_stock_position(self, position):
        logger.debug(f"持仓推送: {position.stock_code} {position.volume}股")

    def on_order_error(self, error):
        logger.error(f"委托失败: order_id={error.order_id} {error.error_msg}")

    def on_cancel_error(self, error):
        logger.error(f"撤单失败: order_id={error.order_id}")

    def on_order_stock_async_response(self, response):
        if response.error_msg:
            logger.error(f"异步下单失败: {response.error_msg}")
        else:
            logger.info(f"异步下单成功: order_id={response.order_id}")

    def on_smt_appointment_async_response(self, response):
        pass

    def on_cancel_order_stock_async_response(self, response):
        pass


class QmtBroker:
    """MiniQMT 券商接口，封装 xtquant 交易操作。"""

    def __init__(self):
        _ensure_xtquant()
        self._trader = None
        self._callback = XtBrokerCallback()
        self._account = None

    @property
    def connected(self):
        return self._callback.connected if self._callback else False

    def connect(self):
        """连接 MiniQMT 并登录账号。返回是否成功。"""
        from xtquant.xttrader import XtQuantTrader
        from xtquant.xttype import StockAccount
        from xtquant import xtconstant

        miniqmt_path = getattr(config, 'QMT_USERDATA_PATH',
                               r"D:\国金QMT交易端模拟\userdata_mini")
        session = int(getattr(config, 'QMT_SESSION_ID', 888888))

        logger.info(f"连接 MiniQMT: path={miniqmt_path} session={session}")

        try:
            self._trader = XtQuantTrader(miniqmt_path, session, self._callback)
        except Exception as e:
            logger.error(f"创建 XtQuantTrader 失败: {e}")
            return False

        self._trader.start()
        result = self._trader.connect()

        if result != 0:
            logger.error(f"MiniQMT 连接失败，返回码: {result}")
            logger.error("请确认 MiniQMT 客户端已启动并已登录")
            return False

        time.sleep(0.5)

        # 查询账号
        accounts = self._trader.query_account_infos()
        if not accounts:
            logger.error("未找到资金账号，请确认已在 MiniQMT 中登录")
            return False

        logger.info(f"找到 {len(accounts)} 个账号")

        # 取股票账号
        for acc in accounts:
            if acc.m_nAccountType == xtconstant.SECURITY_ACCOUNT:
                self._account = StockAccount(acc.m_strAccountID, 'STOCK')
                break
        if self._account is None:
            self._account = StockAccount(accounts[0].m_strAccountID)

        # 订阅账号
        self._trader.subscribe(self._account)
        logger.info(f"已订阅账号: {self._account.account_id}")

        # 查询并打印资产
        asset = self._trader.query_stock_asset(self._account)
        if asset:
            logger.info(f"账户资产: 可用{asset.m_dCash:,.0f} "
                        f"市值{asset.m_dMarketValue:,.0f} "
                        f"总{asset.m_dTotalAsset:,.0f}")

        return True

    def get_asset(self):
        """查询账户资产。返回 {cash, frozen_cash, market_value, total_asset}"""
        if not self._trader or not self._account:
            return None
        asset = self._trader.query_stock_asset(self._account)
        if asset:
            return {
                "cash": asset.m_dCash,
                "frozen_cash": asset.m_dFrozenCash,
                "market_value": asset.m_dMarketValue,
                "total_asset": asset.m_dTotalAsset,
            }
        return None

    def get_positions(self):
        """查询持仓。返回 [{code, volume, can_use, cost, market_value}]"""
        if not self._trader or not self._account:
            return []
        positions = self._trader.query_stock_positions(self._account)
        result = []
        if positions:
            for pos in positions:
                result.append({
                    "code": from_xtcode(pos.m_strStockCode),
                    "xtcode": pos.m_strStockCode,
                    "volume": pos.m_nVolume,
                    "can_use_volume": pos.m_nCanUseVolume,
                    "cost": pos.m_dOpenPrice,
                    "market_value": pos.m_dMarketValue,
                    "frozen_volume": pos.m_nFrozenVolume,
                    "yesterday_volume": pos.m_nYesterdayVolume,
                })
        return result

    def get_orders(self):
        """查询当日委托。"""
        if not self._trader or not self._account:
            return []
        return self._trader.query_stock_orders(self._account) or []

    def get_trades(self):
        """查询当日成交。"""
        if not self._trader or not self._account:
            return []
        return self._trader.query_stock_trades(self._account) or []

    def buy(self, code, volume, price=None, strategy_name="慧策系统"):
        """买入。price=None 则用最新价。"""
        from xtquant import xtconstant
        if not self._trader or not self._account:
            logger.error("未连接 MiniQMT")
            return None

        xtcode = to_xtcode(code)
        price_type = xtconstant.FIX_PRICE if price else xtconstant.LATEST_PRICE
        order_price = price if price else 0

        logger.info(f"下单: 买入 {xtcode} {volume}股 "
                    f"{'@' + str(order_price) if price else '市价'}")

        try:
            order_id = self._trader.order_stock(
                self._account, xtcode,
                xtconstant.STOCK_BUY,
                volume,
                price_type,
                order_price,
                strategy_name,
            )
            if order_id == -1:
                logger.error(f"买入失败: {xtcode}")
                return None
            logger.info(f"买入委托成功: order_id={order_id}")
            return order_id
        except Exception as e:
            logger.error(f"买入异常: {e}")
            return None

    def sell(self, code, volume, price=None, strategy_name="慧策系统"):
        """卖出。price=None 则用最新价。"""
        from xtquant import xtconstant
        if not self._trader or not self._account:
            logger.error("未连接 MiniQMT")
            return None

        xtcode = to_xtcode(code)
        price_type = xtconstant.FIX_PRICE if price else xtconstant.LATEST_PRICE
        order_price = price if price else 0

        logger.info(f"下单: 卖出 {xtcode} {volume}股 "
                    f"{'@' + str(order_price) if price else '市价'}")

        try:
            order_id = self._trader.order_stock(
                self._account, xtcode,
                xtconstant.STOCK_SELL,
                volume,
                price_type,
                order_price,
                strategy_name,
            )
            if order_id == -1:
                logger.error(f"卖出失败: {xtcode}")
                return None
            logger.info(f"卖出委托成功: order_id={order_id}")
            return order_id
        except Exception as e:
            logger.error(f"卖出异常: {e}")
            return None

    def cancel_order(self, order_id):
        """撤单。"""
        if not self._trader or not self._account:
            logger.error("未连接 MiniQMT")
            return -1
        result = self._trader.cancel_order_stock(self._account, order_id)
        logger.info(f"撤单 order_id={order_id}: {'成功' if result == 0 else '失败'}")
        return result

    def disconnect(self):
        """断开连接。"""
        if self._trader:
            if self._account:
                self._trader.unsubscribe(self._account)
            self._trader.stop()
            logger.info("MiniQMT 已断开")
