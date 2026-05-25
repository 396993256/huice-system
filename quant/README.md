# A股量化炒股系统 — 新手使用指南

## 第一步：安装环境

你只需要装一个 Python（3.10 以上版本）。

然后打开终端（PowerShell 或 CMD），进入项目目录：

```bash
cd quant
pip install -r requirements.txt
```

## 第二步：获取数据

```bash
# 初始化数据库（只需一次）
python data/models.py

# 获取股票列表（只需一次）
python data/fetch_stocks.py

# 获取日线数据（按需获取）
python data/fetch_daily.py --symbols 000001,600519,000858 --start 20240101 --end 20251231
```

参数说明：
- `--symbols`：股票代码，逗号分隔
- `--start`：起始日期 YYYYMMDD
- `--end`：结束日期 YYYYMMDD

## 第三步：回测策略

```bash
python backtest_main.py --strategy ma_crossover --symbols 000001 --start 2024-01-01 --end 2024-12-31 --cash 100000
```

参数说明：
- `--strategy`：策略名（ma_crossover=双均线, mean_reversion=布林带回归）
- `--symbols`：回测股票
- `--start / --end`：回测日期范围
- `--cash`：初始资金，默认 10 万
- `--params`：策略参数，如 `fast=5,slow=20`

## 第四步：模拟交易

**先用模拟模式验证，不要直接实盘！**

```bash
python live_main.py --strategy ma_crossover --symbols 000001,600519
```

## 第五步：实盘交易（需券商）

1. 编辑 `.env` 文件，填入你的券商账号：
```
TRADE_MODE=live
BROKER=ht
BROKER_USER=你的账号
BROKER_PASSWORD=你的密码
```

2. 打开券商客户端（涨乐财富通/佣金宝等）并登录

3. 运行：
```bash
python live_main.py --strategy ma_crossover --symbols 000001,600519
```

## 写自己的策略

在 [strategy/my_strategy.py](strategy/my_strategy.py) 中编写，参考 [strategy/ma_crossover.py](strategy/ma_crossover.py)。

## 定时自动交易

```bash
python live/scheduler.py --strategy ma_crossover --symbols 000001 --time 14:55
```

## 常见问题

**Q: akshare 获取数据失败？**
A: 网络问题，换个时间重试。数据源是东方财富。

**Q: easytrader 连不上券商？**
A: 确认券商客户端已打开并登录，验证码已手动处理。

**Q: 策略不产生交易？**
A: 正常，不是每天都有买卖信号。先跑回测确认策略逻辑。
