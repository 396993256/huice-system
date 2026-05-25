"""系统设置页面。"""

import tkinter as tk
from tkinter import ttk, messagebox
import os

from config import config, BASE_DIR


class SettingsPage(tk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent, bg="#f0f2f5")
        self.root = root
        self.env_path = BASE_DIR / ".env"

        self._title("系统设置")

        # 当前配置展示
        self._build_config_display()

        # 编辑区
        self._build_editor()

        # 说明
        self._build_help()

    def _title(self, text):
        tk.Label(self, text=text, font=("微软雅黑", 18, "bold"),
                 bg="#f0f2f5", fg="#1a1a2e").pack(anchor="w", padx=16, pady=(14, 8))

    def _build_config_display(self):
        cfg = tk.Frame(self, bg="white", bd=0)
        cfg.pack(fill="x", padx=16, pady=2)

        tk.Label(cfg, text="当前配置", font=("微软雅黑", 12, "bold"),
                 bg="white", fg="#333").pack(anchor="w", padx=14, pady=(12, 4))

        info_frame = tk.Frame(cfg, bg="white")
        info_frame.pack(fill="x", padx=14, pady=4)

        items = [
            ("交易模式", config.TRADE_MODE, "paper=模拟 / live=实盘"),
            ("券商类型", config.BROKER, "ht=华泰 / gj=国金 / yh=银河"),
            ("数据库路径", config.DATA_DB_PATH, ""),
            ("佣金费率", f"{config.COMMISSION_RATE*10000:.1f}‱", ""),
            ("印花税率", f"{config.STAMP_DUTY_RATE*1000:.1f}‰", "仅卖出"),
            ("单票仓位上限", f"{config.MAX_SINGLE_STOCK_PCT*100:.0f}%", ""),
            ("单日最大亏损", f"{config.MAX_DAILY_LOSS_PCT*100:.0f}%", "触发停止交易"),
        ]
        for label, value, note in items:
            row = tk.Frame(info_frame, bg="white")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{label}:", bg="white", font=("微软雅黑", 10, "bold"),
                     width=14, anchor="w").pack(side="left")
            tk.Label(row, text=str(value), bg="white", font=("微软雅黑", 10),
                     fg="#e94560").pack(side="left")
            if note:
                tk.Label(row, text=f"  ({note})", bg="white", font=("微软雅黑", 9),
                         fg="#999").pack(side="left")

    def _build_editor(self):
        cfg = tk.Frame(self, bg="white", bd=0)
        cfg.pack(fill="x", padx=16, pady=(8, 2))

        sep = ttk.Separator(cfg, orient="horizontal")
        sep.pack(fill="x", padx=14, pady=8)

        tk.Label(cfg, text="编辑 .env 配置", font=("微软雅黑", 12, "bold"),
                 bg="white", fg="#333").pack(anchor="w", padx=14, pady=(4, 4))

        # 读取当前 .env
        current_env = ""
        if self.env_path.exists():
            with open(self.env_path, "r", encoding="utf-8") as f:
                current_env = f.read()

        self.env_editor = tk.Text(cfg, font=("Consolas", 10), bg="#1a1a2e", fg="#00ff88",
                                   padx=12, pady=11, height=10, wrap="none")
        self.env_editor.insert("1.0", current_env)
        self.env_editor.pack(fill="x", padx=14, pady=(4, 8))

        btn_row = tk.Frame(cfg, bg="white")
        btn_row.pack(fill="x", padx=14, pady=(0, 12))

        self.save_btn = tk.Button(btn_row, text="💾 保存配置", font=("微软雅黑", 10),
                                   bg="#e94560", fg="white", bd=0, padx=20, pady=4,
                                   cursor="hand2", command=self._save_env)
        self.save_btn.pack(side="left")

        tk.Label(btn_row, text="修改后需重启应用生效", bg="white",
                 font=("微软雅黑", 9), fg="#999").pack(side="left", padx=12)

    def _build_help(self):
        cfg = tk.Frame(self, bg="white", bd=0)
        cfg.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        tk.Label(cfg, text="券商配置说明", font=("微软雅黑", 12, "bold"),
                 bg="white", fg="#333").pack(anchor="w", padx=14, pady=(12, 4))

        help_text = (
            "▎华泰证券 (ht)\n"
            "  需要安装并打开涨乐财富通客户端，easytrader 会自动识别。\n\n"
            "▎国金证券 (gj)\n"
            "  需要安装佣金宝客户端，使用账号密码登录。\n\n"
            "▎银河证券 (yh)\n"
            "  支持银河证券客户端。\n\n"
            "▎模拟交易 (paper)\n"
            "  不需要真实券商，系统会在本地模拟买卖，用于策略验证。\n"
            "  建议先用 paper 模式跑一周，确认没问题再切换 live。\n\n"
            "▎风控规则\n"
            "  单只股票持仓不超过总资产 20%\n"
            "  单日亏损超过 3% 自动停止交易\n"
            "  连续亏损 3 笔暂停交易"
        )
        help_label = tk.Label(cfg, text=help_text, font=("微软雅黑", 9),
                               bg="white", fg="#555", justify="left", anchor="w")
        help_label.pack(fill="both", padx=14, pady=(4, 14))

    def _save_env(self):
        content = self.env_editor.get("1.0", "end-1c")
        try:
            with open(self.env_path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("提示", "配置已保存。重启应用后生效。")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")
