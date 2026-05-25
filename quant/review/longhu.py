#!/usr/bin/env python3
"""龙虎榜数据（akshare，复盘专用）。"""

import time
import math


def fetch_longhu_list(date=None):
    """获取指定日龙虎榜股票列表。
    返回 [{code, name, close, chg_pct, turnover, amount, reason}, ...]
    """
    import akshare as ak
    if date is None:
        date = time.strftime("%Y%m%d")
    try:
        df = ak.stock_lhb_detail_daily_sina(date=date)
    except Exception:
        return []
    if df is None or len(df) == 0:
        return []
    if "股票代码" not in df.columns:
        return []
    results = []
    for _, row in df.iterrows():
        results.append({
            "code": str(row.get("股票代码", "")).zfill(6),
            "name": str(row.get("股票名称", "")),
            "close": float(row.get("收盘价", 0)) if row.get("收盘价") else 0,
            "chg_pct": float(row.get("对应值", 0)) if row.get("对应值") else 0,
            "turnover": float(row.get("成交量", 0)) if row.get("成交量") else 0,
            "amount": float(row.get("成交额", 0)) if row.get("成交额") else 0,
            "reason": str(row.get("指标", "")),
        })
    return results


def fetch_longhu_detail(code, date=None):
    """获取个股龙虎榜席位明细。
    返回 [{seat, buy, buy_pct, sell, sell_pct, net, type}, ...]
    金额单位：元
    """
    import akshare as ak
    if date is None:
        date = time.strftime("%Y%m%d")
    try:
        df = ak.stock_lhb_stock_detail_em(symbol=code, date=date)
    except Exception:
        return []
    if df is None or len(df) == 0:
        return []
    results = []
    for _, row in df.iterrows():
        buy = row.get("买入金额", 0)
        sell = row.get("卖出金额", 0)
        net = row.get("净额", 0)
        if isinstance(buy, float) and math.isnan(buy):
            buy = 0
        if isinstance(sell, float) and math.isnan(sell):
            sell = 0
        if isinstance(net, float) and math.isnan(net):
            net = 0
        buy_pct = row.get("买入金额-占总成交比例", 0)
        sell_pct = row.get("卖出金额-占总成交比例", 0)
        if isinstance(buy_pct, float) and math.isnan(buy_pct):
            buy_pct = 0
        if isinstance(sell_pct, float) and math.isnan(sell_pct):
            sell_pct = 0
        results.append({
            "seat": str(row.get("交易营业部名称", "")),
            "buy": float(buy) if buy else 0,
            "buy_pct": float(buy_pct) if buy_pct else 0,
            "sell": float(sell) if sell else 0,
            "sell_pct": float(sell_pct) if sell_pct else 0,
            "net": float(net) if net else 0,
            "type": str(row.get("类型", "")),
        })
    return results
