"""主窗口 — 侧边栏导航 + 页面切换。"""

import tkinter as tk
from tkinter import ttk

from gui.page_data import DataPage
from gui.page_backtest import BacktestPage
from gui.page_live import LivePage
from gui.page_settings import SettingsPage


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("A股量化交易系统")
        self.root.geometry("1100x720")
        self.root.configure(bg="#f0f2f5")
        self.root.minsize(900, 600)

        self._build_sidebar()
        self._build_content()

        self.pages = {}
        self._show_page("backtest")

    def _build_sidebar(self):
        sidebar = tk.Frame(self.root, bg="#1a1a2e", width=160)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # 标题
        tk.Label(sidebar, text="量化交易", font=("微软雅黑", 14, "bold"),
                 bg="#1a1a2e", fg="#e94560").pack(pady=(20, 30))

        # 导航按钮
        btns = [
            ("  数据管理", "data", "📊"),
            ("  策略回测", "backtest", "📈"),
            ("  实时交易", "live", "💹"),
            ("  系统设置", "settings", "⚙"),
        ]
        self.nav_btns = {}
        for text, key, icon in btns:
            btn = tk.Button(sidebar, text=f"{icon} {text}", font=("微软雅黑", 11),
                            bg="#16213e", fg="#ccc", bd=0, padx=16, pady=10,
                            anchor="w", width=18, cursor="hand2",
                            activebackground="#e94560", activeforeground="white",
                            command=lambda k=key: self._show_page(k))
            btn.pack(pady=2)
            self.nav_btns[key] = btn

        # 底部署名
        tk.Label(sidebar, text="v1.0", font=("微软雅黑", 8),
                 bg="#1a1a2e", fg="#555").pack(side="bottom", pady=10)

    def _build_content(self):
        self.content = tk.Frame(self.root, bg="#f0f2f5")
        self.content.pack(side="left", fill="both", expand=True)

    def _show_page(self, key):
        # 高亮当前按钮
        for k, btn in self.nav_btns.items():
            if k == key:
                btn.configure(bg="#e94560", fg="white")
            else:
                btn.configure(bg="#16213e", fg="#ccc")

        # 清除当前页面
        for w in self.content.winfo_children():
            w.destroy()

        # 显示对应页面
        if key not in self.pages:
            if key == "data":
                self.pages[key] = DataPage(self.content, self.root)
            elif key == "backtest":
                self.pages[key] = BacktestPage(self.content, self.root)
            elif key == "live":
                self.pages[key] = LivePage(self.content, self.root)
            elif key == "settings":
                self.pages[key] = SettingsPage(self.content, self.root)

        page = self.pages[key]
        page.pack(fill="both", expand=True)

    def run(self):
        self.root.mainloop()
