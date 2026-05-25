"""实时交易页面。"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading

from config import config
from data.models import init_db
from live.trader import run_live


class LivePage(tk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent, bg="#f0f2f5")
        self.root = root

        self._title("实时交易")

        # 上半区：设置
        self._build_config()

        # 下半区：日志输出
        self._build_log()

        # 初始状态
        self._update_mode_label()

    def _title(self, text):
        tk.Label(self, text=text, font=("微软雅黑", 18, "bold"),
                 bg="#f0f2f5", fg="#1a1a2e").pack(anchor="w", padx=16, pady=(14, 8))

    def _build_config(self):
        cfg = tk.Frame(self, bg="white", bd=0)
        cfg.pack(fill="x", padx=16, pady=2)

        # 模式标签
        mode_frame = tk.Frame(cfg, bg="white")
        mode_frame.pack(fill="x", padx=14, pady=(12, 4))

        tk.Label(mode_frame, text="当前模式:", bg="white", font=("微软雅黑", 10)).pack(side="left")
        self.mode_label = tk.Label(mode_frame, text="", font=("微软雅黑", 12, "bold"), bg="white")
        self.mode_label.pack(side="left", padx=6)

        # 策略设置
        row1 = tk.Frame(cfg, bg="white")
        row1.pack(fill="x", padx=14, pady=4)

        tk.Label(row1, text="策略", bg="white", font=("微软雅黑", 10)).pack(side="left")
        self.strategy_var = tk.StringVar(value="ma_crossover")
        ttk.Combobox(row1, textvariable=self.strategy_var, width=16,
                     values=["ma_crossover", "mean_reversion"],
                     font=("微软雅黑", 10), state="readonly").pack(side="left", padx=6)

        tk.Label(row1, text="股票代码", bg="white", font=("微软雅黑", 10)).pack(side="left", padx=(16, 0))
        self.symbols_entry = tk.Entry(row1, width=24, font=("微软雅黑", 10))
        self.symbols_entry.insert(0, "000001")
        self.symbols_entry.pack(side="left", padx=6)

        # 按钮行
        btn_row = tk.Frame(cfg, bg="white")
        btn_row.pack(fill="x", padx=14, pady=(6, 12))

        self.run_btn = tk.Button(btn_row, text="▶ 执行一次交易检查", font=("微软雅黑", 10, "bold"),
                                  bg="#e94560", fg="white", bd=0, padx=20, pady=5,
                                  cursor="hand2", command=self._do_trade)
        self.run_btn.pack(side="left")

        # 说明文字
        tk.Label(btn_row, text="实盘需在 .env 设 TRADE_MODE=live 并配置券商",
                 bg="white", fg="#999", font=("微软雅黑", 9)).pack(side="left", padx=14)

    def _build_log(self):
        log_frame = tk.Frame(self, bg="white", bd=0)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        tk.Label(log_frame, text="交易日志", font=("微软雅黑", 11, "bold"),
                 bg="white", fg="#333").pack(anchor="w", padx=14, pady=(10, 4))

        self.log_text = tk.Text(log_frame, font=("Consolas", 10), bg="#1a1a2e", fg="#00ff88",
                                 padx=12, pady=11, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def _update_mode_label(self):
        mode = config.TRADE_MODE
        if mode == "paper":
            self.mode_label.configure(text="📝 模拟交易 (Paper)", fg="#1a1a2e")
        elif mode == "live":
            self.mode_label.configure(text="🔴 实盘交易 (Live)", fg="#e94560")

    def _log(self, msg):
        """追加日志。"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _do_trade(self):
        symbols = [s.strip() for s in self.symbols_entry.get().split(",") if s.strip()]
        if not symbols:
            messagebox.showwarning("提示", "请输入股票代码")
            return

        strategy = self.strategy_var.get()

        if config.TRADE_MODE == "live":
            ok = messagebox.askokcancel("确认", "实盘模式！将产生真实交易，确认继续？")
            if not ok:
                return

        self.run_btn.configure(state="disabled", text="执行中...")
        self._log(f"[开始] {strategy} 扫描 {len(symbols)} 只股票")

        def task():
            try:
                init_db()
                run_live(strategy, symbols)
                self.root.after(0, lambda: self._log("[完成] 交易检查结束"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"[错误] {e}"))
                self.root.after(0, lambda: messagebox.showerror("错误", str(e)))
            finally:
                self.root.after(0, lambda: self.run_btn.configure(state="normal", text="▶ 执行一次交易检查"))

        threading.Thread(target=task, daemon=True).start()
