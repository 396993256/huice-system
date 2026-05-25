#!/usr/bin/env python3
"""慧策系统 — 短线侠数据 API 统一封装。

所有 duanxianxia.cn 公开 API 的统一入口，方便新策略调用。

用法:
  from data.api import duanxianxia as dx

  # ── 板块数据 ──
  plates, sentiment = dx.sectors()           # 270板块强度 + 市场情绪
  stocks = dx.sector_stocks("801660")        # 通信板块成分股

  # ── 竞价数据 ──
  items = dx.auction("Daban")                # 涨停委买
  items = dx.auction("Jingjia")              # 集合竞价
  items = dx.auction("Vratio")               # 竞价爆量
  items = dx.auction("Zhuli")                # 竞价净额（主力流入）
  items = dx.auction("All")                  # 全景模式

  # ── 股票池 ──
  items = dx.pool("Zt")                      # 涨停池
  items = dx.pool("Lb")                      # 连板池
  items = dx.pool("Fx")                      # 分析池（主力资金）

  # ── 热点数据 ──
  data = dx.hotspot()                        # 全部热点
  data = dx.hotspot("Topic")                 # 题材热点
  data = dx.hotspot("HotDay")                # 日热门股

  # ── 工具函数 ──
  dx.fmt_money(123456789)                    # "12.35亿"

  # ── 交易日历 ──
  status = dx.trading_status()               # 今日是否交易日 + 数据源配置
  news = dx.daily_news()                     # 今日政策要闻
  dx.is_market_open()                        # True/False

  # ── 互动易 & 挖掘 ──
  data = dx.hudongyi()                       # 投资者互动问答
  data = dx.wajue()                          # 数据挖掘匹配

  # ── 需登录 ──
  data = dx.yidong_all()                     # 竞价异动全景（29KB+）
  data = dx.yanbao_list()                    # 研报列表
  data = dx.wajue_detail()                   # 数据挖掘匹配详情

  # ── 复盘（需登录）──
  date = dx.fupan_date()                     # 最新复盘日期
  sc = dx.sentiment_curve()                  # 情绪曲线（575天历史）
  ss = dx.sector_strength(date="20260522")   # 板块强度时间序列
  yi = dx.fupan_yidong(date="20260522")      # 复盘异动（涨停/跌停/炸板）
  pr = dx.plate_rotate()                     # 板块日内轮动
  ld = dx.longtou_dates()                    # 龙头高度可用日期
  lc = dx.lianban_chart()                    # 连板统计图（龙头趋势）
  lr = dx.lianban_range(date="20260522")     # 连板天梯 HTML
  dx.dump_review("review.json")             # 导出全部复盘数据

API 覆盖清单 (38/43):
  ✅ 18 公开 POST API + 2 CDN JSON + 5 公开 GET API + 3 需登录 API（异动/研报/挖掘）
  ✅ 10 复盘 API（情绪/强度/异动/轮动/龙头/连板/概念分组含板块启动理由）
  🔒  5 需 VIP 订阅（热点聚焦/聚合热搜）
  🔒  8 需参数/其他（概念搜索/龙虎榜/公告列表/用户信息等）
"""

import json
import urllib.request

try:
    import akshare as ak
except ImportError:
    ak = None  # type: ignore

from data.fetch_sector import fetch_sectors, fetch_sector_stocks, fmt_yi
from data.fetch_auction import fetch_tab, TABS as AUCTION_TABS, HEADERS as API_HEADERS
from data.fetch_pool import fetch_pool, POOLS
from data.fetch_hotspot import fetch_hotlist, TYPE_MAP as HOTSPOT_TYPES
from data.fetch_calendar import fetch_trading_status, fetch_daily_news, is_trading_day
from data.fetch_yidong import fetch_yidong, yidong_summary
from data.fetch_fupan import (
    fupan_date, sentiment_curve, sector_strength, fupan_yidong,
    plate_rotate, longtou_dates, lianban_chart, lianban_range,
    longtou_stocks, dump_review,
    daily_review, parse_indicators, parse_sector_strength,
    parse_concept_headers, parse_concept_with_stocks,
    fetch_longhu_list, fetch_longhu_detail,
    group_zt_by_concept, INDICATOR_LABELS,
)
try:
    import akshare as ak
except ImportError:
    ak = None  # type: ignore


# ── 板块 ──

def sectors():
    """返回 (plates, sentiment)。
    plates: [{rank, name, strength, code, ztcount}, ...] 按强度排序
    sentiment: {time, emotion, zt_count, dt_count, main_flow, seal_rate, ...}
    """
    return fetch_sectors()


def sector_stocks(code):
    """返回板块成分股列表。
    每只: {code, name, chg_pct, jj_chg, ban_count, float_mv,
           net_inflow, main_net_in, lianban, turn_rate, vol_ratio, ...}
    """
    return fetch_sector_stocks(code)


def sector_flow(code=None):
    """计算板块资金流。code=None 返回 TOP15 板块资金流排行。
    返回 [{name, strength, ztcount, main_net_flow, net_flow, stock_count}, ...]
    main_net_flow = 主力净流入(可为负), net_flow = 总净流入
    """
    import time
    plates, _ = fetch_sectors()

    if code:
        stocks = fetch_sector_stocks(code)
        main_total = sum(s["main_net_in"] for s in stocks if s["main_net_in"])
        net_total = sum(s["net_inflow"] for s in stocks if s["net_inflow"])
        return {"code": code, "main_net_flow": main_total, "net_flow": net_total, "stock_count": len(stocks)}

    # TOP15 非ST板块资金流
    top = [p for p in plates if "ST" not in p["name"]][:15]
    results = []
    for p in top:
        try:
            stocks = fetch_sector_stocks(p["code"])
            main_total = sum(s["main_net_in"] for s in stocks if s["main_net_in"])
            net_total = sum(s["net_inflow"] for s in stocks if s["net_inflow"])
            results.append({
                "name": p["name"], "code": p["code"],
                "strength": p["strength"], "ztcount": p["ztcount"],
                "main_net_flow": main_total, "net_flow": net_total, "stock_count": len(stocks),
            })
        except Exception:
            results.append({**p, "main_net_flow": 0, "net_flow": 0, "stock_count": 0})
        time.sleep(0.1)
    results.sort(key=lambda x: x["net_flow"], reverse=True)
    return results


# ── 竞价 ──

def auction(tab="All", top=0, sort_param=""):
    """抓取竞价数据。tab: Daban|Ztlast|Jingjia|Vratio|Zhuli|Qiangchou|
    Zhaban|Duanban|Longhu|ZtPool|LbPool|ZbPool|CzPool|DtPool|DmPool|FxPool|All
    """
    if tab == "All":
        result = {}
        for key in AUCTION_TABS:
            items, ms = fetch_tab(key, top=top)
            result[key] = {"name": AUCTION_TABS[key]["name"], "count": len(items), "ms": round(ms), "data": items}
        return result
    items, ms = fetch_tab(tab, top=top, sort_param=sort_param)
    return items


# ── 股票池 ──

def pool(pool_type="All", top=0, sort_param=""):
    """抓取股票池。pool_type: Zt|Lb|Zb|Cz|Dt|Dm|Fx|All"""
    if pool_type == "All":
        result = {}
        for key, info in POOLS.items():
            items, ms = fetch_pool(key, sort_param)
            if top > 0:
                items = items[:top]
            result[key] = {"name": info["name"], "count": len(items), "ms": round(ms), "data": items}
        return result
    items, ms = fetch_pool(pool_type, sort_param)
    if top > 0:
        items = items[:top]
    return items


# ── 热点 ──

def hotspot(hot_type="All", top=0):
    """抓取热点数据。hot_type: Topic|HotHour|HotDay|Skyrocket|Keyword|All"""
    data, ms = fetch_hotlist()
    if hot_type == "All":
        return {k: v[:top] if top > 0 else v for k, v in data.items()}
    field = HOTSPOT_TYPES[hot_type]
    items = data.get(field, [])
    return items[:top] if top > 0 else items


# ── 工具 ──

def fmt_money(val):
    return fmt_yi(val)


def market_overview():
    """返回一句话市场概况。"""
    _, sentiment = fetch_sectors()
    if not sentiment:
        return "数据获取失败"
    emo = sentiment["emotion"]
    flow = sentiment["main_flow"]
    flow_label = "主力流入" if flow >= 0 else "主力流出"
    return (
        f"情绪:{emo} 涨停:{sentiment['zt_count']} 跌停:{sentiment['dt_count']} "
        f"上涨:{sentiment['up_count']} 下跌:{sentiment['down_count']} "
        f"{flow_label}:{abs(flow)}亿 封板率:{sentiment['seal_rate']}%"
    )


# ── 批量导出 ──

def dump_all(filepath=None):
    """导出全部公开数据到 JSON 文件。"""
    import time as _time
    result = {
        "fetched_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
        "market": market_overview(),
        "sectors": sectors()[0][:50],
        "pools": pool("All", top=30),
        "auction_tabs": {k: auction(k, top=30) for k in ["Daban", "Vratio", "Zhuli", "Qiangchou"]},
        "hotspot": hotspot("All", top=20),
    }
    if filepath:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"已导出到 {filepath}")
    return result


# ── 交易日历 ──


def trading_status():
    """返回交易日状态。{istrade, nocache, data_url, base_url}"""
    return fetch_trading_status()


def daily_news():
    """返回今日政策要闻。{date, html}"""
    return fetch_daily_news()


def is_market_open():
    """今日是否为交易日。"""
    return is_trading_day()


# ── 互动易 & 数据挖掘 ──


def hudongyi():
    """获取互动易数据（投资者问答）。返回 {result, hudong, gplist}"""
    url = "https://duanxianxia.cn/api/getHudongyi"
    req = urllib.request.Request(url, headers=dict(API_HEADERS))
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def wajue():
    """获取数据挖掘匹配结果。返回 {result, match, id}"""
    url = "https://duanxianxia.cn/api/getWajueMatch"
    req = urllib.request.Request(url, headers=dict(API_HEADERS))
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())


# ── 需登录 API ──


def _get_auth_opener():
    """获取已登录的 opener（自动使用保存的 session 或重新登录）。"""
    from data.auth import DuanxianxiaAuth
    auth = DuanxianxiaAuth.from_saved()
    if not auth or not auth.logged_in:
        auth = DuanxianxiaAuth()
        auth.login("18507507885", "qq781898")
    return auth


def yidong_all():
    """获取竞价异动全景数据（需登录）。返回 (events, ydtype, ms)"""
    auth = _get_auth_opener()
    events, ydtype, ms = fetch_yidong(auth)
    return events


def yidong_summary_data():
    """竞价异动类型统计（需登录）。"""
    events = yidong_all()
    return yidong_summary(events)


def yanbao_list(code=None):
    """获取研报列表（需登录）。"""
    auth = _get_auth_opener()
    data = auth.post("/api/getYanBaoList", {"code": code} if code else {})
    return data


def wajue_detail():
    """获取数据挖掘匹配详情（需登录）。返回 {result, match, id}"""
    auth = _get_auth_opener()
    data = auth.get("/api/getWajueMatch")
    return data


# ── 数据源配置 ──


def datasource_config():
    """获取数据源配置（包含基准URL等）。返回 {istrade, nocache, data_url, base_url}"""
    return fetch_trading_status()


# ── 交易日历 ──

def trade_calendar(start="20200101", end="20261231"):
    """获取交易日历，返回 trade_date 列表。"""
    if ak is None:
        raise ImportError("请先安装 akshare")
    df = ak.tool_trade_date_hist_sina()
    if df is None or df.empty:
        return []
    df["trade_date"] = df["trade_date"].astype(str).str.replace("-", "")
    start = str(start).replace("-", "")
    end = str(end).replace("-", "")
    mask = (df["trade_date"] >= start) & (df["trade_date"] <= end)
    return df.loc[mask, "trade_date"].tolist()


def fetch_trade_calendar(start="20200101", end="20261231"):
    return trade_calendar(start, end)


# ── 历史行情 ──

def stock_hist(code, start_date, end_date, adjust="qfq"):
    """获取 A 股日线历史行情，返回 akshare DataFrame。"""
    if ak is None:
        raise ImportError("请先安装 akshare")
    start = str(start_date).replace("-", "")
    end = str(end_date).replace("-", "")
    return ak.stock_zh_a_hist(
        symbol=str(code).zfill(6),
        period="daily",
        start_date=f"{start[:4]}-{start[4:6]}-{start[6:8]}",
        end_date=f"{end[:4]}-{end[4:6]}-{end[6:8]}",
        adjust=adjust,
    )


# ── 命名空间导出（兼容 `from data.api import duanxianxia as dx`）──


class _DuanXianXiaAPI:
    """短线侠 API 命名空间。"""
    sectors = staticmethod(sectors)
    sector_stocks = staticmethod(sector_stocks)
    sector_flow = staticmethod(sector_flow)
    auction = staticmethod(auction)
    pool = staticmethod(pool)
    hotspot = staticmethod(hotspot)
    fmt_money = staticmethod(fmt_money)
    market_overview = staticmethod(market_overview)
    dump_all = staticmethod(dump_all)
    trading_status = staticmethod(trading_status)
    daily_news = staticmethod(daily_news)
    is_market_open = staticmethod(is_market_open)
    hudongyi = staticmethod(hudongyi)
    wajue = staticmethod(wajue)
    datasource_config = staticmethod(datasource_config)
    trade_calendar = staticmethod(trade_calendar)
    fetch_trade_calendar = staticmethod(fetch_trade_calendar)
    stock_hist = staticmethod(stock_hist)
    yidong_all = staticmethod(yidong_all)
    yidong_summary = staticmethod(yidong_summary_data)
    yanbao_list = staticmethod(yanbao_list)
    wajue_detail = staticmethod(wajue_detail)

    # ── 复盘（需登录）──
    fupan_date = staticmethod(fupan_date)
    sentiment_curve = staticmethod(sentiment_curve)
    sector_strength = staticmethod(sector_strength)
    fupan_yidong = staticmethod(fupan_yidong)
    plate_rotate = staticmethod(plate_rotate)
    longtou_dates = staticmethod(longtou_dates)
    lianban_chart = staticmethod(lianban_chart)
    lianban_range = staticmethod(lianban_range)
    longtou_stocks = staticmethod(longtou_stocks)
    dump_review = staticmethod(dump_review)
    daily_review = staticmethod(daily_review)
    parse_indicators = staticmethod(parse_indicators)
    parse_sector_strength = staticmethod(parse_sector_strength)
    group_zt_by_concept = staticmethod(group_zt_by_concept)
    parse_concept_headers = staticmethod(parse_concept_headers)
    parse_concept_with_stocks = staticmethod(parse_concept_with_stocks)
    fetch_longhu_list = staticmethod(fetch_longhu_list)
    fetch_longhu_detail = staticmethod(fetch_longhu_detail)
    review = staticmethod(daily_review)  # dx.review("20260522") 快捷方式


duanxianxia = _DuanXianXiaAPI()


if __name__ == "__main__":
    # 快速测试
    print(market_overview())
    plates, _ = sectors()
    print(f"板块: {len(plates)}个, TOP3: {[(p['name'], p['strength']) for p in plates[:3]]}")
