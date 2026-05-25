import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent

load_dotenv(BASE_DIR / ".env")


class Config:
    # ---- 交易模式 ----
    TRADE_MODE = os.getenv("TRADE_MODE", "paper")  # paper / live

    # ---- 券商 ----
    BROKER = os.getenv("BROKER", "qmt")  # qmt / ht / gj

    # ---- QMT / MiniQMT 路径 ----
    QMT_LIB_PATH = os.getenv("QMT_LIB_PATH",
                             r"D:\国金QMT交易端模拟\bin.x64\Lib\site-packages")
    QMT_USERDATA_PATH = os.getenv("QMT_USERDATA_PATH",
                                  r"D:\国金QMT交易端模拟\userdata_mini")
    QMT_SESSION_ID = int(os.getenv("QMT_SESSION_ID", "888888"))

    # ---- 数据库 ----
    DATA_DB_PATH = os.getenv("DATA_DB_PATH", str(BASE_DIR / "data" / "quant.db"))

    # ---- Tushare ----
    TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

    # ---- 风控参数 ----
    MAX_SINGLE_STOCK_PCT = 0.20      # 单只股票最大仓位 20%
    MAX_DAILY_LOSS_PCT = 0.03        # 单日最大亏损 3%，触发停止
    MAX_CONSECUTIVE_LOSSES = 3       # 连续亏损 N 笔暂停

    # ---- 手续费 ----
    COMMISSION_RATE = 0.00025        # 佣金万2.5
    MIN_COMMISSION = 5.0             # 最低佣金 5 元
    STAMP_DUTY_RATE = 0.0005         # 印花税 0.05%（仅卖出）


config = Config()
