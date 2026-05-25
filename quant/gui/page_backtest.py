"""策略回测页面（含收益曲线图表）。"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import importlib

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from data.models import init_db
from data.manager import get_bars
from strategy.base import Strategy
from backtest.engine import BacktestEngine


plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False


class BacktestPage(tk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent, bg="#f0f2f5")
        self.root = root

        self._title("策略回测")

        # 上半区：设置
        self._build_config()

        # 下半区：结果 + 图表
        self._build_result_area()

    def _title(self, text):
        tk.Label(self, text=text, font=("微软雅黑", 18, "bold"),
                 bg="#f0f2f5", fg="#1a1a2e").pack(anchor="w", padx=16, pady=(14, 8))

    def _build_config(self):
        cfg = tk.Frame(self, bg="white", bd=0)
        cfg.pack(fill="x", padx=16, pady=2)

        # 第一行
        row1 = tk.Frame(cfg, bg="white")
        row1.pack(fill="x", padx=14, pady=(12, 4))

        tk.Label(row1, text="策略", bg="white", font=("微软雅黑", 10)).pack(side="left")
        self.strategy_var = tk.StringVar(value="ma_crossover")
        strategy_menu = ttk.Combobox(row1, textvariable=self.strategy_var, width=16,
                                      values=["ma_crossover", "mean_reversion"],
                                      font=("微软雅黑", 10), state="readonly")
        strategy_menu.pack(side="left", padx=6)

        tk.Label(row1, text="股票代码", bg="white", font=("微软雅黑", 10)).pack(side="left", padx=(16, 0))
        self.symbols_entry = tk.Entry(row1, width=24, font=("微软雅黑", 10))
        self.symbols_entry.insert(0, "000001")
        self.symbols_entry.pack(side="left", padx=6)

        tk.Label(row1, text="初始资金", bg="white", font=("微软雅黑", 10)).pack(side="left", padx=(16, 0))
        self.cash_entry = tk.Entry(row1, width=10, font=("微软雅黑", 10))
        self.cash_entry.insert(0, "100000")
        self.cash_entry.pack(side="left", padx=6)

        # 第二行
        row2 = tk.Frame(cfg, bg="white")
        row2.pack(fill="x", padx=14, pady=4)

        tk.Label(row2, text="起始日期", bg="white", font=("微软雅黑", 10)).pack(side="left")
        self.start_entry = tk.Entry(row2, width=12, font=("微软雅黑", 10))
        self.start_entry.insert(0, "2024-01-01")
        self.start_entry.pack(side="left", padx=6)

        tk.Label(row2, text="结束日期", bg="white", font=("微软雅黑", 10)).pack(side="left", padx=(16, 0))
        self.end_entry = tk.Entry(row2, width=12, font=("微软雅黑", 10))
        self.end_entry.insert(0, "2024-12-31")
        self.end_entry.pack(side="left", padx=6)

        tk.Label(row2, text="参数", bg="white", font=("微软雅黑", 10)).pack(side="left", padx=(16, 0))
        self.params_entry = tk.Entry(row2, width=20, font=("微软雅黑", 10))
        self.params_entry.insert(0, "fast=5,slow=20")
        self.params_entry.pack(side="left", padx=6)

        self.run_btn = tk.Button(row2, text="▶ 开始回测", font=("微软雅黑", 10, "bold"),
                                  bg="#e94560", fg="white", bd=0, padx=20, pady=4,
                                  cursor="hand2", command=self._do_backtest)
        self.run_btn.pack(side="left", padx=(20, 0))

    def _build_result_area(self):
        # 指标栏
        self.metrics_frame = tk.Frame(self, bg="white", bd=0)
        self.metrics_frame.pack(fill="x", padx=16, pady=(8, 2))

        self.metric_labels = {}
        metrics = ["总收益率", "年化收益", "夏普比率", "最大回撤", "交易次数", "最终资金"]
        for i, m in enumerate(metrics):
            lbl = tk.Label(self.metrics_frame, text=f"{m}\n--", font=("微软雅黑", 9),
                           bg="white", fg="#333", justify="center", width=16)
            lbl.pack(side="left", padx=8, pady=10)
            self.metric_labels[m] = lbl

        # 图表区
        self.chart_frame = tk.Frame(self, bg="white", bd=0)
        self.chart_frame.pack(fill="both", expand=True, padx=16, pady=(2, 16))

        # 初始空图
        self.fig = Figure(figsize=(12, 4), dpi=100, facecolor="white")
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("回测收益曲线", fontsize=13, fontweight="bold", pad=10)
        self.ax.text(0.5, 0.5, "点击「开始回测」查看结果", ha="center", va="center",
                     fontsize=14, color="#aaa", transform=self.ax.transAxes)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, self.chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _do_backtest(self):
        symbols = [s.strip() for s in self.symbols_entry.get().split(",") if s.strip()]
        if not symbols:
            messagebox.showwarning("提示", "请输入股票代码")
            return

        # 解析参数
        params = {}
        if self.params_entry.get().strip():
            for pair in self.params_entry.get().strip().split(","):
                k, v = pair.split("=")
                k, v = k.strip(), v.strip()
                try:
                    params[k] = float(v) if "." in v else int(v)
                except ValueError:
                    params[k] = v

        self.run_btn.configure(state="disabled", text="回测中...")

        def task():
            try:
                init_db()
                data = get_bars(symbols, self.start_entry.get().strip(), self.end_entry.get().strip())
                if not data:
                    self.root.after(0, lambda: messagebox.showerror("错误", "无数据，请先获取数据"))
                    return

                # 加载策略
                mod = importlib.import_module(f"strategy.{self.strategy_var.get()}")
                strategy_cls = None
                for name in dir(mod):
                    attr = getattr(mod, name)
                    if isinstance(attr, type) and issubclass(attr, Strategy) and attr is not Strategy:
                        strategy_cls = attr
                        break

                if strategy_cls is None:
                    self.root.after(0, lambda: messagebox.showerror("错误", "策略加载失败"))
                    return

                cash = float(self.cash_entry.get())
                engine = BacktestEngine(initial_cash=cash)
                result = engine.run(strategy_cls, data, params=params, progress=False)

                # 回到主线程更新 UI
                self.root.after(0, lambda: self._update_ui(result, engine.broker.trades))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", str(e)))
            finally:
                self.root.after(0, lambda: self.run_btn.configure(state="normal", text="▶ 开始回测"))

        threading.Thread(target=task, daemon=True).start()

    def _update_ui(self, result, trades):
        """更新指标和图表（主线程）。"""
        if not result:
            return

        # 更新指标
        self.metric_labels["总收益率"].configure(
            text=f"总收益率\n{result.get('total_return', 0):+.2f}%")
        self.metric_labels["年化收益"].configure(
            text=f"年化收益\n{result.get('annual_return', 0):+.2f}%")
        self.metric_labels["夏普比率"].configure(
            text=f"夏普比率\n{result.get('sharpe_ratio', 0):.2f}")
        self.metric_labels["最大回撤"].configure(
            text=f"最大回撤\n{result.get('max_drawdown', 0):.2f}%")
        self.metric_labels["交易次数"].configure(
            text=f"交易次数\n{result.get('total_trades', 0)}")
        self.metric_labels["最终资金"].configure(
            text=f"最终资金\n{result.get('final_nav', 0):,.0f}")

        # 更新图表
        self.ax.clear()
        nav_series = result.get("nav_series", [])
        if nav_series:
            dates = [s["date"] for s in nav_series]
            navs = [s["nav"] for s in nav_series]
            self.ax.plot(dates, navs, color="#e94560", linewidth=1.8, label="净值曲线")
            self.ax.axhline(y=navs[0], color="#999", linewidth=0.8, linestyle="--", label="初始资金")
            self.ax.fill_between(range(len(dates)), navs, navs[0],
                                  where=[n >= navs[0] for n in navs],
                                  color="#e94560", alpha=0.08)
            self.ax.fill_between(range(len(dates)), navs, navs[0],
                                  where=[n < navs[0] for n in navs],
                                  color="#00b894", alpha=0.08)
            self.ax.set_title(f"收益曲线 (交易 {len(trades)} 笔)", fontsize=13, fontweight="bold")
            self.ax.legend(loc="upper left", frameon=True, fontsize=9)
            self.ax.set_ylabel("资产净值", fontsize=9)
            self.ax.grid(True, alpha=0.3)
            # 格式化 x 轴
            step = max(1, len(dates) // 10)
            self.ax.set_xticks(range(0, len(dates), step))
            self.ax.set_xticklabels([str(d)[:10] for d in dates[::step]], rotation=30, fontsize=7)

        self.fig.tight_layout()
        self.canvas.draw()
