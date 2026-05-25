# 慧策系统 · A股量化交易

## 项目概览

```
                        慧策系统 架构一览
═══════════════════════════════════════════════════════════════

  数据源                          策略与AI                           执行与展示
 ────────────                ────────────────                ───────────────────
 
 流水线 A: akshare  ──→  data/ (SQLite)    ──→  strategy/   ──→  backtest/ (回测)
 (东方财富日线)           │                         │                    │
                          │                  ma_crossover             engine.py
                          │                  macd_strategy            broker.py
                          │                  mean_reversion           portfolio.py
                          │                  rsi_strategy             report.py
                          │                  my_strategy
                          │
 流水线 B: 慧源数据  ──→  review/ (SQLite)   ──→  huice.py (AI打板)
 (duanxianxia.cn)         │                        竞价→DeepSeek/Claude→指令→QMT
                          │
                     review/analytics.py ──→ app.py (Streamlit)
                     情绪周期/连板矩阵/主线/选股
                          │
                     live/ (实盘)
                       trader.py → 风控 → QMT下单

  用户界面:
    app.py (Streamlit Web @ :8501)  ←─ 主界面，8个页面（含市场雷达）
    menu.py (命令行菜单)             ←─ 新手友好
    gui/ (PyQt5桌面端)              ←─ 备用方案
```

## 2 条核心流水线

> **数据源铁律**：两条流水线使用不同的数据源，不可混用。

| | 流水线 A：传统量化 | 流水线 B：AI 短线打板 |
|---|---|---|
| **数据源** | **akshare**（东方财富） | **慧源数据**（duanxianxia.cn） |
| **用途** | 历史回测 + 策略研究 | 实盘决策 + 复盘分析 |
| **时态** | 历史日线（T+1 确认） | 盘中实时 + 竞价 + 当日复盘 |
| **存储** | `data/quant.db` (stocks/daily_bars) | `data/quant.db` (review_* 表) |
| **获取方式** | `data/fetch_daily.py` | `data/api.py` → `review/store.py` |
| **回测引擎** | `backtest/` | `review/analytics.py` |
| **实盘接口** | `live/trader.py` → xtquant | `huice.py` → AI → QMT |

### 慧源数据 (Huiyuan Data)

`duanxianxia.cn` 采集的 A 股实时市场数据，涵盖 **37 个 API 端点**，是流水线 B 的专属数据源。

```
慧源数据 = 竞价数据 + 板块强度 + 股票池 + 热点 + 复盘 + 龙虎榜 + 互动易
```

| 特性 | 说明 |
|------|------|
| 覆盖范围 | 16 竞价 Tab + 270 板块 + 7 股票池 + 6 热点类型 + 9 复盘 API |
| 时效性 | 盘中实时更新（竞价 9:15-9:25，板块/热点全天） |
| 历史深度 | 复盘数据 575 天情绪曲线 + 333 天已入库 |
| 认证 | 需 duanxianxia.cn 登录 session |
| 存储 | `review/store.py` 每日自动入库 5 张表 |
| 备份方案 | API 故障时 `auth.py` 自动重试 3 次轮询（2s→4s→8s） |

### 流水线 A：传统量化（回测→模拟→实盘）

```
akshare 日线 → 写策略 → backtest/ 回测 → live/ 模拟 → live/ 实盘
```

| 步骤 | 入口 | 命令 |
|------|------|------|
| 1. 拉数据 | `data/fetch_daily.py` | `python data/fetch_daily.py --symbols 000001 --start 20240101 --end 20251231` |
| 2. 写策略 | `strategy/my_strategy.py` | 继承 `Strategy` 类，实现 `on_bar()` |
| 3. 回测 | `backtest_main.py` | `python backtest_main.py --strategy ma_crossover --symbols 000001` |
| 4. 模拟 | `live_main.py` | `python live_main.py --strategy ma_crossover --symbols 000001` |
| 5. 实盘 | `live_main.py` + `.env` | `.env` 设 `TRADE_MODE=live` 后运行 |

### 流水线 B：AI 短线打板（竞价→AI→下单）

```
慧源数据(竞价) → AI分析(DeepSeek/Claude) → 解析指令 → 风控 → QMT下单
```

| 步骤 | 入口 | 命令 |
|------|------|------|
| 分析 | `huice.py` | `python huice.py --ai claude` |
| 模拟下单 | `huice.py` | `python huice.py --ai claude --trade` |
| 实盘下单 | `huice.py` | `python huice.py --ai claude --trade --live` |
| Web界面 | `app.py` | 时间轴页面 = huice.py 的可视化版本 |

## 项目文件地图

```
quant/
├── config.py              # 全局配置（券商/风控/手续费），从 .env 读取
├── .env                   # 密钥和模式配置（不要提交git）
├── huice.py               # ★ AI打板主程序（API直连数据→AI→解析→下单）
├── app.py                 # ★ Streamlit Web主界面（@ localhost:8501）
├── menu.py                # 命令行交互菜单（新手友好）
├── backtest_main.py       # 回测命令行入口
├── live_main.py           # 实盘命令行入口
├── connect_qmt_test.py    # QMT连接测试脚本
│
├── data/                  # 数据层
│   ├── models.py          # SQLite 建表（stocks, daily_bars）
│   ├── fetch_stocks.py    # 获取全A股列表
│   ├── fetch_daily.py     # 获取日线行情
│   ├── api.py             # ★ duanxianxia.cn 统一API封装（36个数据源，含8个复盘API）
│   ├── auth.py            # duanxianxia.cn 登录认证（session管理）
│   ├── fetch_sector.py    # 板块数据（270板块强度/资金流/成分股）
│   ├── fetch_auction.py   # 竞价数据（16个Tab：竞价/爆量/抢筹…）
│   ├── fetch_pool.py      # 股票池数据（涨停/连板/炸板/冲涨/大面/分析）
│   ├── fetch_hotspot.py   # 热点数据（题材/热搜/飙升/人气股）
│   ├── fetch_calendar.py  # 交易日历/政策要闻/数据源配置
│   ├── fetch_yidong.py    # 竞价异动数据（需登录，100条实时异动）
│   ├── fetch_fupan.py     # 复盘数据向后兼容重导出 → review/
│   ├── manager.py         # 统一查询接口（get_bars, get_stocks, get_today_bars）
│   └── quant.db           # SQLite 数据库
│
├── review/                # ★ 复盘专用模块
│   ├── __init__.py        # ReviewManager 统一入口
│   ├── fetcher.py         # 9 个 duanxianxia API + 概念/涨停解析
│   ├── longhu.py          # 龙虎榜（akshare，复盘专用）
│   ├── report.py          # 每日复盘整合 + 格式化输出
│   ├── store.py           # SQLite 存储 + 历史查询 + 回填
│   ├── analytics.py       # ★ 复盘分析引擎（板块持续性/情绪周期/连板矩阵/主线识别/选股）
│   ├── scheduler.py       # 每日自动采集调度器
│   └── cli.py             # 命令行入口
│
├── strategy/              # 策略层
│   ├── base.py            # 策略基类（on_init, on_bar, buy, sell, buy_pct, sell_all）
│   ├── indicators.py      # 技术指标库（sma, ema, rsi, macd, bollinger）
│   ├── ma_crossover.py    # 双均线交叉策略
│   ├── macd_strategy.py   # MACD金叉死叉策略
│   ├── mean_reversion.py  # 布林带回归策略
│   ├── rsi_strategy.py    # RSI超买超卖策略
│   └── my_strategy.py     # 用户自定义策略模板
│
├── backtest/              # 回测引擎
│   ├── engine.py          # 事件驱动回测引擎（逐日遍历）
│   ├── broker.py          # 模拟券商（撮合成交、计算费用）
│   ├── portfolio.py       # 投资组合（现金/持仓/净值跟踪）
│   └── report.py          # 报告生成（收益率/夏普/回撤/胜率）
│
├── live/                  # 实盘交易
│   ├── trader.py          # 实盘主流程（数据→策略→风控→下单）
│   ├── broker.py          # QMT券商接口（xtquant封装）
│   ├── risk.py            # 风控管理（仓位限制/日亏损/连续亏损）
│   └── scheduler.py       # 定时任务调度（每日14:55执行）
│
├── gui/                   # PyQt5桌面GUI（备用）
│   ├── main_window.py     # 主窗口
│   ├── page_data.py       # 数据页面
│   ├── page_backtest.py   # 回测页面
│   ├── page_live.py       # 交易页面
│   └── page_settings.py   # 设置页面
│
├── requirements.txt       # Python依赖
├── setup.bat              # 一键安装脚本
├── run.bat                # 一键启动 Streamlit
└── 分析提示.txt            # 分析提示模板（用于AI竞价分析）
```

## 关键依赖

```
streamlit      # Web 界面
pandas, numpy  # 数据处理
matplotlib     # 图表
akshare        # A股数据源（东方财富）
xtquant        # 国金MiniQMT下单接口（需在QMT安装目录）
loguru         # 日志
schedule       # 定时任务
python-dotenv  # 环境变量
```

## 当前开发进度

| 模块 | 状态 | 说明 |
|------|------|------|
| 数据获取 (akshare) | ✅ 完成 | 股票列表 + 日线行情 |
| 本地数据库 (SQLite) | ✅ 完成 | stocks / daily_bars 两张表 |
| 策略框架 | ✅ 完成 | 4 个内置策略 + 自定义模板 |
| 回测引擎 | ✅ 完成 | 事件驱动，含手续费/滑点 |
| 模拟交易 | ✅ 完成 | 本地模拟，不产生真实订单 |
| 实盘交易 (MiniQMT) | ✅ 完成 | 需启动 QMT 客户端 |
| AI 打板流水线 | ✅ 完成 | DeepSeek/Claude API 分析竞价 |
| 风控系统 | ✅ 完成 | 仓位/亏损/连续亏损限制 |
| 短线侠数据封装 (api.py) | ✅ 完成 | 19 公开数据源 + 1 CDN |
| Streamlit Web UI | ✅ 完成 | 8 页面（含市场雷达实时数据） |
| huice.py 数据目录 | ✅ 完成 | 自动检测 WorkBuddy 最新目录 |
| 定时调度 | ✅ 完成 | 每日定时 / 间隔执行 |
| PyQt5 GUI | ⚠️ 备用 | 功能不如 Web 版完整 |

## 日常使用场景

### 数据抓取（Python，无需 PowerShell）

```bash
# 板块数据
python data/fetch_sector.py                     # 板块强度 TOP20
python data/fetch_sector.py --flow              # 含主力资金流排行
python data/fetch_sector.py --sector 801660     # 通信板块成分股

# 竞价数据（16个Tab）
python data/fetch_auction.py                    # 全景模式（All）
python data/fetch_auction.py --tab Daban        # 涨停委买
python data/fetch_auction.py --tab Jingjia      # 集合竞价
python data/fetch_auction.py --tab Vratio       # 竞价爆量
python data/fetch_auction.py --tab Zhuli        # 竞价净额（主力流入）

# 股票池数据
python data/fetch_pool.py                       # 全部池子
python data/fetch_pool.py --pool Lb             # 连板池
python data/fetch_pool.py --pool Fx             # 分析池（主力资金）

# 热点数据
python data/fetch_hotspot.py                    # 全部热点
python data/fetch_hotspot.py --type HotDay      # 日热门股
python data/fetch_hotspot.py --type Topic       # 题材热点

# 复盘数据（需登录）
python data/fetch_fupan.py                       # 今日复盘概览（向后兼容）
python -m review.cli                              # 同上，推荐
python -m review.cli --date 20260522             # 指定日期
python -m review.cli --type lianban              # 连板天梯
python -m review.cli --type sentiment            # 情绪曲线
python -m review.cli --json                      # JSON 导出

# 复盘自动采集
python -m review.scheduler --now                # 立即采集一次（适合 Windows 计划任务）
python -m review.scheduler                      # 常驻进程，每日 15:30 自动采集
python -m review.scheduler --time 16:00         # 自定义采集时间

# 复盘分析引擎
python -m review.analytics                      # 板块持续性报告
python -m review.analytics --sentiment          # 情绪周期拐点识别
python -m review.analytics --lianban            # 连板胜率矩阵
python -m review.analytics --mainline           # 主线识别器
python -m review.analytics --screener           # 复盘驱动选股
```

### API 统一调用（Python 代码中使用）

```python
from data.api import duanxianxia as dx

# 一键获取所有数据类型
plates, sentiment = dx.sectors()        # 板块强度 + 市场情绪
stocks = dx.sector_stocks("801660")     # 板块成分股
flow = dx.sector_flow()                 # 板块资金流 TOP15
items = dx.auction("Daban", top=10)     # 竞价数据
items = dx.pool("Lb", top=10)           # 股票池
data = dx.hotspot("Topic", top=10)      # 热点数据
print(dx.market_overview())             # 一句话市场概况
dx.dump_all("snapshot.json")           # 导出全部数据

# 复盘数据（需登录）
# 推荐新接口: from review import ReviewManager
# rm = ReviewManager(); data = rm.review("20260522")
# 向后兼容:
date = dx.fupan_date()["date"]           # 最新复盘日期
sc = dx.sentiment_curve()               # 情绪曲线（575天历史）
lr = dx.lianban_range(date=date)        # 连板天梯
lc = dx.lianban_chart()                 # 连板统计图（龙头趋势）
dx.dump_review("review.json")          # 导出全部复盘数据
```

### 场景 1：验证一个策略想法
```
1. 打开 http://localhost:8501
2. 左侧 → "策略实验室" → 编辑 my_strategy.py → 保存
3. 左侧 → "回测分析" → 选 my_strategy → 开始回测
4. 看收益曲线/回撤/胜率 → 调整参数 → 再回测
```

### 场景 2：AI 短线打板（竞价分析）
```
1. 确保险商 WorkBuddy 已抓取竞价数据（jingjia_full.json）
2. python huice.py --ai claude           # 先看分析
3. python huice.py --ai claude --trade   # 模拟下单
4. python huice.py --ai claude --trade --live  # 实盘
```

### 场景 3：定时自动交易
```
python live/scheduler.py --strategy ma_crossover --symbols 000001,600519 --time 14:55
```
