"""SQLite 表结构。"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from pathlib import Path

from config import config


def get_conn():
    db_path = Path(config.DATA_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """创建所有表。"""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS stocks (
            code        TEXT PRIMARY KEY,
            name        TEXT,
            exchange    TEXT,     -- sh / sz / bj
            board       TEXT,     -- main / gem / star
            industry    TEXT,
            list_date   TEXT
        );

        CREATE TABLE IF NOT EXISTS daily_bars (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT NOT NULL,
            trade_date  TEXT NOT NULL,
            open        REAL,
            high        REAL,
            low         REAL,
            close       REAL,
            volume      INTEGER,   -- 成交量（股）
            amount      REAL,      -- 成交额（元）
            turnover    REAL,      -- 换手率（%）
            pre_close   REAL,
            change_pct  REAL,
            UNIQUE(code, trade_date)
        );

        CREATE INDEX IF NOT EXISTS idx_bars_code_date ON daily_bars(code, trade_date);

        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mode        TEXT DEFAULT 'backtest',  -- backtest / paper / live
            run_id      TEXT,       -- 回测或实盘运行 ID
            code        TEXT,
            trade_date  TEXT,
            direction   TEXT,      -- BUY / SELL
            volume      INTEGER,
            price       REAL,
            commission  REAL DEFAULT 0,
            stamp_duty  REAL DEFAULT 0,
            pnl         REAL,
            reason      TEXT
        );

        CREATE TABLE IF NOT EXISTS positions (
            code            TEXT PRIMARY KEY,
            total_volume    INTEGER DEFAULT 0,
            sellable_volume INTEGER DEFAULT 0,
            avg_cost        REAL
        );

        CREATE TABLE IF NOT EXISTS account (
            id      INTEGER PRIMARY KEY CHECK (id = 1),
            cash    REAL DEFAULT 0,
            total_asset REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS trading_calendar (
            trade_date  TEXT PRIMARY KEY,
            is_open     INTEGER DEFAULT 1
        );
    """)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("数据库初始化完成")
