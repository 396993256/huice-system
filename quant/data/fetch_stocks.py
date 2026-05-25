"""获取全部 A 股股票列表，存入数据库。"""

import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import akshare as ak
except ImportError:
    ak = None

from data.models import get_conn, init_db


def fetch_stocks():
    """拉取沪深京 A 股列表。"""
    if ak is None:
        raise ImportError("请先安装 akshare: pip install akshare")

    print("正在获取 A 股列表...")
    df = ak.stock_info_a_code_name()
    df.columns = ["code", "name"]

    conn = get_conn()
    cursor = conn.cursor()

    for _, row in df.iterrows():
        code = str(row["code"])
        name = str(row["name"])

        # 判断交易所和板块
        if code.startswith("6"):
            exchange = "sh"
            board = "main"
        elif code.startswith("0") or code.startswith("3"):
            exchange = "sz"
            board = "gem" if code.startswith("3") else "main"
        elif code.startswith("8") or code.startswith("4"):
            exchange = "bj"
            board = "bj"
        elif code.startswith("68"):
            exchange = "sh"
            board = "star"
        else:
            exchange = ""
            board = ""

        cursor.execute(
            "INSERT OR REPLACE INTO stocks (code, name, exchange, board) VALUES (?, ?, ?, ?)",
            (code, name, exchange, board),
        )

    conn.commit()
    conn.close()
    print(f"已保存 {len(df)} 只股票")
    return df


def main():
    parser = argparse.ArgumentParser(description="获取 A 股股票列表")
    parser.parse_args()

    init_db()
    fetch_stocks()


if __name__ == "__main__":
    main()
