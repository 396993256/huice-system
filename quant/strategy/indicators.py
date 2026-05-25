"""常用技术指标 — 纯 pandas/numpy 实现，零外部依赖。"""

import numpy as np
import pandas as pd


def sma(series, period):
    """简单移动平均。"""
    return series.rolling(window=period).mean()


def ema(series, period):
    """指数移动平均。"""
    return series.ewm(span=period, adjust=False).mean()


def macd(close, fast=12, slow=26, signal=9):
    """
    MACD 指标。
    返回 (MACD线, 信号线, 柱)。
    """
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def rsi(close, period=14):
    """相对强弱指标。"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def bollinger(close, period=20, std=2):
    """
    布林带。
    返回 (上轨, 中轨, 下轨)。
    """
    mid = sma(close, period)
    std_val = close.rolling(window=period).std()
    upper = mid + std * std_val
    lower = mid - std * std_val
    return upper, mid, lower


def atr(high, low, close, period=14):
    """平均真实波幅。"""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


def kdj(high, low, close, period=9):
    """KDJ 指标。返回 (K, D, J)。"""
    lowest_low = low.rolling(window=period).min()
    highest_high = high.rolling(window=period).max()
    rsv = (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1/3, adjust=False).mean()
    d = k.ewm(alpha=1/3, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def volume_sma(volume, period=5):
    """成交量均线。"""
    return volume.rolling(window=period).mean()
