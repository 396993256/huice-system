"""MiniQMT 连接测试 — 验证 xtquant 接通、账户查询、模拟下单。

启动前请确保：
1. MiniQMT 客户端已运行 (D:\国金QMT交易端模拟\bin.x64\XtItClient.exe)
2. 已在 MiniQMT 中登录账号
"""

import sys
import time
import os

# 把 xtquant 加入 Python 搜索路径（国金 QMT 自带）
QMT_LIB = r"D:\国金QMT交易端模拟\bin.x64\Lib\site-packages"
sys.path.insert(0, QMT_LIB)

from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount
from xtquant import xtconstant

# MiniQMT userdata 目录（不是 bin.x64！）
MINIQMT_PATH = r"D:\国金QMT交易端模拟\userdata_mini"
# 会话 ID，随便填一个整数
SESSION_ID = 888888


class MyCallback(XtQuantTraderCallback):
    """回调处理，接收 QMT 推送。"""

    def on_connected(self):
        print("[OK] MiniQMT 已连接")

    def on_disconnected(self):
        print("[!!] MiniQMT 断开连接")

    def on_account_status(self, status):
        print(f"[回调] 账号状态: account_id={status.account_id}, "
              f"type={status.account_type}, status={status.status}")

    def on_stock_asset(self, asset):
        print(f"[回调] 资产: 账户={asset.account_id}, "
              f"可用={asset.cash:.2f}, 市值={asset.market_value:.2f}, "
              f"总资产={asset.total_asset:.2f}")

    def on_stock_order(self, order):
        print(f"[回调] 委托: {order.stock_code} order_id={order.order_id} "
              f"状态={order.order_status} {order.status_msg}")

    def on_stock_trade(self, trade):
        print(f"[回调] 成交: {trade.stock_code} {trade.traded_volume}股 "
              f"@{trade.traded_price:.2f}")

    def on_stock_position(self, position):
        print(f"[回调] 持仓: {position.stock_code} "
              f"{position.volume}股 成本{position.open_price:.2f}")

    def on_order_error(self, error):
        print(f"[回调] 委托失败: order_id={error.order_id} "
              f"error={error.error_msg}")

    def on_cancel_error(self, error):
        print(f"[回调] 撤单失败: order_id={error.order_id}")

    def on_order_stock_async_response(self, response):
        print(f"[回调] 异步下单反馈: order_id={response.order_id} "
              f"error={response.error_msg}")


def get_stock_suffix(code):
    """根据代码判断交易所后缀 — 6开头→SH, 0/3开头→SZ, 8/4开头→BJ"""
    if code.startswith("6"):
        return "SH"
    elif code.startswith(("0", "3")):
        return "SZ"
    elif code.startswith(("8", "4")):
        return "BJ"
    return "SZ"


def main():
    print("=" * 60)
    print("  MiniQMT xtquant 连接测试")
    print("=" * 60)

    # 1. 创建交易客户端
    print(f"\n[1] 创建 XtQuantTrader...")
    print(f"    userdata路径: {MINIQMT_PATH}")
    print(f"    会话ID: {SESSION_ID}")

    callback = MyCallback()
    trader = XtQuantTrader(MINIQMT_PATH, SESSION_ID, callback)

    # 2. 启动并连接
    print("\n[2] 启动并连接 MiniQMT...")
    trader.start()
    result = trader.connect()

    if result != 0:
        print(f"[FAIL] 连接失败，返回码: {result}")
        print("   请确认：")
        print("   1) MiniQMT 客户端 (XtItClient.exe) 已启动")
        print("   2) 已在 MiniQMT 中登录账号")
        return

    print("[OK] 连接成功！")
    time.sleep(1)

    # 3. 查询账号列表
    print("\n[3] 查询账号列表...")
    accounts = trader.query_account_infos()
    if not accounts:
        print("[FAIL] 未找到账号，请确保已在 MiniQMT 中登录")
        return

    print(f"[OK] 找到 {len(accounts)} 个账号:")
    for acc in accounts:
        print(f"     account_id={acc.m_strAccountID}, "
              f"account_type={acc.m_nAccountType}")

    # 取第一个股票账号
    account = None
    for acc in accounts:
        if acc.m_nAccountType == xtconstant.SECURITY_ACCOUNT:
            account = StockAccount(acc.m_strAccountID, 'STOCK')
            break
    if account is None:
        # 没有股票账号，用第一个
        acc = accounts[0]
        account = StockAccount(acc.m_strAccountID)
    print(f"\n    使用账号: {account.account_id} (type={account.account_type})")

    # 4. 订阅账号（必须先订阅才能收推送）
    print("\n[4] 订阅账号...")
    trader.subscribe(account)
    print("[OK] 已订阅")

    # 5. 查询资产
    print("\n[5] 查询资产...")
    asset = trader.query_stock_asset(account)
    if asset:
        print(f"    可用资金: {asset.m_dCash:,.2f}")
        print(f"    冻结资金: {asset.m_dFrozenCash:,.2f}")
        print(f"    持仓市值: {asset.m_dMarketValue:,.2f}")
        print(f"    总资产:   {asset.m_dTotalAsset:,.2f}")
    else:
        print("    (无资产数据)")

    # 6. 查询持仓
    print("\n[6] 查询持仓...")
    positions = trader.query_stock_positions(account)
    if positions:
        for pos in positions:
            print(f"    {pos.m_strStockCode}: {pos.m_nVolume}股 "
                  f"成本{pos.m_dOpenPrice:.2f} "
                  f"可用{pos.m_nCanUseVolume} "
                  f"市值{pos.m_dMarketValue:.2f}")
    else:
        print("    (空仓)")

    # 7. 查询当日委托
    print("\n[7] 查询当日委托...")
    orders = trader.query_stock_orders(account)
    if orders:
        for o in orders:
            status_map = {48: "未报", 49: "待报", 50: "已报", 54: "已撤",
                          55: "部成", 56: "已成", 57: "废单"}
            status = status_map.get(o.m_nOrderStatus, str(o.m_nOrderStatus))
            print(f"    {o.m_strStockCode} {'买' if o.m_nOrderType == 23 else '卖'} "
                  f"{o.m_nOrderVolume}股 @{o.m_dPrice:.2f} [{status}]")
    else:
        print("    (无委托)")

    # 8. 清理
    print("\n[8] 断开连接...")
    trader.unsubscribe(account)
    trader.stop()
    print("[OK] 测试完成！")


if __name__ == "__main__":
    main()
