"""获取 A 股日线数据（前复权），存入数据库。"""

import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time

import akshare as ak
import pandas as pd
from loguru import logger

from data.models import get_conn, init_db


def fetch_daily(symbols, start_date="20200101", end_date="20251231", sleep=0.5):
    """
    获取日线数据。
    symbols: 股票代码列表，如 ["000001", "600519"]
    start_date / end_date: "YYYYMMDD"
    """
    conn = get_conn()
    cursor = conn.cursor()

    # 格式化日期为 akshare 需要的格式
    start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
    end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

    total = 0
    for i, code in enumerate(symbols):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq",  # 前复权
            )
            if df is None or df.empty:
                logger.warning(f"{code}: 无数据")
                continue

            # akshare 列名: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
            for _, row in df.iterrows():
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO daily_bars
                        (code, trade_date, open, high, low, close, volume, amount, turnover, pre_close, change_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        code,
                        str(row["日期"]),
                        row["开盘"], row["最高"], row["最低"],
                        row["收盘"], row["成交量"], row["成交额"],
                        row["换手率"], row["开盘"] / (1 + row["涨跌幅"] / 100) if row["涨跌幅"] != 0 else row["收盘"],
                        row["涨跌幅"],
                    ),
                )
                total += 1

            logger.info(f"[{i+1}/{len(symbols)}] {code}: {len(df)} 条")

            if sleep > 0 and i < len(symbols) - 1:
                time.sleep(sleep)

        except Exception as e:
            logger.error(f"{code}: 获取失败 - {e}")

    conn.commit()
    conn.close()
    logger.info(f"完成，共写入 {total} 条日线数据")


def main():
    parser = argparse.ArgumentParser(description="获取 A 股日线数据")
    parser.add_argument("--symbols", type=str, required=True,
                        help="股票代码，逗号分隔，如: 000001,600519")
    parser.add_argument("--start", type=str, default="20200101")
    parser.add_argument("--end", type=str, default="20251231")
    parser.add_argument("--sleep", type=float, default=0.5,
                        help="请求间隔秒数")
    args = parser.parse_args()

    symbol_list = [s.strip() for s in args.symbols.split(",") if s.strip()]

    init_db()
    logger.info(f"开始获取 {len(symbol_list)} 只股票日线数据")
    fetch_daily(symbol_list, args.start, args.end, args.sleep)


if __name__ == "__main__":
    main()
