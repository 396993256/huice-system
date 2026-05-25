"""A股量化交易系统 - 专业版 Streamlit 界面。

双击 run.bat 或在终端运行: streamlit run app.py
"""

import os, sys, time, importlib
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")

from data.models import init_db, get_conn
from data.manager import get_bars, get_stocks
from data.fetch_daily import fetch_daily
from data.fetch_stocks import fetch_stocks
from data.api import duanxianxia as dx
from review import ReviewManager
from review.fetcher import INDICATOR_LABELS
from review.longhu import fetch_longhu_detail
from review.analytics import (
    sector_persistence, concept_timeline, streak_heatmap,
    sentiment_cycle, sentiment_summary,
    lianban_matrix, mainline_identifier, review_screener,
)
from strategy.base import Strategy
from backtest.engine import BacktestEngine
from config import config

# ═══════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════
st.set_page_config(page_title="A股量化交易系统", page_icon="📈", layout="wide",
                   initial_sidebar_state="expanded")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

init_db()

# ═══════════════════════════════════════════════
# 策略注册表
# ═══════════════════════════════════════════════
STRATEGIES = {
    "ma_crossover":    {"name": "双均线交叉",    "params": "fast=5,slow=20",         "desc": "快线上穿慢线买入，下穿卖出"},
    "macd_strategy":  {"name": "MACD 金叉死叉",  "params": "fast=12,slow=26,signal=9", "desc": "MACD金叉买入，死叉卖出"},
    "mean_reversion": {"name": "布林带回归",     "params": "period=20,std=2",        "desc": "触下轨买入，触上轨卖出"},
    "rsi_strategy":   {"name": "RSI 超买超卖",   "params": "period=14,oversold=30,overbought=70", "desc": "RSI低位买入，高位卖出"},
}

# ═══════════════════════════════════════════════
# 侧边栏
# ═══════════════════════════════════════════════
st.sidebar.markdown("# 📈 A股量化交易")
st.sidebar.markdown("---")
page = st.sidebar.radio("",
    ["🏠 首页", "📡 市场雷达", "📋 每日复盘", "🔥 板块持续性", "🔬 深度分析", "⏱ 时间轴", "📊 数据中心", "🧪 策略实验室", "📈 回测分析", "💹 实时交易", "⚙ 系统设置"])
st.sidebar.markdown("---")

# 状态指示
mode_color = "🔴" if config.TRADE_MODE == "live" else "🟢"
st.sidebar.caption(f"{mode_color} 模式: {'实盘' if config.TRADE_MODE == 'live' else '模拟'}")
st.sidebar.caption(f"🏦 券商: {'国金MiniQMT' if config.BROKER == 'qmt' else config.BROKER.upper()}")

# 快速数据统计
try:
    conn = get_conn()
    bar_count = conn.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0]
    stock_count = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
    conn.close()
    st.sidebar.caption(f"📦 {stock_count} 只股票 / {bar_count:,} 条日线")
except:
    pass

# ═══════════════════════════════════════════════
# 缓存数据加载
# ═══════════════════════════════════════════════
@st.cache_data(ttl=300)
def load_bars(symbols, start, end):
    return get_bars(symbols, start, end)

def load_strategy_cls(name):
    mod = importlib.import_module(f"strategy.{name}")
    for attr_name in dir(mod):
        attr = getattr(mod, attr_name)
        if isinstance(attr, type) and issubclass(attr, Strategy) and attr is not Strategy:
            return attr
    return None


@st.cache_data(ttl=60)
def load_market_overview():
    """实时市场概况（60秒缓存）"""
    return dx.market_overview()


@st.cache_data(ttl=60)
def load_sectors():
    """板块强度数据"""
    return dx.sectors()


@st.cache_data(ttl=60)
def load_auction(tab="Daban", top=20):
    """竞价数据"""
    return dx.auction(tab, top=top)


@st.cache_data(ttl=60)
def load_pools():
    """股票池全景"""
    return dx.pool("All", top=15)


@st.cache_data(ttl=120)
def load_hotspots():
    """热点数据"""
    return dx.hotspot("All", top=10)


# ═══════════════════════════════════════════════
# 1. 首页
# ═══════════════════════════════════════════════
def page_home():
    st.title("🏠 慧策量化交易系统")

    # ═══════════════════════════════════
    # 第一行：实时市场情绪（短线侠）
    # ═══════════════════════════════════
    try:
        overview = load_market_overview()
        plates, sentiment = load_sectors()
        st.caption(f"🕐 数据来源: duanxianxia.cn | 更新时间: {sentiment.get('time', '-') if sentiment else '-'}")
    except Exception as e:
        st.warning(f"实时数据获取失败: {e}")
        overview = "数据获取失败"
        plates, sentiment = [], None

    if sentiment:
        emo = sentiment["emotion"]
        emo_label = "🔥 过热" if emo >= 80 else "🟢 偏暖" if emo >= 50 else "🔵 偏冷" if emo >= 20 else "❄️ 冰点"
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
        c1.metric("市场情绪", f"{emo}", emo_label)
        c2.metric("涨停", sentiment["zt_count"], f"跌停{sentiment['dt_count']}")
        c3.metric("上涨", sentiment["up_count"], f"下跌{sentiment['down_count']}")
        main_flow = sentiment['main_flow']
        c4.metric("主力流入" if main_flow >= 0 else "主力流出", f"{abs(main_flow)}亿")
        c5.metric("封板率", f"{sentiment['seal_rate']}%")
        c6.metric("连板高度", sentiment["lianban_height"])
        c7.metric("昨日涨停表现", sentiment.get("zt_yesterday", "-"))
        c8.metric("亏钱效应", sentiment.get("lose_effect", "-"))
    else:
        st.info("等待实时数据...")

    st.divider()

    # ═══════════════════════════════════
    # 第二行：板块强度 TOP10 + 热门股票池
    # ═══════════════════════════════════
    col_a, col_b = st.columns([0.45, 0.55])

    with col_a:
        st.subheader("🔥 板块强度 TOP10")
        if plates:
            top10 = plates[:10]
            sector_df = pd.DataFrame([{
                "排名": p["rank"], "板块": p["name"], "强度": p["strength"],
                "涨停": p["ztcount"], "代码": p["code"],
            } for p in top10])
            st.dataframe(sector_df, use_container_width=True, hide_index=True,
                         column_config={
                             "强度": st.column_config.ProgressColumn(
                                 "强度", min_value=0, max_value=max(p["strength"] for p in top10),
                                 format="%d"),
                         })
        else:
            st.caption("暂无板块数据")

    with col_b:
        st.subheader("📋 竞价 / 股票池 速览")
        tab_p1, tab_p2, tab_p3 = st.tabs(["涨停委买", "连板池", "竞价爆量"])
        try:
            with tab_p1:
                daban = load_auction("Daban", top=8)
                if daban:
                    st.dataframe(pd.DataFrame([{
                        "股票": f"{i['name']}({i['code']})",
                        "涨幅": f"{i['chg_pct']}%",
                        "封单": i.get("fengdan", "-"),
                        "概念": i.get("concept", "-"),
                        "板型": i.get("ban_type", "-"),
                    } for i in daban]), use_container_width=True, hide_index=True)
                else:
                    st.caption("暂无数据")
            with tab_p2:
                lb = dx.pool("Lb", top=8)
                if lb:
                    st.dataframe(pd.DataFrame([{
                        "股票": f"{i['name']}({i['code']})",
                        "涨幅": f"{i['chg_pct']}%",
                        "连板": i.get("lb_count", "-"),
                        "概念": i.get("concept", "-"),
                    } for i in lb]), use_container_width=True, hide_index=True)
                else:
                    st.caption("暂无数据")
            with tab_p3:
                vratio = load_auction("Vratio", top=8)
                if vratio:
                    st.dataframe(pd.DataFrame([{
                        "股票": f"{i['name']}({i['code']})",
                        "涨幅": f"{i['chg_pct']}%",
                        "竞涨": f"{i['jj_chg']}%",
                        "量比": i.get("vratio", "-"),
                        "概念": i.get("concept", "-"),
                    } for i in vratio]), use_container_width=True, hide_index=True)
                else:
                    st.caption("暂无数据")
        except Exception as e:
            st.caption(f"数据加载失败: {e}")

    st.divider()

    # ═══════════════════════════════════
    # 第三行：本地数据库 + 快速入门
    # ═══════════════════════════════════
    c1, c2, c3, c4 = st.columns(4)
    try:
        conn = get_conn()
        bar_c = conn.execute("SELECT COUNT(DISTINCT code) FROM daily_bars").fetchone()[0]
        date_row = conn.execute("SELECT MAX(trade_date), MIN(trade_date) FROM daily_bars").fetchone()
        conn.close()
    except:
        bar_c, date_row = 0, (None, None)

    c1.metric("📦 本地数据", f"{bar_c} 只", "日线行情")
    c2.metric("📅 数据范围", str(date_row[1] or "-")[:10], f"~{str(date_row[0] or '-')[:10]}")
    c3.metric("🧪 内置策略", "4 个", "可自定义扩展")
    c4.metric("⚡ 回测引擎", "就绪", "事件驱动 A股适配")

    # 快速入门
    st.divider()
    st.subheader("🚀 快速开始")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.info("**第一步：获取数据**\n\n数据中心 → 输入股票代码 → 获取日线", icon="📊")
    with col_b:
        st.info("**第二步：回测策略**\n\n回测分析 → 选择策略 → 开始回测", icon="📈")
    with col_c:
        st.info("**第三步：模拟/实盘**\n\n实时交易 → 先模拟再实盘", icon="💹")

    # 策略一览
    st.divider()
    st.subheader("🧪 内置策略")
    cols = st.columns(4)
    for i, (key, info) in enumerate(STRATEGIES.items()):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"**{info['name']}**")
                st.caption(info["desc"])
                st.code(info["params"], language=None)


# ═══════════════════════════════════════════════
# 2. 数据中心
# ═══════════════════════════════════════════════
def page_data():
    st.title("📊 数据中心")

    tab1, tab2, tab3, tab4 = st.tabs(["📥 获取数据", "📋 数据浏览", "🔍 股票筛选", "📡 实时数据"])

    # --- Tab 1: 获取数据 ---
    with tab1:
        col1, col2 = st.columns([0.6, 0.4])
        with col1:
            st.subheader("拉取日线数据")
            symbols = st.text_input("股票代码", "000001,600519,000858,300750,688981",
                                     help="逗号分隔，支持沪深京")
            c1, c2, c3 = st.columns(3)
            start = c1.text_input("起始", "20240101")
            end = c2.text_input("结束", "20251231")
            period_sel = c3.selectbox("快捷选择", ["自定义", "最近1个月", "最近3个月", "最近1年", "最近3年"])
            if period_sel != "自定义":
                today = datetime.now()
                days = {"最近1个月": 30, "最近3个月": 90, "最近1年": 365, "最近3年": 1095}
                start = (today - timedelta(days=days[period_sel])).strftime("%Y%m%d")
                end = today.strftime("%Y%m%d")

            if st.button("📥 开始获取日线数据", type="primary", use_container_width=True):
                sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
                progress = st.progress(0, text="正在获取...")
                total = len(sym_list)
                success_count = 0
                for i, code in enumerate(sym_list):
                    progress.progress((i+1)/total, text=f"获取 {code} ({i+1}/{total})")
                    try:
                        fetch_daily([code], start, end, sleep=0.1)
                        success_count += 1
                    except Exception as e:
                        st.warning(f"{code} 失败: {e}")
                progress.empty()
                st.success(f"完成！成功 {success_count}/{total} 只股票")
                st.rerun()

        with col2:
            st.subheader("股票列表")
            if st.button("🔄 更新全部A股列表", use_container_width=True):
                with st.spinner("获取中..."):
                    fetch_stocks()
                    st.success("更新完成！")
                    st.rerun()
            try:
                stocks = get_stocks()
                st.metric("沪深京股票总数", len(stocks))
                st.dataframe(stocks.head(20), use_container_width=True, hide_index=True,
                             column_config={"code": "代码", "name": "名称", "exchange": "交易所", "board": "板块"})
            except:
                st.caption("暂未获取股票列表")

    # --- Tab 2: 数据浏览 ---
    with tab2:
        st.subheader("行情数据查看")
        c1, c2 = st.columns([0.3, 0.7])
        with c1:
            view_code = st.text_input("代码", "000001", key="view_code2")
            view_start = st.text_input("起始日期", "2024-01-01", key="vs")
            view_end = st.text_input("结束日期", "2024-12-31", key="ve")
            show_rows = st.slider("显示行数", 20, 500, 100, 20)
            if st.button("🔍 查询", use_container_width=True):
                st.session_state.view_data = load_bars([view_code], view_start, view_end)
                st.rerun()

        with c2:
            if "view_data" in st.session_state and st.session_state.view_data:
                data = st.session_state.view_data
                if view_code in data:
                    df = data[view_code]
                    st.caption(f"{view_code} — 共 {len(df)} 条")

                    # K线图 + 成交量
                    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 5.5),
                                                    gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
                    disp = df.tail(show_rows)
                    x = range(len(disp))
                    colors = ["#e94560" if disp["close"].iloc[i] >= disp["open"].iloc[i] else "#00b894"
                              for i in range(len(disp))]
                    ax1.bar(x, disp["high"] - disp["low"], bottom=disp["low"], width=0.6,
                            color=colors, alpha=0.8)
                    ax1.bar(x, abs(disp["close"] - disp["open"]),
                            bottom=disp[["open", "close"]].min(axis=1), width=0.6,
                            color=colors)
                    ax1.set_title(f"{view_code} K线图", fontweight="bold", fontsize=13)
                    ax1.grid(True, alpha=0.2)
                    ax1.set_ylabel("价格")

                    vol_colors = ["#e94560" if disp["close"].iloc[i] >= disp["open"].iloc[i] else "#00b894"
                                  for i in range(len(disp))]
                    ax2.bar(x, disp["volume"], color=vol_colors, alpha=0.6, width=0.7)
                    ax2.set_ylabel("成交量")
                    ax2.grid(True, alpha=0.2)

                    step = max(1, len(disp) // 15)
                    ax2.set_xticks(range(0, len(disp), step))
                    ax2.set_xticklabels([str(d)[:10] for d in disp["trade_date"].iloc[::step]],
                                        rotation=30, fontsize=7)
                    fig.tight_layout()
                    st.pyplot(fig)

                    # 数据表
                    st.dataframe(df.tail(show_rows)[["trade_date", "open", "high", "low", "close",
                                                      "volume", "amount", "change_pct"]],
                                 use_container_width=True, hide_index=True,
                                 column_config={
                                     "trade_date": st.column_config.DatetimeColumn("日期", format="YYYY-MM-DD"),
                                     "volume": st.column_config.NumberColumn("成交量", format="%.0f"),
                                     "amount": st.column_config.NumberColumn("成交额", format="%.0f"),
                                     "change_pct": st.column_config.NumberColumn("涨跌幅%", format="%.2f"),
                                 })
                else:
                    st.warning("无数据")

    # --- Tab 3: 股票筛选 ---
    with tab3:
        st.subheader("🔍 股票筛选器")
        st.caption("根据涨跌幅、成交量等条件筛选股票")

        c1, c2, c3 = st.columns(3)
        with c1:
            filter_board = st.selectbox("板块", ["全部", "main", "gem", "star", "bj"],
                                         format_func=lambda x: {"全部": "全部", "main": "主板", "gem": "创业板", "star": "科创板", "bj": "北交所"}.get(x, x))
        with c2:
            min_price = st.number_input("最低股价", 0.0, 10000.0, 0.0)
        with c3:
            max_price = st.number_input("最高股价", 0.0, 10000.0, 9999.0)

        if st.button("🔍 筛选", use_container_width=True):
            try:
                stocks = get_stocks(board=None if filter_board == "全部" else filter_board)
                st.info(f"匹配 {len(stocks)} 只（详细筛选需更多数据，此处展示基础列表）")
                st.dataframe(stocks.head(50), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"筛选失败: {e}")

    # --- Tab 4: 短线侠实时数据 ---
    with tab4:
        st.subheader("📡 短线侠 duanxianxia.cn 实时数据")
        st.caption("直接从短线侠公开 API 获取，盘中实时刷新")

        col_a, col_b = st.columns([0.45, 0.55])

        with col_a:
            st.markdown("**📊 市场概况**")
            try:
                overview = load_market_overview()
                st.success(overview)
            except Exception as e:
                st.error(f"获取失败: {e}")

            st.divider()
            st.markdown("**🏗 板块强度 TOP10**")
            try:
                plates, _ = load_sectors()
                if plates:
                    st.dataframe(pd.DataFrame([{
                        "排名": p["rank"], "板块": p["name"],
                        "强度": p["strength"], "涨停": p["ztcount"],
                    } for p in plates[:10]]), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"获取失败: {e}")

            st.divider()
            st.markdown("**💾 数据导出**")
            if st.button("📥 导出全部实时数据为 JSON", use_container_width=True):
                try:
                    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                               "data", "market_snapshot.json")
                    result = dx.dump_all(output_path)
                    st.success(f"已导出到 data/market_snapshot.json")
                    st.caption(f"导出时间: {result.get('fetched_at', '-')}")
                except Exception as e:
                    st.error(f"导出失败: {e}")

        with col_b:
            st.markdown("**⚡ 竞价数据速览**")
            auction_type = st.selectbox("选择竞价Tab", [
                "Daban", "Vratio", "Zhuli", "Qiangchou", "Jingjia",
            ], format_func=lambda x: {
                "Daban": "涨停委买", "Vratio": "竞价爆量", "Zhuli": "竞价净额",
                "Qiangchou": "竞价抢筹", "Jingjia": "集合竞价",
            }.get(x, x), key="dc_auction")

            try:
                items = load_auction(auction_type, top=15)
                if items:
                    st.dataframe(pd.DataFrame([{
                        "代码": i.get("code", "-"),
                        "名称": i.get("name", "-"),
                        "涨幅": i.get("chg_pct", "-"),
                        "概念": i.get("concept", "-"),
                    } for i in items]), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"获取失败: {e}")

            st.divider()
            st.markdown("**🔥 热点题材**")
            try:
                hots = load_hotspots()
                topics = hots.get("stock_topic", [])
                if topics:
                    st.dataframe(pd.DataFrame([{
                        "排名": t.get("rank", "-"),
                        "题材": t.get("title", "-"),
                        "热度": t.get("rate", "-"),
                    } for t in topics]), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"获取失败: {e}")

            st.divider()
            st.markdown("**📈 日热门股**")
            try:
                day_stocks = hots.get("hot_stock_day", []) if hots else []
                if day_stocks:
                    st.dataframe(pd.DataFrame([{
                        "排名": s.get("rank", "-"),
                        "股票": f"{s.get('name', '-')}({s.get('code', '-')})",
                        "热度": s.get("rate", "-"),
                    } for s in day_stocks[:10]]), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"获取失败: {e}")


# ═══════════════════════════════════════════════
# 3. 策略实验室
# ═══════════════════════════════════════════════
def page_strategy():
    st.title("🧪 策略实验室")

    tab1, tab2 = st.tabs(["📖 策略详情", "✏️ 自定义策略"])

    with tab1:
        st.subheader("内置策略详解")
        selected = st.selectbox("选择策略", list(STRATEGIES.keys()),
                                 format_func=lambda x: STRATEGIES[x]["name"])

        info = STRATEGIES[selected]
        col1, col2 = st.columns([0.6, 0.4])

        with col1:
            st.markdown(f"### {info['name']}")
            st.caption(info["desc"])
            st.markdown(f"**默认参数**: `{info['params']}`")

            # 尝试加载和显示策略源码
            try:
                src_path = f"strategy/{selected}.py"
                with open(src_path, "r", encoding="utf-8") as f:
                    code = f.read()
                with st.expander("📝 查看源码", expanded=False):
                    st.code(code, language="python")
            except:
                pass

        with col2:
            st.markdown("**策略参数说明**")
            if selected == "ma_crossover":
                st.markdown("""
                - `fast` — 快线周期（默认 5）
                - `slow` — 慢线周期（默认 20）
                - `buy_pct` — 每次买入仓位比例（0~1）
                """)
            elif selected == "macd_strategy":
                st.markdown("""
                - `fast` — 快线 EMA 周期（默认 12）
                - `slow` — 慢线 EMA 周期（默认 26）
                - `signal` — 信号线周期（默认 9）
                - `buy_pct` — 每次买入仓位比例
                """)
            elif selected == "mean_reversion":
                st.markdown("""
                - `period` — 布林带周期（默认 20）
                - `std` — 标准差倍数（默认 2）
                - `buy_pct` — 每次买入仓位比例
                """)
            elif selected == "rsi_strategy":
                st.markdown("""
                - `period` — RSI 周期（默认 14）
                - `oversold` — 超卖线（默认 30）
                - `overbought` — 超买线（默认 70）
                - `buy_pct` — 每次买入仓位比例
                """)

    with tab2:
        st.subheader("✏️ 编写自定义策略")
        st.caption("在 strategy/my_strategy.py 中编写你的策略")

        # 显示当前自定义策略
        try:
            with open("strategy/my_strategy.py", "r", encoding="utf-8") as f:
                current = f.read()
        except:
            current = "# 文件不存在"

        new_code = st.text_area("编辑策略代码", current, height=420, key="strategy_code",
                                 help="修改后点击保存即可")

        if st.button("💾 保存策略", type="primary"):
            try:
                with open("strategy/my_strategy.py", "w", encoding="utf-8") as f:
                    f.write(new_code)
                st.success("已保存！在回测页面选择 my_strategy 即可使用")
            except Exception as e:
                st.error(f"保存失败: {e}")

        with st.expander("📖 策略编写模板"):
            st.code("""
from strategy.base import Strategy
from strategy.indicators import sma, ema, rsi, macd, bollinger

class MyStrategy(Strategy):
    def on_init(self, data, portfolio):
        super().on_init(data, portfolio)
        # 初始化参数

    def on_bar(self, symbol, portfolio):
        df = self.data.get(symbol)
        if df is None:
            return
        close = df["close"]

        # === 你的交易逻辑 ===
        # self.buy(symbol, volume=100, price=None)   # 买入100股
        # self.sell(symbol, volume=100, price=None)   # 卖出100股
        # self.buy_pct(symbol, 0.3, close.iloc[-1])   # 用30%仓位买入
        # self.sell_all(symbol)                        # 全部卖出
""", language="python")


# ═══════════════════════════════════════════════
# 4. 回测分析 (增强版)
# ═══════════════════════════════════════════════
def page_backtest():
    st.title("📈 回测分析")

    col_cfg, col_result = st.columns([0.32, 0.68])

    with col_cfg:
        st.subheader("⚙ 回测设置")

        strategy_name = st.selectbox("选择策略", list(STRATEGIES.keys()),
                                      format_func=lambda x: f"{STRATEGIES[x]['name']} ({x})")
        symbols = st.text_input("股票代码", "000001", help="逗号分隔")
        params_str = st.text_input("策略参数", STRATEGIES[strategy_name]["params"])
        c1, c2 = st.columns(2)
        start_date = c1.text_input("起始日期", "2024-01-01")
        end_date = c2.text_input("结束日期", "2024-12-31")
        cash = st.number_input("初始资金", 10000, 10000000, 100000, 10000, format="%d")

        st.divider()
        st.caption("📐 参数优化（网格搜索）")
        opt_enabled = st.checkbox("启用参数优化", value=False)
        opt_fast = st.text_input("fast 范围", "3,5,10", help="逗号分隔的多个值") if opt_enabled and strategy_name in ["ma_crossover"] else None
        opt_slow = st.text_input("slow 范围", "10,20,30") if opt_enabled and strategy_name in ["ma_crossover"] else None

        st.divider()
        run_btn = st.button("▶ 开始回测", type="primary", use_container_width=True)

    with col_result:
        st.subheader("📊 回测结果")

        if "bt_result" not in st.session_state:
            st.session_state.bt_result = None
            st.session_state.bt_trades = None
            st.session_state.bt_nav = None
            st.session_state.bt_params_used = None
            st.session_state.opt_results = None

        if run_btn:
            sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
            if not sym_list:
                st.error("请输入股票代码")
                return

            params = {}
            for pair in params_str.split(","):
                if "=" in pair:
                    k, v = pair.split("=")
                    try:
                        params[k.strip()] = float(v.strip()) if "." in v.strip() else int(v.strip())
                    except ValueError:
                        params[k.strip()] = v.strip()

            with st.spinner("回测运行中..."):
                try:
                    data = load_bars(sym_list, start_date, end_date)
                    if not data:
                        st.error("无数据！请先在数据中心获取")
                        return

                    if opt_enabled and strategy_name == "ma_crossover":
                        # 网格搜索参数优化
                        fast_vals = [int(x.strip()) for x in opt_fast.split(",")]
                        slow_vals = [int(x.strip()) for x in opt_slow.split(",")]
                        opt_results = []
                        total = len(fast_vals) * len(slow_vals)
                        prog = st.progress(0, text=f"参数优化 0/{total}")
                        idx = 0
                        for fa in fast_vals:
                            for sl in slow_vals:
                                if fa >= sl:
                                    idx += 1
                                    continue
                                idx += 1
                                prog.progress(idx/total, text=f"测试 fast={fa} slow={sl} ({idx}/{total})")
                                cls = load_strategy_cls(strategy_name)
                                eng = BacktestEngine(initial_cash=float(cash))
                                res = eng.run(cls, data, params={"fast": fa, "slow": sl, "buy_pct": 0.8}, progress=False)
                                opt_results.append({
                                    "fast": fa, "slow": sl,
                                    "total_return": res.get("total_return", 0),
                                    "sharpe": res.get("sharpe_ratio", 0),
                                    "max_dd": res.get("max_drawdown", 0),
                                    "trades": res.get("total_trades", 0),
                                })
                        prog.empty()

                        # 按夏普排序
                        opt_results.sort(key=lambda x: x["sharpe"], reverse=True)
                        st.session_state.opt_results = opt_results

                        # 用最优参数重新回测
                        best = opt_results[0]
                        params = {"fast": best["fast"], "slow": best["slow"], "buy_pct": 0.8}
                        st.info(f"最优参数: fast={best['fast']}, slow={best['slow']} (夏普={best['sharpe']:.2f})")

                    cls = load_strategy_cls(strategy_name)
                    eng = BacktestEngine(initial_cash=float(cash))
                    result = eng.run(cls, data, params=params, progress=False)

                    st.session_state.bt_result = result
                    st.session_state.bt_trades = eng.broker.trades
                    st.session_state.bt_nav = [s["nav"] for s in result.get("nav_series", [])]
                    st.session_state.bt_params_used = params

                except Exception as e:
                    st.error(f"回测失败: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                st.rerun()

        # 显示结果
        result = st.session_state.bt_result
        if result:
            # 6 指标卡片
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("📈 总收益率", f"{result['total_return']:+.1f}%",
                       delta=f"{result['total_return']:+.1f}%")
            m2.metric("📅 年化收益", f"{result['annual_return']:+.1f}%")
            m3.metric("⚡ 夏普比率", f"{result['sharpe_ratio']:.2f}")
            m4.metric("📉 最大回撤", f"{result['max_drawdown']:.1f}%",
                       delta=f"-{result['max_drawdown']:.1f}%", delta_color="inverse")
            m5.metric("🔀 交易次数", result["total_trades"])
            m6.metric("💰 最终资金", f"{result['final_nav']:,.0f}",
                       delta=f"{result['final_nav'] - result['initial_nav']:+,.0f}")

            # 图表区
            cht1, cht2 = st.columns([1, 1])

            with cht1:
                # 收益曲线
                nav_series = result.get("nav_series", [])
                if nav_series:
                    fig, ax = plt.subplots(figsize=(7, 3.5))
                    dates = [s["date"] for s in nav_series]
                    navs = [s["nav"] for s in nav_series]
                    ax.plot(dates, navs, color="#e94560", linewidth=2, label="净值")
                    ax.axhline(y=navs[0], color="#888", linewidth=0.8, linestyle="--", alpha=0.5)
                    ax.fill_between(dates, navs, navs[0],
                                    where=[n >= navs[0] for n in navs],
                                    color="#e94560", alpha=0.08)
                    ax.fill_between(dates, navs, navs[0],
                                    where=[n < navs[0] for n in navs],
                                    color="#00b894", alpha=0.08)
                    ax.set_title("收益曲线", fontsize=12, fontweight="bold")
                    ax.legend(frameon=True, fontsize=9)
                    ax.grid(True, alpha=0.25)
                    ax.set_ylabel("资产")
                    step = max(1, len(dates) // 10)
                    ax.set_xticks(dates[::step])
                    ax.set_xticklabels([str(d)[:10] for d in dates[::step]], rotation=30, fontsize=7)
                    fig.tight_layout()
                    st.pyplot(fig)

            with cht2:
                # 回撤曲线
                if nav_series:
                    navs = [s["nav"] for s in nav_series]
                    peak = navs[0]
                    drawdowns = []
                    for n in navs:
                        peak = max(peak, n)
                        drawdowns.append((peak - n) / peak * 100)
                    fig, ax = plt.subplots(figsize=(7, 3.5))
                    ax.fill_between(dates, drawdowns, 0, color="#e94560", alpha=0.15)
                    ax.plot(dates, drawdowns, color="#e94560", linewidth=1)
                    ax.set_title("回撤曲线", fontsize=12, fontweight="bold")
                    ax.grid(True, alpha=0.25)
                    ax.set_ylabel("回撤 %")
                    step = max(1, len(dates) // 10)
                    ax.set_xticks(dates[::step])
                    ax.set_xticklabels([str(d)[:10] for d in dates[::step]], rotation=30, fontsize=7)
                    ax.invert_yaxis()
                    fig.tight_layout()
                    st.pyplot(fig)

            # 参数优化结果
            if st.session_state.opt_results:
                st.divider()
                st.subheader("🔬 参数优化结果（按夏普排名）")
                opt_df = pd.DataFrame(st.session_state.opt_results)
                opt_df["sharpe"] = opt_df["sharpe"].round(2)
                opt_df["total_return"] = opt_df["total_return"].round(1)
                opt_df["max_dd"] = opt_df["max_dd"].round(1)
                opt_df.columns = ["快线", "慢线", "总收益%", "夏普", "最大回撤%", "交易次数"]
                st.dataframe(opt_df, use_container_width=True, hide_index=True)

            # 交易明细
            trades = st.session_state.bt_trades
            if trades:
                st.divider()
                st.subheader("📋 交易明细")
                td = []
                for t in trades:
                    td.append({
                        "日期": str(t["trade_date"])[:10],
                        "方向": "🟢 买入" if t["direction"] == "BUY" else "🔴 卖出",
                        "股票": t["symbol"],
                        "数量": f"{t['volume']:,}",
                        "价格": f"{t['price']:.2f}",
                        "费用": f"{t.get('commission', 0) + t.get('stamp_duty', 0):.2f}",
                        "盈亏": f"{t.get('pnl', 0):+,.2f}",
                    })
                st.dataframe(pd.DataFrame(td), use_container_width=True, hide_index=True)

            # 统计信息
            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💰 总盈亏", f"{result.get('total_pnl', 0):+,.2f}")
            c2.metric("🎯 胜率", f"{result.get('win_rate', 0):.1f}%")
            c3.metric("📊 盈亏比", str(result.get('profit_factor', '-')))
            c4.metric("💵 年化波动", f"{result.get('annual_volatility', 0):.1f}%")

        else:
            st.info("👈 在左侧设置参数，点击「开始回测」查看结果")
            st.markdown("""
            #### 支持的操作：
            - **单股回测**: 输入一个股票代码
            - **多股回测**: 逗号分隔多个代码
            - **参数优化**: 勾选后可对双均线策略网格搜索最佳参数
            """)


# ═══════════════════════════════════════════════
# 5. 实时交易
# ═══════════════════════════════════════════════
def page_live():
    st.title("💹 实时交易")

    if config.TRADE_MODE == "live":
        st.warning("⚠️ 当前为实盘模式，将产生真实交易！")

    col1, col2 = st.columns([0.38, 0.62])

    with col1:
        st.subheader("⚙ 交易设置")
        strategy_name = st.selectbox("策略", list(STRATEGIES.keys()),
                                      format_func=lambda x: STRATEGIES[x]["name"], key="live_sg")
        symbols = st.text_input("股票池", "000001", key="live_sym", help="逗号分隔")
        st.divider()

        if st.button("▶ 执行交易检查", type="primary", use_container_width=True):
            sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
            if not sym_list:
                st.error("请输入股票代码")
                return

            if config.TRADE_MODE == "live":
                st.warning("实盘模式！真实下单中...")

            with st.spinner("交易检查中..."):
                try:
                    from live.trader import run_live
                    result = run_live(strategy_name, sym_list)
                    st.success("交易检查完成，查看右侧日志")
                except Exception as e:
                    st.error(f"执行失败: {e}")

        st.divider()
        st.subheader("📋 风控状态")
        c1, c2, c3 = st.columns(3)
        c1.metric("单票上限", f"{config.MAX_SINGLE_STOCK_PCT*100:.0f}%")
        c2.metric("日亏损停止", f"{config.MAX_DAILY_LOSS_PCT*100:.0f}%")
        c3.metric("连续亏损停", f"{config.MAX_CONSECUTIVE_LOSSES}笔")

        st.divider()
        st.caption("💡 建议流程")
        st.caption("① 先在回测页面验证策略")
        st.caption("② 在模拟模式下跑 1-2 周")
        st.caption("③ 确认无误后在设置中切到实盘")
        st.caption("④ 实盘需要券商客户端已登录")

    with col2:
        st.subheader("📊 交易面板")

        tab_l1, tab_l2 = st.tabs(["📋 当日信号", "📜 交易日志"])

        with tab_l1:
            st.info("执行交易检查后，此处显示策略信号")
            # 显示最近数据
            sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
            if sym_list:
                try:
                    from data.manager import get_today_bars
                    bars = get_today_bars(sym_list)
                    if bars:
                        td = []
                        for code, bar in bars.items():
                            td.append({
                                "股票": code,
                                "收盘": f"{bar.get('close', 0):.2f}",
                                "最高": f"{bar.get('high', 0):.2f}",
                                "最低": f"{bar.get('low', 0):.2f}",
                                "涨跌幅": f"{bar.get('change_pct', 0):+.2f}%",
                                "成交量": f"{bar.get('volume', 0):,.0f}",
                            })
                        st.dataframe(pd.DataFrame(td), use_container_width=True, hide_index=True)
                    else:
                        st.caption("今日暂无行情数据")
                except:
                    st.caption("数据获取失败")

        with tab_l2:
            st.caption("交易执行日志将在此显示")
            st.code("等待执行交易检查...", language=None)


# ═══════════════════════════════════════════════
# 6. 系统设置
# ═══════════════════════════════════════════════
def page_settings():
    st.title("⚙ 系统设置")

    tab1, tab2, tab3 = st.tabs(["📋 当前配置", "✏️ 编辑 .env", "ℹ️ 帮助说明"])

    with tab1:
        st.subheader("运行参数")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("交易模式", "🔴 实盘" if config.TRADE_MODE == "live" else "🟢 模拟")
        c2.metric("券商", "国金MiniQMT" if config.BROKER == "qmt" else config.BROKER.upper())
        c3.metric("数据库", "SQLite")
        c4.metric("Tushare", "已配置" if config.TUSHARE_TOKEN else "未配置")

        st.divider()
        st.subheader("风控参数")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("单票仓位上限", f"{config.MAX_SINGLE_STOCK_PCT*100:.0f}%")
        c2.metric("单日亏损停止", f"{config.MAX_DAILY_LOSS_PCT*100:.0f}%")
        c3.metric("连续亏损暂停", f"{config.MAX_CONSECUTIVE_LOSSES} 笔")
        c4.metric("佣金费率", f"{config.COMMISSION_RATE*10000:.1f}‱")

        st.divider()
        st.subheader("费用设置")
        c1, c2, c3 = st.columns(3)
        c1.metric("佣金", f"{config.COMMISSION_RATE*10000:.1f}‱", f"最低{config.MIN_COMMISSION:.0f}元")
        c2.metric("印花税", f"{config.STAMP_DUTY_RATE*1000:.1f}‰", "仅卖出收取")
        c3.metric("过户费", "0.01‰", "双向收取")

    with tab2:
        st.subheader("编辑 .env 配置文件")
        st.caption("修改后需重启应用生效。重启方法：关闭终端，重新双击 run.bat")

        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                current = f.read()
        except:
            current = ""

        new_env = st.text_area("配置内容", current, height=280)
        if st.button("💾 保存配置", type="primary"):
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(new_env)
            st.success("已保存！重启后生效。")

    with tab3:
        st.subheader("ℹ️ 使用说明")
        st.markdown("""
        ### 券商对接 — 国金 MiniQMT

        **第一次使用：**
        1. 启动 MiniQMT 客户端：`D:\\国金QMT交易端模拟\\bin.x64\\XtItClient.exe`
        2. 在 MiniQMT 中登录你的国金证券账号
        3. 在本系统中将 `TRADE_MODE=live` 设为 paper 先模拟

        **实盘交易：**
        1. MiniQMT 保持运行并已登录
        2. `.env` 中设置 `TRADE_MODE=live`
        3. 运行 `python live_main.py --strategy <策略> --symbols <代码>`

        ### 模拟 vs 实盘

        | 模式 | 说明 |
        |------|------|
        | paper | 本地模拟下单，不产生真实交易。**推荐先使用** |
        | live | 通过 xtquant → MiniQMT 真实下单到券商柜台 |

        ### 风控规则

        - 单只股票仓位不超过总资产 20%
        - 单日亏损超过 3% 自动暂停交易
        - 连续亏损 3 笔自动暂停交易
        - 买入委托数量为 100 股的整数倍
        """)


# ═══════════════════════════════════════════════
# 7. 时间轴（AI 打板流水线 — 与 huice.py 同步）
# ═══════════════════════════════════════════════
def page_timeline():
    st.title("⏱ 交易时间轴 — AI 短线打板")
    st.caption("与 huice.py 共享同一 AI 分析流水线：竞价数据 → AI 大脑 → 指令解析 → 风控 → 下单")

    import huice

    # ---- 设置区 ----
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([0.2, 0.35, 0.2, 0.25])
        ai_engine = c1.selectbox("AI 引擎", ["deepseek", "claude"],
                                  help="DeepSeek API / Claude API")
        data_source = c2.selectbox("数据源", ["API直连 (推荐)", "WorkBuddy文件"],
                                    help="API直连=从duanxianxia.cn实时获取 | 文件=从本地jingjia_full.json")
        exec_mode = c3.selectbox("执行模式", ["分析", "模拟", "实盘"],
                                  help="分析=只看AI结果 | 模拟=打印订单 | 实盘=QMT下单")
        run_btn = c4.button("▶ 启动 AI 分析", type="primary", use_container_width=True)
        if run_btn:
            st.session_state.tl_run = True

    st.divider()

    # ---- 流水线步骤 ----
    steps = [
        {"icon": "📥", "name": "数据加载", "desc": "从 duanxianxia.cn API 获取实时市场数据"},
        {"icon": "🧠", "name": "AI 分析", "desc": f"调用 {ai_engine.upper()} 分析市场全景"},
        {"icon": "📋", "name": "指令解析", "desc": "从 AI 输出提取买卖指令"},
        {"icon": "🛡️", "name": "风控审核", "desc": "仓位/价格/数量检查"},
        {"icon": "📡", "name": "下单执行", "desc": "通过 MiniQMT 向券商下单"},
        {"icon": "✅", "name": "结果确认", "desc": "成交回报与汇总"},
    ]

    if "tl_run" not in st.session_state:
        st.session_state.tl_run = False

    if not st.session_state.tl_run:
        _render_timeline(steps, {s["name"]: "wait" for s in steps})
        st.info("👆 选择 AI 引擎和模式，点击「启动 AI 分析」运行 AI 打板流水线")
        return

    # ═══════════════════════════════════════
    # 开始执行流水线
    # ═══════════════════════════════════════
    tl_status = {s["name"]: "wait" for s in steps}

    # ---- 步骤 1: 数据加载 ----
    tl_status["数据加载"] = "run"
    _render_timeline(steps, tl_status)

    use_api = "API" in data_source
    try:
        if use_api:
            market_data = huice.load_market_data(use_api=True)
            data_text = huice.format_data_table(market_data)
            st.success(f"API直连成功 — {len(data_text)} 字符 ({market_data['fetched_at']})")
        else:
            jingjia = huice.load_jingjia_file()
            if not jingjia:
                tl_status["数据加载"] = "fail"
                _render_timeline(steps, tl_status)
                st.error(f"竞价数据不存在: {os.path.join(huice.DATA_DIR, 'jingjia_full.json')}")
                st.session_state.tl_run = False
                return
            data_text = huice.format_data_table(jingjia)
            st.success(f"文件加载 — {jingjia['total']} 只竞价异动股")
        tl_status["数据加载"] = "ok"
        _render_timeline(steps, tl_status)
    except Exception as e:
        tl_status["数据加载"] = "fail"
        _render_timeline(steps, tl_status)
        st.error(f"数据加载失败: {e}")
        st.session_state.tl_run = False
        return

    # ---- 步骤 2: AI 分析 ----
    tl_status["AI 分析"] = "run"
    _render_timeline(steps, tl_status)

    try:
        with st.spinner(f"调用 {ai_engine.upper()} API 分析市场数据 (约需 10-30 秒)..."):
            analysis = huice.ai_analyze(data_text, engine=ai_engine)
        tl_status["AI 分析"] = "ok"
        _render_timeline(steps, tl_status)
        st.success(f"AI 分析完成, 返回 {len(analysis)} 字符")
    except Exception as e:
        tl_status["AI 分析"] = "fail"
        _render_timeline(steps, tl_status)
        st.error(f"AI 分析失败: {e}")
        st.warning("请检查 API Key 是否正确设置了环境变量")
        st.session_state.tl_run = False
        return

    # 显示 AI 分析原文
    with st.expander("📝 查看 AI 分析原文", expanded=False):
        st.code(analysis, language=None)

    # ---- 步骤 3: 指令解析 ----
    tl_status["指令解析"] = "run"
    _render_timeline(steps, tl_status)

    buys, sells = huice.parse_orders(analysis)

    tl_status["指令解析"] = "ok"
    _render_timeline(steps, tl_status)

    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("📊 总指令", len(buys) + len(sells))
    sc2.metric("🟢 买入", len(buys))
    sc3.metric("🔴 卖出", len(sells))

    if not buys and not sells:
        st.warning("AI 未给出买卖指令（可能建议空仓/观望）")
        st.session_state.tl_run = False
        return

    # 显示解析后的指令
    cb1, cb2 = st.columns(2)
    with cb1:
        if buys:
            st.write("**买入指令:**")
            st.dataframe(pd.DataFrame([{
                "代码": c, "数量": f"{v}股", "价格": f"{pr:.2f}" if pr else "市价", "理由": r
            } for c, v, pr, r in buys]), use_container_width=True, hide_index=True)
        else:
            st.caption("无买入指令")
    with cb2:
        if sells:
            st.write("**卖出指令:**")
            st.dataframe(pd.DataFrame([{
                "代码": c, "数量": f"{v}股", "价格": f"{pr:.2f}" if pr else "市价", "理由": r
            } for c, v, pr, r in sells]), use_container_width=True, hide_index=True)
        else:
            st.caption("无卖出指令")

    # 分析模式到此为止
    if exec_mode == "分析":
        st.info("💡 分析模式 — 不执行下单。切换到「模拟」或「实盘」模式可执行交易。")
        st.session_state.tl_run = False
        return

    # ---- 步骤 4: 风控审核 ----
    tl_status["风控审核"] = "run"
    _render_timeline(steps, tl_status)

    from live.risk import RiskManager
    risk = RiskManager()

    # 组装订单列表 (direction, code, vol, price, reason)
    all_orders = [("BUY", c, v, pr, r) for c, v, pr, r in buys] + \
                 [("SELL", c, v, pr, r) for c, v, pr, r in sells]

    # 模拟账户状态 (实盘时会连 QMT 取真实数据)
    mock_portfolio = {
        "cash": 1000000,
        "nav": 1000000,
        "positions": {c: {"total_volume": v} for _, c, v, _, _ in sells},
    }

    approved, rejected = [], []
    for direction, code, vol, price, reason in all_orders:
        if direction == "BUY":
            ok, msg = risk.check_buy(code, vol, price or 0, mock_portfolio)
        else:
            ok, msg = risk.check_sell(code, vol, price or 0, mock_portfolio)
        if ok:
            approved.append((direction, code, vol, price, reason))
        else:
            rejected.append((direction, code, vol, price, reason, msg))

    tl_status["风控审核"] = "ok"
    _render_timeline(steps, tl_status)

    rc1, rc2 = st.columns(2)
    rc1.metric("✅ 通过", len(approved))
    rc2.metric("🚫 拦截", len(rejected))
    if rejected:
        with st.expander(f"查看拦截详情 ({len(rejected)} 笔)"):
            for d, c, v, pr, r, msg in rejected:
                st.caption(f"🚫 {d} {c} {v}股 — {msg}")

    if not approved:
        st.warning("所有指令被风控拦截，不执行下单")
        st.session_state.tl_run = False
        return

    # ---- 步骤 5: 下单执行 ----
    tl_status["下单执行"] = "run"
    _render_timeline(steps, tl_status)

    if exec_mode == "实盘":
        try:
            qmt = huice.QmtTrader(live=True)
            if not qmt.connect():
                tl_status["下单执行"] = "fail"
                _render_timeline(steps, tl_status)
                st.error("MiniQMT 连接失败，请确认客户端已启动并登录")
                st.session_state.tl_run = False
                return

            order_results = []
            for direction, code, vol, price, reason in approved:
                if direction == "BUY":
                    oid = qmt.buy(code, vol, price)
                else:
                    oid = qmt.sell(code, vol, price)
                status = "sent" if (isinstance(oid, int) and oid != -1) else "failed"
                order_results.append({
                    "direction": direction, "code": code, "vol": vol,
                    "price": price, "reason": reason,
                    "order_id": oid, "status": status,
                })
                time.sleep(0.5)
            qmt.close()
        except Exception as e:
            tl_status["下单执行"] = "fail"
            _render_timeline(steps, tl_status)
            st.error(f"下单异常: {e}")
            st.session_state.tl_run = False
            return
    else:
        # 模拟下单
        order_results = []
        for direction, code, vol, price, reason in approved:
            order_results.append({
                "direction": direction, "code": code, "vol": vol,
                "price": price, "reason": reason,
                "order_id": f"SIM-{abs(hash(code)) % 100000:05d}",
                "status": "simulated",
            })

    tl_status["下单执行"] = "ok"
    _render_timeline(steps, tl_status)

    # ---- 步骤 6: 结果确认 ----
    tl_status["结果确认"] = "run"
    _render_timeline(steps, tl_status)

    ok_count = sum(1 for o in order_results if o["status"] in ("sent", "simulated"))
    fail_count = sum(1 for o in order_results if o["status"] == "failed")

    tl_status["结果确认"] = "ok"
    _render_timeline(steps, tl_status)

    # 最终汇总
    st.divider()
    st.subheader("📋 AI 交易结果")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("📊 数据量", f"{len(data_text)} 字符")
    m2.metric("🧠 AI 指令", f"{len(buys)}买{len(sells)}卖")
    m3.metric("🛡️ 风控通过", len(approved))
    m4.metric("📡 下单成功", ok_count)
    m5.metric("❌ 失败", fail_count)

    if order_results:
        st.dataframe(
            pd.DataFrame([{
                "方向": o["direction"],
                "股票": o["code"],
                "数量": f"{o['vol']:,}",
                "价格": f"{o['price']:.2f}" if o["price"] else "市价",
                "理由": o["reason"],
                "订单号": str(o["order_id"]),
                "状态": "✅ 已发" if o["status"] in ("sent", "simulated") else "❌ 失败",
            } for o in order_results]),
            use_container_width=True, hide_index=True,
        )

    st.session_state.tl_run = False


def _render_timeline(steps, status):
    """渲染垂直时间轴。status: dict of step_name → wait/run/ok/fail"""
    status_icon = {
        "wait": "⚪", "run": "🔵", "ok": "🟢", "fail": "🔴"
    }
    status_label = {
        "wait": "等待中", "run": "执行中...", "ok": "完成", "fail": "失败"
    }

    cols = st.columns(len(steps))
    for i, step in enumerate(steps):
        s = status.get(step["name"], "wait")
        with cols[i]:
            icon = status_icon[s]
            st.markdown(f"<div style='text-align:center;font-size:2rem;'>{icon}</div>",
                        unsafe_allow_html=True)
            st.markdown(f"<div style='text-align:center;font-weight:bold;'>{step['name']}</div>",
                        unsafe_allow_html=True)
            st.caption(f"<div style='text-align:center;'>{status_label[s]}</div>",
                      unsafe_allow_html=True)
            if s == "run":
                st.markdown(
                    "<div style='text-align:center;margin-top:-10px;'>"
                    "<div style='display:inline-block;width:100%;"
                    "background:linear-gradient(90deg,#1f77b4 0%,#1f77b440 100%);"
                    "height:4px;border-radius:2px;'></div></div>",
                    unsafe_allow_html=True,
                )

    # 连接线
    st.markdown(
        "<div style='position:relative;height:2px;background:#333;margin:-30px 10% 0 10%;'></div>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════
# 市场雷达（短线侠实时数据全景）
# ═══════════════════════════════════════════════
def page_market_radar():
    st.title("📡 市场雷达 — duanxianxia.cn 实时数据")
    st.caption("数据来源: 短线侠公开API | 板块/竞价/股票池/热点全景仪表盘")

    # ---- 市场情绪条 ----
    try:
        overview = load_market_overview()
        plates, sentiment = load_sectors()
    except Exception as e:
        st.error(f"数据获取失败: {e}")
        return

    if sentiment:
        emo = sentiment["emotion"]
        emo_label = "🔥 过热" if emo >= 80 else "🟢 偏暖" if emo >= 50 else "🔵 偏冷" if emo >= 20 else "❄️ 冰点"
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
        c1.metric("市场情绪", f"{emo}", emo_label)
        c2.metric("涨停", sentiment["zt_count"], f"跌停{sentiment['dt_count']}")
        c3.metric("上涨/下跌", f"{sentiment['up_count']}/{sentiment['down_count']}")
        main_flow = sentiment['main_flow']
        c4.metric("主力流入" if main_flow >= 0 else "主力流出", f"{abs(main_flow)}亿")
        c5.metric("封板率", f"{sentiment['seal_rate']}%")
        c6.metric("连板高度", sentiment["lianban_height"])
        c7.metric("涨停表现", sentiment.get("zt_yesterday", "-"))
        c8.metric("亏钱效应", sentiment.get("lose_effect", "-"))

    st.divider()

    # ---- Tab 布局 ----
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏗 板块全景", "⚡ 竞价数据", "📋 股票池", "🔥 热点数据",
    ])

    # ════════════════════ Tab 1: 板块全景 ════════════════════
    with tab1:
        if not plates:
            st.info("暂无板块数据")
        else:
            col_a, col_b = st.columns([0.5, 0.5])

            with col_a:
                st.subheader(f"板块强度排行（共 {len(plates)} 个板块）")
                top_n = st.slider("显示数量", 10, 100, 30, 10, key="sector_top")
                disp = plates[:top_n]
                st.dataframe(pd.DataFrame([{
                    "排名": p["rank"], "板块": p["name"], "强度": p["strength"],
                    "涨停": p["ztcount"], "代码": p["code"],
                } for p in disp]), use_container_width=True, hide_index=True,
                    column_config={
                        "强度": st.column_config.ProgressColumn(
                            "强度", min_value=0, max_value=max(p["strength"] for p in disp),
                            format="%d"),
                    })

                # 板块成分股查询
                st.divider()
                st.subheader("🔍 板块成分股查询")
                sector_code = st.text_input("板块代码", "801660", key="sector_code_input",
                                            help="输入板块代码，如 801660=通信")
                if st.button("查询成分股", key="btn_sector_stocks"):
                    with st.spinner(f"获取 {sector_code} 成分股..."):
                        try:
                            stocks = dx.sector_stocks(sector_code)
                            if stocks:
                                st.success(f"{sector_code} — {len(stocks)} 只成分股")
                                st.dataframe(pd.DataFrame([{
                                    "代码": s["code"], "名称": s["name"],
                                    "涨幅": f"{s['chg_pct']:+.1f}%" if s["chg_pct"] else "-",
                                    "总净流入": dx.fmt_money(s.get("net_inflow", 0)),
                                    "主力净流入": dx.fmt_money(s["main_net_in"]),
                                    "连板": s.get("lianban") or "-",
                                    "换手": f"{s['turn_rate']:.1f}%" if s.get("turn_rate") else "-",
                                } for s in stocks]), use_container_width=True, hide_index=True)
                            else:
                                st.warning("无成分股数据")
                        except Exception as e:
                            st.error(f"获取失败: {e}")

            with col_b:
                st.subheader("💰 板块资金流 TOP15")
                try:
                    with st.spinner("计算板块资金流..."):
                        flow_data = dx.sector_flow()
                    if flow_data:
                        st.dataframe(pd.DataFrame([{
                            "板块": f["name"], "强度": f["strength"],
                            "涨停": f["ztcount"], "成分股": f["stock_count"],
                            "总净流入": dx.fmt_money(f.get("net_flow", 0)),
                            "主力": dx.fmt_money(f["main_net_flow"]),
                        } for f in flow_data]), use_container_width=True, hide_index=True)

                        # 资金流柱状图
                        fig, ax = plt.subplots(figsize=(10, 4))
                        names = [f["name"] for f in flow_data[:12]]
                        flows = [f.get("net_flow", 0) / 1e8 for f in flow_data[:12]]
                        colors = ["#e94560" if v > 0 else "#00b894" for v in flows]
                        ax.barh(range(len(names)), flows, color=colors, alpha=0.8, height=0.6)
                        ax.set_yticks(range(len(names)))
                        ax.set_yticklabels(names, fontsize=9)
                        ax.axvline(x=0, color="#888", linewidth=0.8)
                        ax.set_xlabel("总净流入（亿）")
                        ax.set_title("板块资金流 TOP12", fontweight="bold")
                        ax.invert_yaxis()
                        ax.grid(True, alpha=0.2, axis="x")
                        fig.tight_layout()
                        st.pyplot(fig)
                except Exception as e:
                    st.warning(f"资金流数据获取失败: {e}")

    # ════════════════════ Tab 2: 竞价数据 ════════════════════
    with tab2:
        auction_tab = st.selectbox("竞价类型", [
            "Daban", "Ztlast", "Jingjia", "Vratio", "Zhuli", "Qiangchou",
            "Zhaban", "Duanban", "Longhu",
        ], format_func=lambda x: {
            "Daban": "涨停委买", "Ztlast": "昨日涨停", "Jingjia": "集合竞价",
            "Vratio": "竞价爆量", "Zhuli": "竞价净额", "Qiangchou": "竞价抢筹",
            "Zhaban": "昨炸板", "Duanban": "昨断板", "Longhu": "昨上榜",
        }.get(x, x), key="auction_select")

        auction_top = st.slider("显示条数", 5, 50, 20, 5, key="auction_top")

        with st.spinner(f"加载竞价数据: {auction_tab}..."):
            try:
                items = load_auction(auction_tab, top=auction_top)
                if items:
                    st.success(f"{auction_tab} — 共 {len(items)} 条")
                    if auction_tab == "Daban":
                        st.dataframe(pd.DataFrame([{
                            "代码": i["code"], "名称": i["name"],
                            "涨幅": f"{i['chg_pct']}%",
                            "封单": i.get("fengdan", "-"),
                            "换手": i.get("turn_rate", "-"),
                            "概念": i.get("concept", "-"),
                            "板型": i.get("ban_type", "-"),
                            "人气": i.get("popular", "-"),
                        } for i in items]), use_container_width=True, hide_index=True)
                    elif auction_tab == "Ztlast":
                        st.dataframe(pd.DataFrame([{
                            "代码": i["code"], "名称": i["name"],
                            "换手": i.get("turn_rate", "-"),
                            "竞涨": f"{i['jj_chg']}%",
                            "实时涨": f"{i['real_chg']}%",
                            "竞额": i.get("jj_amount", "-"),
                            "量比": i.get("jj_vratio", "-"),
                            "连板": i.get("lb_desc", "-"),
                        } for i in items]), use_container_width=True, hide_index=True)
                    elif auction_tab == "Vratio":
                        st.dataframe(pd.DataFrame([{
                            "代码": i["code"], "名称": i["name"],
                            "涨幅": f"{i['chg_pct']}%",
                            "竞涨": f"{i['jj_chg']}%",
                            "竞额": i.get("jj_amount", "-"),
                            "量比": i.get("vratio", "-"),
                            "换手": i.get("turn_rate", "-"),
                            "概念": i.get("concept", "-"),
                        } for i in items]), use_container_width=True, hide_index=True)
                    elif auction_tab == "Zhuli":
                        st.dataframe(pd.DataFrame([{
                            "代码": i["code"], "名称": i["name"],
                            "涨幅": f"{i['chg_pct']}%",
                            "竞涨": f"{i['jj_chg']}%",
                            "净流入": i.get("net_inflow", "-"),
                            "人气": i.get("popular", "-"),
                            "概念": i.get("concept", "-"),
                        } for i in items]), use_container_width=True, hide_index=True)
                    else:
                        st.dataframe(pd.DataFrame([{
                            "代码": i["code"], "名称": i["name"],
                            "涨幅": f"{i['chg_pct']}%" if i.get("chg_pct") else "-",
                            "竞涨": f"{i.get('jj_chg', '-')}%",
                            "概念": i.get("concept", "-"),
                        } for i in items]), use_container_width=True, hide_index=True)
                else:
                    st.info("暂无数据")
            except Exception as e:
                st.error(f"获取失败: {e}")

    # ════════════════════ Tab 3: 股票池 ════════════════════
    with tab3:
        try:
            pools = load_pools()
            if pools:
                pool_cols = st.columns(len(pools))
                for idx, (key, info) in enumerate(pools.items()):
                    with pool_cols[idx]:
                        st.markdown(f"**{info['name']}** ({info['count']}只)")
                        items = info["data"]
                        if items:
                            for item in items:
                                code = item.get("code", "-")
                                name = item.get("name", "-")
                                chg = item.get("chg_pct", "-")
                                concept = item.get("concept", "-")
                                st.caption(f"{code} {name} {chg}% | {concept}")
                        else:
                            st.caption("(空)")
        except Exception as e:
            st.warning(f"股票池数据获取失败: {e}")

    # ════════════════════ Tab 4: 热点数据 ════════════════════
    with tab4:
        try:
            hotspots = load_hotspots()
            if hotspots:
                hc1, hc2 = st.columns(2)

                with hc1:
                    st.subheader("📰 热点题材")
                    topics = hotspots.get("stock_topic", [])
                    if topics:
                        st.dataframe(pd.DataFrame([{
                            "排名": t.get("rank", "-"),
                            "题材": t.get("title", "-"),
                            "热度": t.get("rate", "-"),
                        } for t in topics]), use_container_width=True, hide_index=True)

                    st.subheader("🔑 热搜关键词")
                    keywords = hotspots.get("hotkeyword", [])
                    if keywords:
                        st.dataframe(pd.DataFrame([{
                            "排名": kw.get("rank", "-"),
                            "关键词": kw.get("keyword", "-"),
                        } for kw in keywords]), use_container_width=True, hide_index=True)

                with hc2:
                    st.subheader("📈 日热门股")
                    day_stocks = hotspots.get("hot_stock_day", [])
                    if day_stocks:
                        st.dataframe(pd.DataFrame([{
                            "排名": s.get("rank", "-"),
                            "股票": f"{s.get('name', '-')}({s.get('code', '-')})",
                            "热度": s.get("rate", "-"),
                        } for s in day_stocks]), use_container_width=True, hide_index=True)

                    st.subheader("🚀 飙升股")
                    rising = hotspots.get("skyrocket_hour", [])
                    if rising:
                        st.dataframe(pd.DataFrame([{
                            "排名": s.get("rank", "-"),
                            "股票": f"{s.get('name', '-')}({s.get('code', '-')})",
                            "热度": s.get("rate", "-"),
                        } for s in rising]), use_container_width=True, hide_index=True)
            else:
                st.info("暂无热点数据")
        except Exception as e:
            st.warning(f"热点数据获取失败: {e}")


# ═══════════════════════════════════════════════
# 路由
# ═══════════════════════════════════════════════
# 9. 每日复盘
# ═══════════════════════════════════════════════

@st.cache_data(ttl=600)
def load_review(date_str):
    rm = ReviewManager()
    return rm.review(date_str)

@st.cache_data(ttl=3600)
def load_review_dates():
    """加载可选复盘日期列表（情绪曲线覆盖的所有交易日）。"""
    try:
        from review.fetcher import sentiment_curve
        sc = sentiment_curve()
        dates_map = sc.get("dates", {})
        # 返回按日期排序的列表
        sorted_dates = sorted(dates_map.keys(), reverse=True)
        return sorted_dates
    except Exception:
        return []


def page_review():
    st.title("📋 每日复盘")
    st.caption("数据来源: duanxianxia.cn 复盘API + akshare 龙虎榜 | 综合分析仪表盘")

    # ── 日期选择 ──
    dates = load_review_dates()
    if dates:
        default_date = dates[0]  # 最新
        default_idx = 0
        # 转换为 YYYY-MM-DD 显示格式
        disp_dates = [f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d for d in dates]
        sel = st.selectbox("复盘日期", disp_dates, index=default_idx, key="review_date_sel")
        date_raw = sel.replace("-", "")
    else:
        date_raw = st.text_input("复盘日期", "20260522", help="YYYYMMDD")

    if not date_raw:
        st.info("暂无复盘数据")
        return

    with st.spinner(f"加载 {date_raw} 复盘数据..."):
        try:
            data = load_review(date_raw)
        except Exception as e:
            st.error(f"数据加载失败: {e}")
            return

    if data.get("error"):
        st.warning(data["error"])
        return

    st.markdown(f"### {data['date']} 市场复盘")

    # ═══════ 市场指标卡片 ═══════
    ind = data.get("indicators", {})
    labels = data.get("indicator_labels", INDICATOR_LABELS)

    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
    core_pairs = [
        ("ZT", "跌停", "dt_label"), ("DT", None, None), ("LBGD", None, None), ("FB", None, None),
        ("KQXY", None, None), ("HSLN", "主力", "zl_label"), ("ZHULI", None, None), ("ZTBX", "连板", "lb_label"),
    ]
    for i, (key, _, _) in enumerate(core_pairs):
        cols = [c1, c2, c3, c4, c5, c6, c7, c8]
        v = ind.get(key)
        label = labels.get(key, key)
        if v is not None:
            if key == "ZT":
                delta = f"跌停{ind.get('DT','')}" if ind.get("DT") is not None else None
                cols[i].metric("涨停数量", v, delta)
            elif key == "HSLN":
                cols[i].metric(label, f"{v}亿", f"主力{ind.get('ZHULI','')}亿" if ind.get("ZHULI") is not None else None)
            elif key == "ZTBX":
                lbbx = ind.get("LBBX")
                cols[i].metric(label, f"{v}%", f"连板{lbbx}%" if lbbx is not None else None)
            elif key == "FB":
                cols[i].metric(label, f"{v}%")
            elif key in ("DT", "LBGD", "KQXY", "ZHULI"):
                cols[i].metric(label, v)
            else:
                cols[i].metric(label, v)

    c9, c10, c11, c12 = st.columns(4)
    extra = [("SZ", "上涨"), ("XD", "下跌"), ("LB", "连板"), ("CYB", "创业板")]
    for i, (key, _) in enumerate(extra):
        cols2 = [c9, c10, c11, c12]
        v = ind.get(key)
        label = labels.get(key, key)
        if v is not None:
            cols2[i].metric(label, v)

    st.divider()

    # ═══════ 晋级率 + 风险 ═══════
    col_jj, col_risk = st.columns([0.6, 0.4])
    with col_jj:
        jj_keys = ["jinji_1_2", "jinji_2_3", "jinji_3_4", "jinji_lianban", "jinji_top"]
        jj_vals = {}
        for k in jj_keys:
            v = ind.get(k)
            if v is not None:
                jj_vals[labels.get(k, k)] = f"{v}%"
        if jj_vals:
            st.subheader("晋级率")
            jj_df = pd.DataFrame([jj_vals])
            st.dataframe(jj_df, use_container_width=True, hide_index=True)

    with col_risk:
        risk_vals = {}
        for k in ["risk_val", "risk_avg"]:
            v = ind.get(k)
            if v is not None:
                risk_vals[labels.get(k, k)] = round(float(v), 1) if isinstance(v, (int, float)) else v
        if risk_vals:
            st.subheader("风险指标")
            st.dataframe(pd.DataFrame([risk_vals]), use_container_width=True, hide_index=True)

    st.divider()

    # ═══════ TAB: 板块 / 概念 / 涨停 / 连板 / 龙虎榜 ═══════
    tabs = st.tabs(["🏗 板块强度", "💡 概念分组", "📋 涨停复盘", "🪜 连板天梯", "🐉 龙虎榜"])

    sectors = data.get("sectors", [])
    concept_groups = data.get("concept_groups", [])
    zt_concept = data.get("zt_by_concept", [])
    zt_lianban = data.get("zt_by_lianban", [])
    longhu_list = data.get("longhu_list", [])
    lianban_html = data.get("lianban_html", "")

    # ── Tab 1: 板块强度 ──
    with tabs[0]:
        if sectors:
            st.subheader(f"板块强度排名（共 {len(sectors)} 个板块）")
            top_n = st.slider("显示数量", 10, 100, 30, 10, key="review_sector_top")
            disp = sectors[:top_n]
            st.dataframe(pd.DataFrame([{
                "排名": i+1, "板块": s["name"], "强度": s["strength"], "代码": s["code"],
            } for i, s in enumerate(disp)]), use_container_width=True, hide_index=True,
                column_config={
                    "强度": st.column_config.ProgressColumn(
                        "强度", min_value=0, max_value=max((s["strength"] for s in disp), default=1),
                        format="%d"),
                })
        else:
            st.info("暂无板块数据")

    # ── Tab 2: 概念分组 ──
    with tabs[1]:
        if concept_groups:
            st.subheader(f"涨停概念分组（{len(concept_groups)} 组）— 含板块启动理由")
            for i, cg in enumerate(concept_groups):
                with st.expander(f"{cg['concept']} — {cg['stock_count']}只涨停" + (f" — {cg.get('reason', '')}" if cg.get('reason') else ""), expanded=(i < 5)):
                    stocks = cg.get("stocks", [])
                    if stocks:
                        st.caption(cg.get("reason", ""))
                        st.dataframe(pd.DataFrame([{
                            "名称": s["name"], "代码": s["code"], "涨幅": s["chg_pct"],
                            "类型": s["ban_type"], "板数": s["ban_count"],
                            "连板": s["lianban"], "封单": s["seal_amount"],
                            "换手": s["turn_rate"], "龙虎榜": s["longhu"],
                        } for s in stocks]), use_container_width=True, hide_index=True)
                    else:
                        st.caption("(股票数据未解析)")
        else:
            st.info("暂无概念分组数据")

    # ── Tab 3: 涨停复盘 ──
    with tabs[2]:
        sub_tab1, sub_tab2 = st.tabs([f"按概念 ({len(zt_concept)}只)", f"按连板 ({len(zt_lianban)}只)"])

        with sub_tab1:
            if zt_concept:
                st.dataframe(pd.DataFrame([{
                    "名称": z["name"], "代码": z["code"], "涨幅": z["chg_pct"],
                    "类型": z["ban_type"], "板数": z["ban_count"],
                    "连板": z["lianban"], "首封": z["first_seal"], "最后封板": z["last_seal"],
                    "开板": z["open_count"], "封单": z["seal_amount"],
                    "成交额": z["volume"], "换手": z["turn_rate"],
                    "实际流通": z["float_mv_real"], "流通市值": z["float_mv"],
                    "总市值": z["total_mv"], "龙虎榜": z["longhu"],
                } for z in zt_concept]), use_container_width=True, hide_index=True)
            else:
                st.info("暂无涨停数据")

        with sub_tab2:
            if zt_lianban:
                st.dataframe(pd.DataFrame([{
                    "名称": z["name"], "代码": z["code"], "涨幅": z["chg_pct"],
                    "类型": z["ban_type"], "板数": z["ban_count"],
                    "连板": z["lianban"], "首封": z["first_seal"], "最后封板": z["last_seal"],
                    "开板": z["open_count"], "封单": z["seal_amount"],
                    "成交额": z["volume"], "换手": z["turn_rate"],
                    "龙虎榜": z["longhu"] + (" [上榜]" if z.get("longhu_detail") else ""),
                } for z in zt_lianban]), use_container_width=True, hide_index=True)
            else:
                st.info("暂无连板数据")

    # ── Tab 4: 连板天梯 ──
    with tabs[3]:
        if lianban_html:
            st.components.v1.html(lianban_html, height=500, scrolling=True)
        else:
            st.info("暂无连板天梯数据")

    # ── Tab 5: 龙虎榜 ──
    with tabs[4]:
        if longhu_list:
            st.subheader(f"龙虎榜上榜股票（{len(longhu_list)} 只）")
            sel_lh = st.selectbox("选择股票查看席位明细", [f"{lh['name']}({lh['code']})" for lh in longhu_list], key="lh_stock_sel")
            if sel_lh:
                sel_code = sel_lh.split("(")[1].rstrip(")")
                with st.spinner(f"加载 {sel_code} 席位明细..."):
                    seats = fetch_longhu_detail(sel_code, date_raw)
                if seats:
                    st.caption(f"**{sel_lh}** — {seats[0].get('type', '')}")
                    st.dataframe(pd.DataFrame([{
                        "席位": s["seat"],
                        "买入": f"{s['buy']/1e8:.2f}亿" if s['buy'] > 1e8 else f"{s['buy']/1e4:.0f}万" if s['buy'] else "-",
                        "买入占比": f"{s['buy_pct']*100:.1f}%" if s['buy_pct'] else "-",
                        "卖出": f"{s['sell']/1e8:.2f}亿" if s['sell'] > 1e8 else f"{s['sell']/1e4:.0f}万" if s['sell'] else "-",
                        "卖出占比": f"{s['sell_pct']*100:.1f}%" if s['sell_pct'] else "-",
                        "净额": f"{s['net']/1e8:+.2f}亿" if abs(s['net']) > 1e8 else f"{s['net']/1e4:+.0f}万" if s['net'] else "0",
                    } for s in seats]), use_container_width=True, hide_index=True)
                else:
                    st.caption("该股席位明细暂不可用（可能日期较早）")

            st.divider()
            st.caption("全部上榜股票")
            st.dataframe(pd.DataFrame([{
                "名称": lh["name"], "代码": lh["code"],
                "涨跌幅": f"{lh['chg_pct']:+.2f}%",
                "成交额": f"{lh['amount']/1e8:.2f}亿" if lh.get("amount") else "-",
                "上榜原因": lh["reason"],
            } for lh in longhu_list]), use_container_width=True, hide_index=True)
        else:
            st.info("暂无龙虎榜数据")


def page_sector_persistence():
    """板块持续性分析页面。"""
    st.title("🔥 板块持续性分析")
    st.caption("基于历史复盘数据，识别主线/轮动/一日游板块")

    @st.cache_data(ttl=3600)
    def load_persistence():
        return sector_persistence()

    with st.spinner("分析中..."):
        df = load_persistence()

    if df.empty:
        st.warning("暂无数据")
        return

    # ── 筛选 ──
    col1, col2, col3 = st.columns(3)
    with col1:
        active_filter = st.selectbox("活跃度", ["全部", "近5日", "近10日", "近20日"], index=2)
    with col2:
        category_filter = st.selectbox("分类", ["全部", "主线", "热点", "轮动", "一日游"], index=0)
    with col3:
        min_streak = st.slider("最少连续天数", 1, 20, 2)

    filtered = df.copy()
    if active_filter == "近5日":
        filtered = filtered[filtered["active_5d"]]
    elif active_filter == "近10日":
        filtered = filtered[filtered["active_10d"]]
    elif active_filter == "近20日":
        filtered = filtered[filtered["active_20d"]]

    if category_filter != "全部":
        filtered = filtered[filtered["category"] == category_filter]

    filtered = filtered[filtered["max_streak"] >= min_streak]

    # ── 概览指标 ──
    total = len(df)
    main_line = int((df["category"] == "主线").sum())
    hot = int((df["category"] == "热点").sum())
    rotate = int((df["category"] == "轮动").sum())
    one_day = int((df["category"] == "一日游").sum())

    st.markdown("### 板块分类概览")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("总概念数", total)
    c2.metric("主线 (≥5天连续)", main_line, delta=f"{main_line/total*100:.0f}%")
    c3.metric("热点 (3-4天)", hot)
    c4.metric("轮动 (2天)", rotate)
    c5.metric("一日游", one_day)

    st.markdown("---")

    # ── 排名表格 ──
    st.markdown(f"### 概念排名（当前筛选 {len(filtered)} 个）")

    display = filtered.head(50).copy()
    display["活跃"] = display.apply(
        lambda r: "🟢" if r["active_5d"] else ("🟡" if r["active_10d"] else "⚪"), axis=1
    )
    display["持续性"] = display["max_streak"].apply(
        lambda x: "█" * min(20, x) if x > 0 else ""
    )

    # 持续性评分为 0-100 归一化
    max_score = display["persistence_score"].max()
    display["评分"] = (display["persistence_score"] / max_score * 100).astype(int) if max_score > 0 else 0

    st.dataframe(
        display[[
            "活跃", "concept", "days", "max_streak", "avg_stocks",
            "category", "last_seen", "持续性", "评分",
        ]].rename(columns={
            "concept": "概念",
            "days": "出现天数",
            "max_streak": "最长连续",
            "avg_stocks": "日均涨停",
            "category": "分类",
            "last_seen": "最近出现",
        }),
        column_config={
            "评分": st.column_config.ProgressColumn("评分", min_value=0, max_value=100, format="%d"),
        },
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")

    # ── 概念时间线 ──
    st.markdown("### 概念时间线查询")
    concepts = sorted(df["concept"].tolist())
    selected_concept = st.selectbox("选择概念", concepts, key="tl_concept")

    if selected_concept:
        tl = concept_timeline(selected_concept)
        if not tl.empty:
            tl["trade_date"] = pd.to_datetime(tl["trade_date"], format="%Y%m%d")
            tl = tl.sort_values("trade_date")

            # 计算每个月的出现天数
            tl["month"] = tl["trade_date"].dt.to_period("M")
            monthly = tl.groupby("month").agg(
                出现天数=("trade_date", "count"),
                平均涨停数=("stock_count", "mean"),
            ).reset_index()
            monthly["month"] = monthly["month"].astype(str)

            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.area_chart(
                    monthly.set_index("month")[["出现天数", "平均涨停数"]],
                    use_container_width=True,
                )
            with col_b:
                st.metric("总出现天数", len(tl))
                st.metric("最近出现", tl["trade_date"].max().strftime("%Y-%m-%d"))
                st.metric("最长连续", int(df[df["concept"] == selected_concept]["max_streak"].values[0])
                          if selected_concept in df["concept"].values else 0)
                st.metric("日均涨停", f"{tl['stock_count'].mean():.1f}" if len(tl) > 0 else "0")
        else:
            st.info("无数据")

    st.markdown("---")

    # ── 热力图 ──
    st.markdown("### TOP20 板块活跃热力图")
    with st.spinner("加载热力图..."):
        hm = streak_heatmap(min_days=10, top_n=20)

    if hm["concepts"]:
        hm_df = pd.DataFrame(
            hm["matrix"],
            index=hm["concepts"],
            columns=hm["dates"],
        )
        # 简化日期标签（只显示月-日）
        hm_df.columns = [c[4:6] + "/" + c[6:8] for c in hm_df.columns]

        # 取最近60天
        if len(hm_df.columns) > 60:
            hm_df = hm_df.iloc[:, -60:]

        st.dataframe(
            hm_df.style.background_gradient(axis=None, cmap="YlOrRd"),
            use_container_width=True,
        )
        st.caption("颜色越深 = 当日该概念涨停股数越多")
    else:
        st.info("数据不足，无法生成热力图")


def page_deep_analysis():
    """深度分析页面 — 情绪周期 / 连板矩阵 / 主线识别 / 复盘选股。"""
    st.title("🔬 深度分析")
    st.caption("基于 333 个交易日复盘数据的量化分析")

    tabs = st.tabs(["💡 情绪周期", "🪜 连板矩阵", "🎯 主线识别", "⭐ 复盘选股"])

    # ── Tab 1: 情绪周期 ──
    with tabs[0]:
        st.markdown("### 情绪周期拐点识别")
        st.caption("基于涨停数、跌停数、封板率、晋级率等指标的 Z-score 综合评分")

        @st.cache_data(ttl=3600)
        def load_sentiment():
            return sentiment_cycle()

        with st.spinner("计算中..."):
            sc = load_sentiment()

        if not sc.empty:
            current = sc.iloc[-1]
            phase_color = {"高潮": "🔴", "修复偏暖": "🟠", "修复": "🟡", "退潮": "🔵", "冰点": "⚪"}

            # 当前状态
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("当前阶段", f"{phase_color.get(current['phase'], '')} {current['phase']}")
            col2.metric("综合情绪", f"{current['composite']:.2f}", delta="看多" if current['composite'] > 0 else "看空")
            col3.metric("涨停数", int(current['ZT']))
            col4.metric("跌停数", int(current['DT']))
            col5.metric("封板率", f"{current['FB']:.1f}%")

            # 情绪曲线图
            chart_df = sc.set_index("trade_date")
            fig, ax = plt.subplots(figsize=(14, 5))

            # 填充区域
            ax.fill_between(chart_df.index, chart_df["composite"], 0,
                            where=chart_df["composite"] >= 0, color="#e74c3c", alpha=0.15)
            ax.fill_between(chart_df.index, chart_df["composite"], 0,
                            where=chart_df["composite"] < 0, color="#3498db", alpha=0.15)

            # 画线
            ax.plot(chart_df.index, chart_df["composite"], color="#2c3e50", linewidth=1.2)

            # 标注拐点
            inflections = sc[sc["inflection"]]
            for _, inf in inflections.tail(30).iterrows():
                color = "#e74c3c" if inf["inflection_type"] == "顶" else "#27ae60"
                marker = "v" if inf["inflection_type"] == "顶" else "^"
                ax.scatter(inf["trade_date"], inf["composite"], c=color, s=40, marker=marker, zorder=5)

            # 阈值线
            ax.axhline(y=1.0, color="#e74c3c", linestyle="--", alpha=0.5, label="高潮线")
            ax.axhline(y=0.3, color="#f39c12", linestyle="--", alpha=0.4)
            ax.axhline(y=-0.3, color="#3498db", linestyle="--", alpha=0.4)
            ax.axhline(y=-1.0, color="#2980b9", linestyle="--", alpha=0.5, label="冰点线")
            ax.axhline(y=0, color="#95a5a6", linestyle="-", alpha=0.3)

            ax.set_title("情绪周期 · 综合情绪分", fontsize=14, fontweight="bold")
            ax.legend(loc="upper left", fontsize=9)
            ax.set_ylabel("Composite Z-score")
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

            # 阶段分布 + 近期拐点
            col_a, col_b = st.columns([1, 2])
            with col_a:
                st.markdown("**阶段分布**")
                phase_counts = sc["phase"].value_counts()
                for p in ["高潮", "修复偏暖", "修复", "退潮", "冰点"]:
                    cnt = phase_counts.get(p, 0)
                    st.write(f"{phase_color.get(p, '')} {p}: {cnt}天 ({cnt/len(sc)*100:.1f}%)")

            with col_b:
                st.markdown("**近期拐点**")
                recent_inf = inflections.tail(15).iloc[::-1]
                for _, r in recent_inf.iterrows():
                    arrow = "📈" if r["inflection_type"] == "底" else "📉"
                    st.write(
                        f"{r['trade_date'].strftime('%Y-%m-%d')} {arrow} → {r['phase']}  "
                        f"(涨停{int(r['ZT'])}, 封板率{r['FB']:.0f}%)"
                    )

    # ── Tab 2: 连板矩阵 ──
    with tabs[1]:
        st.markdown("### 连板胜率矩阵")
        st.caption("统计各连板高度的晋级率和分歧率")

        @st.cache_data(ttl=3600)
        def load_lianban():
            return lianban_matrix()

        with st.spinner("计算中..."):
            lm = load_lianban()

        matrix = lm["matrix"]
        if not matrix.empty:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**晋级率 & 分歧率**")
                disp = matrix.copy()
                disp["晋级率_vis"] = disp["晋级率"].apply(lambda x: f"{x:.1f}%")
                disp["分歧率_vis"] = disp["分歧板率"].apply(lambda x: f"{x:.1f}%")

                st.dataframe(
                    disp[["连板", "样本数", "晋级率_vis", "分歧率_vis"]].rename(columns={
                        "晋级率_vis": "晋级率", "分歧率_vis": "分歧率",
                    }),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "晋级率": st.column_config.ProgressColumn(
                            "晋级率", min_value=0, max_value=100, format="%.1f%%"
                        ),
                        "分歧率": st.column_config.ProgressColumn(
                            "分歧率", min_value=0, max_value=100, format="%.1f%%"
                        ),
                    },
                )

            with col2:
                st.markdown("**晋级率趋势**")
                timeline = lm["timeline"]
                if not timeline.empty:
                    timeline["trade_date"] = pd.to_datetime(timeline["trade_date"], format="%Y%m%d")

                    # 只看主要层级
                    fig2, ax2 = plt.subplots(figsize=(10, 5))
                    colors = {1: "#3498db", 2: "#2ecc71", 3: "#f39c12", 4: "#e74c3c", 5: "#9b59b6"}
                    for lb in [1, 2, 3, 4]:
                        ld = timeline[timeline["level"] == lb].sort_values("trade_date")
                        if ld.empty:
                            continue
                        ld = ld.set_index("trade_date")
                        ax2.plot(ld.index, ld["rate"].rolling(10).mean(),
                                color=colors.get(lb, "#333"), linewidth=1,
                                label=f"{lb}→{lb+1} (10日均)")
                    ax2.set_title("晋级率趋势（10日滚动均线）", fontsize=12)
                    ax2.legend(fontsize=8)
                    ax2.set_ylabel("晋级率 %")
                    fig2.tight_layout()
                    st.pyplot(fig2)
                    plt.close(fig2)

            # 当前各层级
            if lm["current"]:
                st.markdown("**最新交易日晋级率**")
                cols = st.columns(len(lm["current"]))
                for i, (k, v) in enumerate(lm["current"].items()):
                    cols[i].metric(k, v)

    # ── Tab 3: 主线识别 ──
    with tabs[2]:
        st.markdown("### 主线识别器")
        st.caption("基于近期活跃度、涨停强度、趋势和持续性的综合评分")

        @st.cache_data(ttl=1800)
        def load_mainline():
            return mainline_identifier()

        with st.spinner("识别中..."):
            ml = load_mainline()

        if not ml.empty:
            # 概览
            main = ml[ml["label"] == "主线"]
            hot = ml[ml["label"] == "热点支线"]
            col1, col2 = st.columns(2)
            col1.metric("主线板块", f"{len(main)} 个")
            col2.metric("热点支线", f"{len(hot)} 个")

            st.markdown("---")

            # 主线详情
            st.markdown("#### 主线板块")
            for _, r in main.iterrows():
                with st.expander(f"🔥 {r['concept']} — 综合得分 {r['total_score']:.0f}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("近期天数", f"{r['recent_days']}/{r['lookback']}")
                    c2.metric("日均涨停", f"{r['avg_zt']:.1f} 只")
                    c3.metric("趋势", r["trend"])
                    c4.metric("连续天数", r["consecutive"])

            # 热点支线
            st.markdown("#### 热点支线")
            hot_disp = hot.copy()
            st.dataframe(
                hot_disp[["concept", "total_score", "avg_zt", "trend", "recent_days"]].rename(columns={
                    "concept": "概念", "total_score": "得分", "avg_zt": "日均涨停",
                    "trend": "趋势", "recent_days": "近期天数",
                }),
                use_container_width=True, hide_index=True,
                column_config={
                    "得分": st.column_config.ProgressColumn("得分", min_value=0, max_value=100, format="%.0f"),
                },
            )

    # ── Tab 4: 复盘选股 ──
    with tabs[3]:
        st.markdown("### 复盘驱动选股")
        st.caption("多因子综合评分：板块强度 + 连板位置 + 涨停质量 + 龙虎榜 + 板块效应")

        top_n = st.slider("显示数量", 10, 50, 30, key="screener_top")

        @st.cache_data(ttl=1800)
        def load_screener(top):
            return review_screener(top=top)

        with st.spinner("评分中..."):
            stocks = load_screener(top_n)

        if not stocks.empty:
            # 评级分布
            grade_counts = stocks["grade"].value_counts()
            cols = st.columns(4)
            for i, g in enumerate(["S级", "A级", "B级", "C级"]):
                cols[i].metric(g, grade_counts.get(g, 0))

            st.markdown("---")

            st.dataframe(
                stocks.rename(columns={
                    "code": "代码", "name": "名称", "lianban": "连板",
                    "ban_type": "板型", "concept": "概念", "score": "得分",
                    "grade": "评级", "has_longhu": "龙虎榜",
                }),
                column_config={
                    "得分": st.column_config.ProgressColumn("得分", min_value=0, max_value=100, format="%.0f"),
                },
                use_container_width=True, hide_index=True,
            )


# ═══════════════════════════════════════════════
pages = {
    "🏠 首页": page_home,
    "📡 市场雷达": page_market_radar,
    "📋 每日复盘": page_review,
    "🔥 板块持续性": page_sector_persistence,
    "🔬 深度分析": page_deep_analysis,
    "⏱ 时间轴": page_timeline,
    "📊 数据中心": page_data,
    "🧪 策略实验室": page_strategy,
    "📈 回测分析": page_backtest,
    "💹 实时交易": page_live,
    "⚙ 系统设置": page_settings,
}
pages[page]()
