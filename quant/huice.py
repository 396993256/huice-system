#!/usr/bin/env python3
"""
慧策系统 v3 — 短线打板 AI 全自动交易
=======================================
流程（一键完成）:
  1. 读取短线侠竞价数据 (jingjia_full.json)
  2. 调用 AI（DeepSeek/Claude）分析数据，返回买卖信号
  3. 解析信号 → 通过 xtquant → MiniQMT 下单

用法:
  python huice.py                       # AI 分析模式（不下单）
  python huice.py --trade               # AI 分析 + 模拟下单
  python huice.py --trade --live        # AI 分析 + 实盘下单
  python huice.py --ai claude           # 用 Claude API 分析
  python huice.py --ai deepseek         # 用 DeepSeek API 分析（默认）
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# 强制 UTF-8 输出（解决 Windows GBK 兼容问题）
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ============================================================
# 配置
# ============================================================
BASE_DIR = Path(__file__).parent

def _find_latest_data_dir():
    """在 WorkBuddy 目录中找到最新的包含 jingjia_full.json 的子目录。"""
    workbuddy = Path(r"C:\Users\Administrator\WorkBuddy")
    if not workbuddy.exists():
        return None
    candidates = []
    for subdir in workbuddy.iterdir():
        if subdir.is_dir() and (subdir / "jingjia_full.json").exists():
            candidates.append((subdir.stat().st_mtime, str(subdir)))
    candidates.sort(reverse=True)
    return candidates[0][1] if candidates else None

DATA_DIR = _find_latest_data_dir() or r"C:\Users\Administrator\WorkBuddy\20260512110241"

# QMT
QMT_LIB = r"D:\国金QMT交易端模拟\bin.x64\Lib\site-packages"
QMT_USERDATA = r"D:\国金QMT交易端模拟\userdata_mini"
QMT_SESSION = 888888

# AI API Keys（优先从 .env 读取）
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=True)
except ImportError:
    pass

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", os.environ.get("CUSTOM_API_KEY", ""))
DEEPSEEK_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
CLAUDE_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", os.environ.get("ANTHROPIC_API_KEY", ""))
CLAUDE_BASE = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")


# ============================================================
# Part 1: 数据加载 — 双模式：API直连 / 文件回退
# ============================================================

# 导入统一 API
sys.path.insert(0, str(BASE_DIR))
from data.api import (
    market_overview, sectors, auction, pool, hotspot,
    yidong_all, yidong_summary_data,
)
from data.api import _get_auth_opener  # 登录认证
from review import ReviewManager  # 复盘数据


def load_market_data(use_api=True):
    """加载市场全景数据。优先用 API 直连，失败则回退到 WorkBuddy 文件。
    返回 {market, sectors, auction, pools, yidong, fetched_at}
    """
    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = {"fetched_at": fetched_at}

    print("  [数据] 获取市场概况...")
    try:
        result["market"] = market_overview()
    except Exception as e:
        result["market"] = f"获取失败: {e}"

    print("  [数据] 获取板块强度...")
    try:
        plates, sentiment = sectors()
        result["sectors"] = plates[:30]  # TOP30
        result["sentiment"] = sentiment
    except Exception as e:
        result["sectors"] = []
        result["sentiment"] = None
        print(f"  [!] 板块数据失败: {e}")

    print("  [数据] 获取竞价数据...")
    auction_data = {}
    for tab in ["Daban", "Vratio", "Zhuli", "Qiangchou", "Ztlast"]:
        try:
            items = auction(tab, top=30)
            auction_data[tab] = items
        except Exception:
            auction_data[tab] = []
    result["auction"] = auction_data

    print("  [数据] 获取股票池...")
    try:
        result["pools"] = pool("All", top=20)
    except Exception:
        result["pools"] = {}

    print("  [数据] 获取竞价异动...")
    try:
        result["yidong"] = yidong_all()
    except Exception:
        result["yidong"] = []

    print("  [数据] 获取热点题材...")
    try:
        result["hotspot"] = hotspot("All", top=10)
    except Exception:
        result["hotspot"] = {}

    return result


def load_review_context(date=None):
    """加载最近交易日的复盘数据作为 AI 分析上下文。
    返回格式化文本，失败返回 None。
    """
    try:
        print("  [数据] 获取复盘上下文...")
        rm = ReviewManager()
        data = rm.review(date)
        if data.get("error"):
            print(f"  [!] 复盘数据不可用: {data['error']}")
            return None
        return _format_review_text(data)
    except Exception as e:
        print(f"  [!] 复盘数据获取失败: {e}")
        return None


def _format_review_text(data):
    """将复盘数据格式化为 AI 可读的上下文。"""
    lines = []
    date = data.get("date", "")
    ind = data.get("indicators", {})
    from review.fetcher import INDICATOR_LABELS
    labels = data.get("indicator_labels", INDICATOR_LABELS)

    lines.append(f"## 0. 前一日复盘数据 ({date})\n")

    # 核心指标
    core = ["ZT", "DT", "LBGD", "FB", "KQXY", "HSLN", "ZHULI", "ZTBX", "LBBX", "SZ", "XD"]
    vals = []
    for k in core:
        v = ind.get(k)
        if v is not None:
            vals.append(f"{labels.get(k,k)}={v}")
    lines.append("核心指标: " + ", ".join(vals))
    lines.append("")

    # 晋级率
    jj = ["jinji_1_2", "jinji_2_3", "jinji_3_4", "jinji_lianban"]
    jv = []
    for k in jj:
        v = ind.get(k)
        if v is not None:
            jv.append(f"{labels.get(k,k)}={v}%")
    if jv:
        lines.append("晋级率: " + ", ".join(jv))
        lines.append("")

    # 板块强度 TOP10
    sectors = data.get("sectors", [])
    if sectors:
        lines.append("板块强度 TOP10:")
        for s in sectors[:10]:
            lines.append(f"  {s['name']} (强度{s['strength']})")
        lines.append("")

    # 概念分组 + 启动理由
    cgs = data.get("concept_groups", [])
    if cgs:
        lines.append("涨停概念分组 (含板块启动理由):")
        for cg in cgs[:8]:
            reason = f" — {cg['reason']}" if cg.get('reason') else ""
            lines.append(f"  {cg['concept']}: {cg['stock_count']}只涨停{reason}")
        lines.append("")

    # 连板天梯 TOP
    zt_lianban = data.get("zt_by_lianban", [])
    if zt_lianban:
        lines.append("连板梯队 TOP10:")
        for z in zt_lianban[:10]:
            lines.append(f"  {z['name']}({z['code']}) {z['ban_count']} L{z['lianban']} "
                        f"{z['chg_pct']} 封单{z['seal_amount']} 换手{z['turn_rate']}")
        lines.append("")

    # 龙虎榜概览
    lh = data.get("longhu_list", [])
    if lh:
        # 只统计涨停相关的龙虎榜
        lh_in_zt = [l for l in lh if any(z.get("code") == l["code"] for z in zt_lianban)]
        if lh_in_zt:
            lines.append(f"龙虎榜上榜: {len(lh_in_zt)}只涨停股 (共{len(lh)}只)")
            for l in lh_in_zt[:8]:
                lines.append(f"  {l['name']}({l['code']}) {l['chg_pct']:+.2f}% — {l['reason']}")
        else:
            lines.append(f"龙虎榜上榜: {len(lh)}只")
        lines.append("")

    return "\n".join(lines)


def load_jingjia_file():
    """[回退] 从 WorkBuddy 文件加载竞价数据。"""
    path = os.path.join(DATA_DIR, "jingjia_full.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    data = json.loads(json.loads(raw))
    return {
        "total": data["total"],
        "headers": data["headers"],
        "rows": data["data"],
        "fetched_at": datetime.fromtimestamp(os.path.getmtime(path)),
    }


def format_data_table(market_data):
    """将市场数据格式化为 AI 易读的文本。支持新旧两种数据格式。"""
    lines = []
    ts = market_data.get("fetched_at", datetime.now().strftime("%Y-%m-%d %H:%M"))

    # ── 市场情绪 ──
    sentiment = market_data.get("sentiment")
    if sentiment:
        lines.append("## 1. 市场情绪\n")
        lines.append(f"情绪值:{sentiment['emotion']} "
                     f"涨停:{sentiment['zt_count']} 跌停:{sentiment['dt_count']} "
                     f"上涨:{sentiment['up_count']} 下跌:{sentiment['down_count']} "
                     f"主力净:{sentiment['main_flow']}亿 封板率:{sentiment['seal_rate']}% "
                     f"连板高度:{sentiment['lianban_height']}")
        lines.append("")

    # ── 板块强度 ──
    sectors_list = market_data.get("sectors", [])
    if sectors_list:
        lines.append("## 2. 板块强度 TOP15\n")
        lines.append("| 排名 | 板块 | 强度 | 涨停数 |")
        lines.append("|------|------|------|--------|")
        for p in sectors_list[:15]:
            lines.append(f"| {p['rank']} | {p['name']} | {p['strength']} | {p['ztcount']} |")
        lines.append("")

    # ── 竞价数据 ──
    auction_data = market_data.get("auction", {})
    if auction_data:
        lines.append("## 3. 竞价数据\n")

        # 涨停委买
        daban = auction_data.get("Daban", [])
        if daban:
            lines.append(f"### 涨停委买 TOP20 (共{len(daban)}只)\n")
            lines.append("| # | 股票 | 代码 | 涨幅 | 封单 | 换手 | 板型 | 人气 | 概念 |")
            lines.append("|---|------|------|------|------|------|------|------|------|")
            for i, item in enumerate(daban[:20]):
                lines.append(
                    f"| {i+1} | {item.get('name','')} | {item.get('code','')} | "
                    f"{item.get('chg_pct','')} | {item.get('fengdan','')} | "
                    f"{item.get('turn_rate','')} | {item.get('ban_type','')} | "
                    f"{item.get('popular','')} | {item.get('concept','')} |"
                )
            lines.append("")

        # 竞价爆量
        vratio = auction_data.get("Vratio", [])
        if vratio:
            lines.append(f"### 竞价爆量 TOP15 (共{len(vratio)}只)\n")
            lines.append("| # | 股票 | 代码 | 涨幅 | 竞涨% | 竞额 | 量比 | 换手 | 概念 |")
            lines.append("|---|------|------|------|------|------|------|------|------|")
            for i, item in enumerate(vratio[:15]):
                lines.append(
                    f"| {i+1} | {item.get('name','')} | {item.get('code','')} | "
                    f"{item.get('chg_pct','')} | {item.get('jj_chg','')} | "
                    f"{item.get('jj_amount','')} | {item.get('vratio','')} | "
                    f"{item.get('turn_rate','')} | {item.get('concept','')} |"
                )
            lines.append("")

        # 竞价净额
        zhuli = auction_data.get("Zhuli", [])
        if zhuli:
            lines.append(f"### 竞价净额 TOP15 (共{len(zhuli)}只)\n")
            lines.append("| # | 股票 | 代码 | 涨幅 | 竞涨% | 净流入 | 人气 | 概念 |")
            lines.append("|---|------|------|------|------|------|------|------|")
            for i, item in enumerate(zhuli[:15]):
                lines.append(
                    f"| {i+1} | {item.get('name','')} | {item.get('code','')} | "
                    f"{item.get('chg_pct','')} | {item.get('jj_chg','')} | "
                    f"{item.get('net_inflow','')} | {item.get('popular','')} | "
                    f"{item.get('concept','')} |"
                )
            lines.append("")

    # ── 股票池 ──
    pools = market_data.get("pools", {})
    if pools:
        lines.append("## 4. 股票池\n")
        for pkey in ["Lb", "Zt", "Fx"]:
            if pkey in pools:
                info = pools[pkey]
                lines.append(f"### {info['name']} ({info['count']}只)\n")
                items = info.get("data", [])[:10]
                for item in items:
                    code = item.get('code', '-')
                    name = item.get('name', '-')
                    chg = item.get('chg_pct', '-')
                    concept = item.get('concept', '-')
                    lb = item.get('lb_count', item.get('lb_height', ''))
                    extra = f" {lb}板" if lb else ""
                    lines.append(f"- {code} {name} {chg}% {concept}{extra}")
                lines.append("")

    # ── 竞价异动 ──
    yidong = market_data.get("yidong", [])
    if yidong:
        lines.append(f"## 5. 竞价异动 (共{len(yidong)}条)\n")
        lines.append("| 时间 | 类型 | 股票 | 代码 | 板型 | 说明 |")
        lines.append("|------|------|------|------|------|------|")
        for e in yidong[:30]:
            lines.append(
                f"| {e.get('time','')} | {e.get('type','')} | "
                f"{e.get('name','')} | {e.get('code','')} | "
                f"{e.get('ban_desc','')} | {e.get('desc','')} |"
            )
        lines.append("")

    # ── 热点 ──
    hots = market_data.get("hotspot", {})
    if hots:
        topics = hots.get("stock_topic", [])
        if topics:
            lines.append("## 6. 热点题材\n")
            for t in topics[:10]:
                lines.append(f"- #{t.get('rank','')} {t.get('title','')} (热度:{t.get('rate','')})")
            lines.append("")

    return "\n".join(lines)


# ============================================================
# Part 2: AI 分析引擎
# ============================================================

SYSTEM_PROMPT = """你是一个A股短线打板交易专家。你会收到当日完整的市场数据，包括：

- 前一日复盘数据（市场指标/板块强度/概念分组与启动理由/连板梯队/龙虎榜）
- 市场情绪（涨停数/跌停数/上涨数/下跌数/主力资金流/封板率）
- 板块强度排行（主力资金进攻方向）
- 竞价数据（涨停委买/竞价爆量/竞价净额）
- 股票池（连板池/涨停池/分析池）
- 竞价异动（封涨大减/涨停回封/涨停打开等实时异动）
- 热点题材

请完成以下分析并输出交易指令：

### 1. 主线判断
对比昨日复盘数据与今日板块强度/热点题材，判断主线是延续还是切换，找出今日最强主线题材（1-2个）。

### 2. 连板晋级预判
结合昨日连板梯队和今日竞价数据，预判哪些连板股有望晋级（关注：竞价量比、封单变化、板块持续性）。

### 3. 龙头推荐
综合竞价数据+连板池+竞价异动+昨日复盘，选出 TOP 5 最值得打的板。
标准：封单金额大 > 竞价量比高 > 连板数合理（2-4板最优） > 题材是主线。

### 4. 交易指令
输出格式（每行一条，严格遵守）：
买入: 代码 数量股 价格 理由
卖出: 代码 数量股 价格 理由

- 代码用纯数字（如 000725 不是 000725.SZ）
- 数量必须是100的整数倍（A股1手=100股）
- 价格填"市价"或具体数字
- 如果建议空仓，输出：买入: 无 0 空仓 市场风险过高

### 5. 风控评估
市场情绪: [乐观/中性/谨慎]
建议仓位: [全仓/7成/5成/3成/空仓]
风险提示: [一句话]"""


def call_deepseek(data_text):
    """调用 DeepSeek API 分析数据。"""
    import openai

    if not DEEPSEEK_KEY:
        raise RuntimeError("未设置 DEEPSEEK_API_KEY 环境变量")

    client_kwargs = {"api_key": DEEPSEEK_KEY}
    if DEEPSEEK_BASE:
        client_kwargs["base_url"] = DEEPSEEK_BASE
    client = openai.OpenAI(**client_kwargs)

    print("[AI] 调用 DeepSeek 分析中...")
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": data_text},
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    return resp.choices[0].message.content


def call_claude(data_text):
    """调用 Claude API 分析数据。"""
    import anthropic

    if not CLAUDE_KEY:
        raise RuntimeError("未设置 ANTHROPIC_API_KEY 环境变量")

    client_kwargs = {"api_key": CLAUDE_KEY}
    if CLAUDE_BASE and CLAUDE_BASE != "https://api.anthropic.com":
        client_kwargs["base_url"] = CLAUDE_BASE
    client = anthropic.Anthropic(**client_kwargs)

    print("[AI] 调用 Claude 分析中...")
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2000,
        temperature=0.3,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": data_text}],
    )
    # Opus 4.7 默认带 ThinkingBlock，需找出 TextBlock
    for block in resp.content:
        if hasattr(block, "text"):
            return block.text
    return ""


def ai_analyze(data_text, engine="deepseek"):
    """调用 AI 分析市场数据，返回分析文本。data_text 是已格式化的文本。"""
    print(f"[AI] 使用引擎: {engine}")
    print(f"[AI] 数据量: {len(data_text)} 字符")

    if engine == "deepseek":
        result = call_deepseek(data_text)
    elif engine == "claude":
        result = call_claude(data_text)
    else:
        raise ValueError(f"不支持的 AI 引擎: {engine}")

    print(f"[AI] 分析完成, 返回 {len(result)} 字符")
    return result


# ============================================================
# Part 3: 交易指令解析 & 执行
# ============================================================

def parse_orders(text):
    """从 AI 分析文本中解析买卖指令。"""
    buys, sells = [], []

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        is_buy = line.startswith("买入")
        is_sell = line.startswith("卖出")

        if not (is_buy or is_sell):
            continue

        # 统一格式
        line = line.replace("：", ":")
        tag = "买入:" if is_buy else "卖出:"
        body = line.split(":", 1)[1] if ":" in line else line[2:]
        parts = body.strip().split()

        if len(parts) < 1:
            continue

        code = parts[0]

        # 检查空仓信号
        if code in ("无", "空", "空仓"):
            continue

        # 解析数量
        vol = 0
        if len(parts) >= 2:
            vol_str = parts[1].replace("股", "").replace(",", "").replace("手", "")
            try:
                vol = int(vol_str)
                if parts[1].endswith("手"):
                    vol *= 100
            except ValueError:
                continue

        if vol <= 0:
            continue

        # 确保数量是 100 的整数倍
        vol = (vol // 100) * 100
        if vol == 0:
            continue

        # 解析价格
        price = None
        if len(parts) >= 3:
            price_str = parts[2]
            if price_str in ("市价", "market", "最新价"):
                price = None
            else:
                try:
                    price = float(price_str)
                except ValueError:
                    price = None

        reason = parts[3] if len(parts) >= 4 else ""
        (buys if is_buy else sells).append((code, vol, price, reason))

    return buys, sells


# ============================================================
# Part 4: xtquant 下单执行
# ============================================================

def code_suffix(c):
    if c.startswith("6"): return "SH"
    if c.startswith(("0","3")): return "SZ"
    if c.startswith(("8","4")): return "BJ"
    return "SZ"

def to_xt(c):
    return c if "." in c else f"{c}.{code_suffix(c)}"


class QmtTrader:
    def __init__(self, live=False):
        self.live = live
        self._t = None
        self._a = None
        if QMT_LIB not in sys.path:
            sys.path.insert(0, QMT_LIB)

    def connect(self):
        from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
        from xtquant.xttype import StockAccount
        from xtquant import xtconstant

        class CB(XtQuantTraderCallback):
            def on_connected(self): print("[QMT] 已连接")
            def on_disconnected(self): print("[QMT] 断开")
            def on_stock_order(self, o):
                print(f"[QMT] 委托 {o.stock_code} #{o.order_id} 状态={o.order_status}")
            def on_stock_trade(self, t):
                print(f"[QMT] >>> 成交 <<< {t.stock_code} {t.traded_volume}股 @{t.traded_price:.2f}")
            def on_order_error(self, e):
                print(f"[QMT] 委托失败: {e.error_msg}")

        self._t = XtQuantTrader(QMT_USERDATA, QMT_SESSION, CB())
        self._t.start()
        if self._t.connect() != 0:
            print("[QMT] 连接失败，请确认 MiniQMT 已启动并登录")
            return False

        time.sleep(0.5)
        accs = self._t.query_account_infos()
        if not accs:
            print("[QMT] 未找到账号")
            return False

        for a in accs:
            if a.m_nAccountType == xtconstant.SECURITY_ACCOUNT:
                self._a = StockAccount(a.m_strAccountID, "STOCK")
                break
        if not self._a:
            self._a = StockAccount(accs[0].m_strAccountID)

        self._t.subscribe(self._a)

        # 显示资产
        asset = self._t.query_stock_asset(self._a)
        if asset:
            print(f"[QMT] 可用:{asset.m_dCash:,.0f} 市值:{asset.m_dMarketValue:,.0f} "
                  f"总:{asset.m_dTotalAsset:,.0f}")

        # 显示持仓
        positions = self._t.query_stock_positions(self._a)
        if positions:
            print(f"[QMT] 持仓 {len(positions)} 只:")
            for p in positions:
                print(f"  {p.m_strStockCode} {p.m_nVolume}股 "
                      f"成本{p.m_dOpenPrice:.2f} 市值{p.m_dMarketValue:.0f}")
        else:
            print("[QMT] 空仓")
        return True

    def buy(self, code, vol, price=None):
        from xtquant import xtconstant
        xc = to_xt(code)
        pt = xtconstant.FIX_PRICE if price else xtconstant.LATEST_PRICE
        pr = price if price else 0
        if self.live:
            oid = self._t.order_stock(self._a, xc, xtconstant.STOCK_BUY, vol, pt, pr, "慧策")
            tag = "实盘" if oid != -1 else "失败"
            print(f"[{tag}] 买入 {xc} {vol}股 @{pr or '市价'}")
            return oid
        else:
            print(f"[模拟] 买入 {xc} {vol}股 @{pr or '市价'}")
            return f"SIM-{int(time.time())}"

    def sell(self, code, vol, price=None):
        from xtquant import xtconstant
        xc = to_xt(code)
        pt = xtconstant.FIX_PRICE if price else xtconstant.LATEST_PRICE
        pr = price if price else 0
        if self.live:
            oid = self._t.order_stock(self._a, xc, xtconstant.STOCK_SELL, vol, pt, pr, "慧策")
            tag = "实盘" if oid != -1 else "失败"
            print(f"[{tag}] 卖出 {xc} {vol}股 @{pr or '市价'}")
            return oid
        else:
            print(f"[模拟] 卖出 {xc} {vol}股 @{pr or '市价'}")
            return f"SIM-{int(time.time())}"

    def close(self):
        if self._t:
            if self._a:
                self._t.unsubscribe(self._a)
            self._t.stop()


# ============================================================
# Main
# ============================================================

def main():
    p = argparse.ArgumentParser(description="慧策系统 v3 — AI 短线打板全自动交易")
    p.add_argument("--ai", choices=["deepseek", "claude"], default="deepseek",
                   help="AI 引擎 (默认 deepseek)")
    p.add_argument("--trade", action="store_true", help="AI分析后自动执行交易")
    p.add_argument("--live", action="store_true", help="实盘模式（默认模拟）")
    p.add_argument("--review", action="store_true", default=True,
                   help="注入前一日复盘数据作为分析上下文（默认开启）")
    p.add_argument("--no-review", action="store_true", help="禁用复盘上下文")
    args = p.parse_args()

    print("=" * 55)
    print("  慧策系统 v3 · AI 短线打板全自动交易")
    print("=" * 55)

    # ---- Step 1: 加载数据 ----
    print("\n[1/4] 加载市场数据...")

    # 优先使用 API 直连
    try:
        market_data = load_market_data(use_api=True)
        data_text = format_data_table(market_data)
        print(f"   [OK] API直连成功 — {len(data_text)} 字符")
        print(f"   [{market_data['fetched_at']}]")
    except Exception as e:
        print(f"   [!] API加载失败: {e}, 回退到文件...")
        jingjia = load_jingjia_file()
        if not jingjia:
            print("[FAIL] 竞价数据不存在:")
            print(f"   {os.path.join(DATA_DIR, 'jingjia_full.json')}")
            print("   请确认: 1) 网络连接正常 或 2) WorkBuddy 已抓取数据")
            sys.exit(1)
        data_text = format_data_table(jingjia)
        market_data = None
        print(f"   [OK] 文件加载 — {jingjia['total']} 只股票")

    # ---- Step 1.5: 复盘上下文 ----
    if args.review and not args.no_review:
        review_text = load_review_context()
        if review_text:
            data_text = review_text + "\n---\n\n" + data_text
            print(f"   [OK] 复盘上下文已注入 — 共 {len(data_text)} 字符")
        else:
            print(f"   [!] 复盘上下文不可用，继续纯竞价分析")

    # ---- Step 2: AI 分析 ----
    print(f"\n[2/4] AI 分析 ({args.ai})...")
    try:
        analysis = ai_analyze(data_text, engine=args.ai)
    except Exception as e:
        print(f"[FAIL] AI 分析失败: {e}")
        sys.exit(1)

    print("\n" + "─" * 55)
    print("  AI 分析结果")
    print("─" * 55)
    print(analysis)
    print("─" * 55)

    # ---- Step 3: 解析交易指令 ----
    print("\n[3/4] 解析交易指令...")
    buys, sells = parse_orders(analysis)

    if not buys and not sells:
        print("   [!] AI 未给出买卖指令（可能建议空仓/观望）")
        if not args.trade:
            sys.exit(0)

    buys_display = [f"{c} {v}股 @{pr or '市价'} — {r}" for c, v, pr, r in buys]
    sells_display = [f"{c} {v}股 @{pr or '市价'} — {r}" for c, v, pr, r in sells]

    print(f"   买入 {len(buys)} 笔: {buys_display if buys else '无'}")
    print(f"   卖出 {len(sells)} 笔: {sells_display if sells else '无'}")

    if not args.trade:
        print("\n   (分析模式，不执行下单。加 --trade 执行交易)")
        sys.exit(0)

    # ---- Step 4: 下单执行 ----
    print(f"\n[4/4] {'实盘' if args.live else '模拟'}下单...")

    qmt = QmtTrader(live=args.live)
    if args.live:
        if not qmt.connect():
            print("[FAIL] QMT 连接失败")
            sys.exit(1)

    # 先卖后买
    for code, vol, price, reason in sells:
        qmt.sell(code, vol, price)
        time.sleep(0.5)

    for code, vol, price, reason in buys:
        qmt.buy(code, vol, price)
        time.sleep(0.5)

    if args.live:
        qmt.close()

    print(f"\n** 全自动交易完成！")
    print(f"   买入 {len(buys)} 笔, 卖出 {len(sells)} 笔")


if __name__ == "__main__":
    main()
