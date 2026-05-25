"""数据管理页面。"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading

import pandas as pd

from data.models import init_db, get_conn
from data.manager import get_bars, get_stocks
from data.fetch_stocks import fetch_stocks
from data.fetch_daily import fetch_daily


class DataPage(tk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent, bg="#f0f2f5")
        self.root = root

        # 标题
        self._title("数据管理")

        # 上半区：操作区
        top = tk.Frame(self, bg="white", bd=0, highlightthickness=0)
        top.pack(fill="x", padx=16, pady=(10, 4))

        self._build_data_fetch(top)
        self._build_data_view(top)

        # 下半区：数据表格
        self._build_table()

    def _title(self, text):
        tk.Label(self, text=text, font=("微软雅黑", 18, "bold"),
                 bg="#f0f2f5", fg="#1a1a2e").pack(anchor="w", padx=16, pady=(14, 4))

    def _build_data_fetch(self, parent):
        tk.Label(parent, text="获取数据", font=("微软雅黑", 12, "bold"),
                 bg="white", fg="#333").pack(anchor="w", padx=14, pady=(14, 4))

        row = tk.Frame(parent, bg="white")
        row.pack(fill="x", padx=14, pady=2)

        tk.Label(row, text="股票代码", bg="white", font=("微软雅黑", 10)).pack(side="left")
        self.stock_entry = tk.Entry(row, width=40, font=("微软雅黑", 10))
        self.stock_entry.insert(0, "000001,600519")
        self.stock_entry.pack(side="left", padx=8)

        tk.Label(row, text="起始", bg="white", font=("微软雅黑", 10)).pack(side="left", padx=(12, 0))
        self.start_entry = tk.Entry(row, width=12, font=("微软雅黑", 10))
        self.start_entry.insert(0, "20240101")
        self.start_entry.pack(side="left", padx=4)

        tk.Label(row, text="结束", bg="white", font=("微软雅黑", 10)).pack(side="left", padx=(12, 0))
        self.end_entry = tk.Entry(row, width=12, font=("微软雅黑", 10))
        self.end_entry.insert(0, "20251231")
        self.end_entry.pack(side="left", padx=4)

        btn_row = tk.Frame(parent, bg="white")
        btn_row.pack(fill="x", padx=14, pady=8)

        self.fetch_btn = tk.Button(btn_row, text="拉取日线数据", font=("微软雅黑", 10),
                                    bg="#e94560", fg="white", bd=0, padx=16, pady=4,
                                    cursor="hand2", command=self._do_fetch)
        self.fetch_btn.pack(side="left", padx=(0, 8))

        self.fetch_stocks_btn = tk.Button(btn_row, text="更新股票列表", font=("微软雅黑", 10),
                                           bg="#1a1a2e", fg="white", bd=0, padx=16, pady=4,
                                           cursor="hand2", command=self._do_fetch_stocks)
        self.fetch_stocks_btn.pack(side="left")

        self.status_label = tk.Label(btn_row, text="", bg="white", font=("微软雅黑", 9), fg="#666")
        self.status_label.pack(side="left", padx=12)

    def _build_data_view(self, parent):
        sep = ttk.Separator(parent, orient="horizontal")
        sep.pack(fill="x", padx=14, pady=6)

        tk.Label(parent, text="查看数据", font=("微软雅黑", 12, "bold"),
                 bg="white", fg="#333").pack(anchor="w", padx=14, pady=(4, 4))

        row = tk.Frame(parent, bg="white")
        row.pack(fill="x", padx=14, pady=2)

        tk.Label(row, text="股票代码", bg="white", font=("微软雅黑", 10)).pack(side="left")
        self.view_stock = tk.Entry(row, width=20, font=("微软雅黑", 10))
        self.view_stock.insert(0, "000001")
        self.view_stock.pack(side="left", padx=8)

        self.view_btn = tk.Button(row, text="刷新查看", font=("微软雅黑", 10),
                                   bg="#1a1a2e", fg="white", bd=0, padx=14, pady=3,
                                   cursor="hand2", command=self._do_view)
        self.view_btn.pack(side="left")

    def _build_table(self):
        table_frame = tk.Frame(self, bg="white", bd=0)
        table_frame.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        columns = ("日期", "开盘", "最高", "最低", "收盘", "成交量", "涨跌幅")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _do_fetch(self):
        symbols = [s.strip() for s in self.stock_entry.get().split(",") if s.strip()]
        start = self.start_entry.get().strip()
        end = self.end_entry.get().strip()
        if not symbols:
            messagebox.showwarning("提示", "请输入股票代码")
            return

        self.fetch_btn.configure(state="disabled", text="获取中...")
        self.status_label.configure(text="正在获取数据，请稍候...")

        def task():
            try:
                init_db()
                fetch_daily(symbols, start, end, sleep=0.3)
                self.root.after(0, lambda: self.status_label.configure(text="获取完成！"))
                self.root.after(0, lambda: self._do_view())
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", str(e)))
            finally:
                self.root.after(0, lambda: self.fetch_btn.configure(state="normal", text="拉取日线数据"))

        threading.Thread(target=task, daemon=True).start()

    def _do_fetch_stocks(self):
        self.fetch_stocks_btn.configure(state="disabled", text="获取中...")
        self.status_label.configure(text="正在获取股票列表...")

        def task():
            try:
                init_db()
                fetch_stocks()
                self.root.after(0, lambda: self.status_label.configure(text="股票列表更新完成！"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", str(e)))
            finally:
                self.root.after(0, lambda: self.fetch_stocks_btn.configure(state="normal", text="更新股票列表"))

        threading.Thread(target=task, daemon=True).start()

    def _do_view(self):
        code = self.view_stock.get().strip()
        if not code:
            return
        data = get_bars([code])
        if code not in data:
            self.status_label.configure(text=f"{code}: 无数据")
            return

        df = data[code]
        self.tree.delete(*self.tree.get_children())
        for _, row in df.tail(200).iterrows():
            date_str = str(row["trade_date"])[:10]
            self.tree.insert("", "end", values=(
                date_str,
                f"{row['open']:.2f}",
                f"{row['high']:.2f}",
                f"{row['low']:.2f}",
                f"{row['close']:.2f}",
                f"{row['volume']:,.0f}",
                f"{row.get('change_pct', 0):.2f}%",
            ))
        self.status_label.configure(text=f"{code}: 显示最近 {min(200, len(df))} 条")
