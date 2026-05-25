"""回测报告：收益率、夏普比率、最大回撤等。"""

import math
import numpy as np
import pandas as pd


def compute(nav_series, trades, benchmark_returns=None):
    """
    根据净值曲线和交易记录计算各项指标。

    nav_series: [{"date": dt, "nav": float, ...}, ...]
    trades: [{"symbol", "direction", "volume", "price", "pnl"}, ...]
    """
    if not nav_series or len(nav_series) < 2:
        return {}

    navs = [s["nav"] for s in nav_series]
    nav_df = pd.DataFrame(nav_series)
    initial_nav = navs[0]
    final_nav = navs[-1]

    # 计算收益率序列
    nav_df["return"] = nav_df["nav"].pct_change()
    returns = nav_df["return"].dropna()

    # 总收益率
    total_return = (final_nav / initial_nav - 1) * 100

    # 年化收益率
    trading_days = len(nav_df)
    years = trading_days / 252
    annual_return = (pow(final_nav / initial_nav, 1 / years) - 1) * 100 if years > 0 else 0

    # 年化波动率
    annual_vol = returns.std() * math.sqrt(252) * 100 if len(returns) > 0 else 0

    # 夏普比率（假设无风险利率 3%）
    rf_daily = 0.03 / 252
    excess = returns.mean() - rf_daily
    sharpe = excess / returns.std() * math.sqrt(252) if returns.std() > 0 else 0

    # 最大回撤
    peak = navs[0]
    max_dd = 0
    max_dd_start = None
    max_dd_end = None
    for i, n in enumerate(navs):
        if n > peak:
            peak = n
        dd = (peak - n) / peak
        if dd > max_dd:
            max_dd = dd
            max_dd_end = i
            # 找到回撤起点的 peak 位置
            max_dd_start = next(
                (j for j in range(i, -1, -1) if navs[j] == peak), 0
            )

    # 胜率
    buy_trades = [t for t in trades if t.get("direction") == "BUY"]
    sell_trades = [t for t in trades if t.get("direction") == "SELL"]

    # 根据每次完整交易（买入->卖出）计算盈亏
    win_count = 0
    total_pnl = 0
    total_profit = 0
    total_loss = 0

    for t in trades:
        pnl = t.get("pnl", 0) or 0
        total_pnl += pnl
        if pnl > 0:
            win_count += 1
            total_profit += pnl
        else:
            total_loss += abs(pnl)

    win_rate = win_count / len(trades) * 100 if trades else 0

    # 盈亏比
    profit_factor = total_profit / total_loss if total_loss > 0 else float("inf")

    return {
        "total_return": round(total_return, 2),
        "annual_return": round(annual_return, 2),
        "annual_volatility": round(annual_vol, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown": round(max_dd * 100, 2),
        "max_dd_start": nav_series[max_dd_start]["date"] if max_dd_start is not None else None,
        "max_dd_end": nav_series[max_dd_end]["date"] if max_dd_end is not None else None,
        "total_trades": len(trades),
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "∞",
        "initial_nav": round(initial_nav, 2),
        "final_nav": round(final_nav, 2),
        "nav_series": nav_series,
    }


def print_report(result):
    """打印回测报告。"""
    print("\n" + "=" * 55)
    print("  回测报告")
    print("=" * 55)
    print(f"  初始资金          {result['initial_nav']:>12,.2f}")
    print(f"  最终资金          {result['final_nav']:>12,.2f}")
    print(f"  总收益率          {result['total_return']:>11.2f}%")
    print(f"  年化收益率        {result['annual_return']:>11.2f}%")
    print(f"  年化波动率        {result['annual_volatility']:>11.2f}%")
    print(f"  夏普比率          {result['sharpe_ratio']:>12.2f}")
    print(f"  最大回撤          {result['max_drawdown']:>11.2f}%")
    print(f"  总交易次数        {result['total_trades']:>12}")
    print(f"  胜率              {result['win_rate']:>11.1f}%")
    print(f"  总盈亏            {result['total_pnl']:>12,.2f}")
    print(f"  盈亏比            {result['profit_factor']:>12}")
    print("=" * 55)
