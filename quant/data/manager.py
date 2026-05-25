"""统一数据读写接口。"""

import sqlite3

import pandas as pd

from data.models import get_conn


def get_bars(symbols, start=None, end=None):
    """
    获取日线数据，返回 {symbol: DataFrame}。

    symbols: list[str] 股票代码列表
    start: "YYYY-MM-DD" 或 "YYYYMMDD"
    end: "YYYY-MM-DD" 或 "YYYYMMDD"
    """
    if isinstance(symbols, str):
        symbols = [symbols]

    conn = get_conn()

    placeholders = ",".join(["?" for _ in symbols])
    sql = f"SELECT * FROM daily_bars WHERE code IN ({placeholders})"
    params = list(symbols)

    if start:
        start = start.replace("-", "")[:8]
        sql += " AND REPLACE(trade_date, '-', '') >= ?"
        params.append(start)
    if end:
        end = end.replace("-", "")[:8]
        sql += " AND REPLACE(trade_date, '-', '') <= ?"
        params.append(end)

    sql += " ORDER BY trade_date ASC"

    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()

    if df.empty:
        return {}

    df["trade_date"] = pd.to_datetime(df["trade_date"])

    result = {}
    for code in df["code"].unique():
        result[code] = df[df["code"] == code].reset_index(drop=True)

    return result


def get_stocks(board=None):
    """获取股票列表。board: main / gem / star / bj"""
    conn = get_conn()
    if board:
        df = pd.read_sql_query("SELECT * FROM stocks WHERE board = ?", conn, params=(board,))
    else:
        df = pd.read_sql_query("SELECT * FROM stocks", conn)
    conn.close()
    return df


def get_last_trade_date():
    """获取最近的交易日。"""
    conn = get_conn()
    row = conn.execute("SELECT MAX(trade_date) FROM daily_bars").fetchone()
    conn.close()
    return row[0] if row[0] else None


def get_today_bars(symbols):
    """获取最近一个交易日的行情（实盘用）。"""
    last_date = get_last_trade_date()
    if last_date is None:
        return {}
    conn = get_conn()
    placeholders = ",".join(["?" for _ in symbols])
    sql = f"SELECT * FROM daily_bars WHERE code IN ({placeholders}) AND trade_date = ?"
    df = pd.read_sql_query(sql, conn, params=list(symbols) + [last_date])
    conn.close()
    if df.empty:
        return {}
    result = {}
    for code in df["code"].unique():
        result[code] = df[df["code"] == code].iloc[0].to_dict()
    return result
