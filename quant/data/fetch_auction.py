#!/usr/bin/env python3
"""竞价强度数据抓取 — 短线侠 duanxianxia.cn API。

覆盖竞价强度.ps1 的全部 16 个 API Tab。

用法:
  python fetch_auction.py                    # All 模式（竞价全景）
  python fetch_auction.py --tab Daban        # 涨停委买
  python fetch_auction.py --tab Jingjia      # 集合竞价
  python fetch_auction.py --tab Vratio       # 竞价爆量
  python fetch_auction.py --tab Zhuli        # 竞价净额
  python fetch_auction.py --tab Qiangchou    # 竞价抢筹
  python fetch_auction.py --tab Ztlast       # 昨日涨停
  python fetch_auction.py --tab Zhaban       # 昨炸板
  python fetch_auction.py --tab Duanban      # 昨断板
  python fetch_auction.py --tab Longhu       # 昨上榜
  python fetch_auction.py --tab ZtPool       # 涨停池
  python fetch_auction.py --tab LbPool       # 连板池
  python fetch_auction.py --tab ZbPool       # 炸板池
  python fetch_auction.py --tab CzPool       # 冲涨池
  python fetch_auction.py --tab DmPool       # 大面池
  python fetch_auction.py --tab FxPool       # 分析池
  python fetch_auction.py --top 20           # 限制条数
  python fetch_auction.py --json             # JSON 输出
"""

import json
import sys
import time
import urllib.request
import urllib.parse
import argparse

BASE_API1 = "https://duanxianxia.cn/api"   # getDabanData, getJingjiaData
BASE_API2 = "https://duanxianxia.cn/data"   # 其余端点

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://duanxianxia.cn",
    "Referer": "https://duanxianxia.cn/",
}

# Tab 配置
TABS = {
    "Daban":     {"name": "涨停委买",   "api": f"{BASE_API1}/getDabanData",    "has_sort": True},
    "Ztlast":    {"name": "昨日涨停",   "api": f"{BASE_API2}/getZtlastData",   "has_sort": True},
    "Jingjia":   {"name": "集合竞价",   "api": f"{BASE_API1}/getJingjiaData",   "has_sort": False},
    "Vratio":    {"name": "竞价爆量",   "api": f"{BASE_API2}/getVratioData",    "has_sort": True},
    "Zhuli":     {"name": "竞价净额",   "api": f"{BASE_API2}/getJjzhuliData",   "has_sort": True},
    "Qiangchou": {"name": "竞价抢筹",   "api": f"{BASE_API2}/getQiangchouData", "has_sort": True},
    "Zhaban":    {"name": "昨炸板",     "api": f"{BASE_API2}/getZhabanData",    "has_sort": True},
    "Duanban":   {"name": "昨断板",     "api": f"{BASE_API2}/getDuanbanData",   "has_sort": True},
    "Longhu":    {"name": "昨上榜",     "api": f"{BASE_API2}/getLonghuData",    "has_sort": True},
    "ZtPool":    {"name": "涨停池",     "api": f"{BASE_API2}/getZtPoolData",    "has_sort": False},
    "LbPool":    {"name": "连板池",     "api": f"{BASE_API2}/getLbPoolData",    "has_sort": False},
    "ZbPool":    {"name": "炸板池",     "api": f"{BASE_API2}/getZbPoolData",    "has_sort": False},
    "CzPool":    {"name": "冲涨池",     "api": f"{BASE_API2}/getCzPoolData",    "has_sort": False},
    "DtPool":    {"name": "跌停池",     "api": f"{BASE_API2}/getDtPoolData",    "has_sort": False},
    "DmPool":    {"name": "大面池",     "api": f"{BASE_API2}/getDmPoolData",    "has_sort": False},
    "FxPool":    {"name": "分析池",     "api": f"{BASE_API2}/getFxPoolData",    "has_sort": False},
}


def _post(url, sort_param=""):
    """POST API，返回解析后的数据列表。"""
    if sort_param:
        url = f"{url}/{sort_param}"
    req = urllib.request.Request(url, data=b"", headers=HEADERS, method="POST")
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def fmt_money(val):
    """格式化金额为易读字符串。"""
    if val is None or val == "" or val == "-":
        return "-"
    try:
        v = float(val)
        if abs(v) >= 1e8:
            return f"{v / 1e8:.2f}亿"
        if abs(v) >= 1e4:
            return f"{v / 1e4:.0f}万"
        return f"{v:.0f}"
    except (ValueError, TypeError):
        return str(val)


def fetch_tab(tab_type, top=0, sort_param=""):
    """抓取单个 Tab 数据，返回结构化列表。"""
    t0 = time.time()
    tab_info = TABS[tab_type]
    result = _post(tab_info["api"], sort_param)
    ms = (time.time() - t0) * 1000

    if tab_type == "Jingjia":
        items = result if isinstance(result, list) else []
    elif tab_type == "Qiangchou":
        items = result.get("grab", []) or result.get("qiangchou", []) or result.get("list", [])
    else:
        items = result.get("list", [])

    if not items:
        return [], ms

    parsed = [_parse_item(item, tab_type) for item in items]
    if top > 0:
        parsed = parsed[:top]
    return parsed, ms


def _parse_item(item, tab_type):
    """根据 Tab 类型解析原始数组为字典。"""
    if tab_type == "Daban":
        return {
            "code": item[0], "name": item[1], "price": item[2],
            "chg_pct": item[3], "fengdan": item[4], "chg2": item[5],
            "turnover": item[6], "turn_rate": item[7], "amount": item[8],
            "amount2": item[9], "amount3": item[10], "concept": item[11] or "-",
            "float_mv": item[12], "turnover2": item[13], "net_inflow": item[14],
            "net_inflow2": item[15], "ban_type": item[16], "popular": item[17],
        }
    if tab_type == "Ztlast":
        return {
            "code": item[0], "name": item[1], "turn_rate": item[2],
            "popular": item[3], "jj_chg": item[4], "real_chg": item[5],
            "turnover": item[6], "lb_count": item[7], "lb_desc": item[8],
            "jj_amount": item[10] if len(item) > 10 else "", "jj_vratio": item[11] if len(item) > 11 else "",
        }
    if tab_type == "Jingjia":
        return {
            "code": item.get("code", ""), "name": item.get("name", ""),
            "chg_pct": item.get("zf", 0), "jj_amount": item.get("amount", 0),
            "buy1": item.get("buy1", 0), "sell1": item.get("sell1", 0),
            "float_mv": item.get("mv", 0), "volume": item.get("volume", 0),
            "time": item.get("time", ""), "ulimit": item.get("ulimit", 0),
        }
    if tab_type == "Vratio":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "popular": item[3], "jj_chg": item[4], "jj_amount": item[5],
            "concept": item[6] or "-", "jj_chg2": item[7], "jj_amount2": item[8],
            "turnover": item[9], "vratio": item[10], "turn_rate": item[11],
            "float_mv_ratio": item[12] if len(item) > 12 else "",
        }
    if tab_type == "Zhuli":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "jj_chg": item[3], "net_inflow": item[4], "popular": item[5],
            "jj_amount": item[6], "concept": item[7] or "-", "turn_rate": item[8],
        }
    if tab_type in ("Zhaban", "Duanban", "Longhu"):
        result = {"code": item[0], "name": item[1], "chg_pct": item[2] if item[2] else "-"}
        if len(item) >= 8:
            result.update({
                "popular": item[3], "jj_chg": item[4] if item[4] else "-",
                "yes_chg": item[5] if len(item) > 5 and item[5] else "-",
                "float_mv": item[6] if len(item) > 6 else "",
                "concept": item[7] if len(item) > 7 and item[7] else "-",
            })
        return result
    if tab_type == "ZtPool":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "amount": item[3], "time": item[5], "concept": item[6] or "-",
            "ban_type": item[7], "amount2": item[8], "amount3": item[9],
            "seal_type": item[10] if len(item) > 10 else "",
        }
    if tab_type == "LbPool":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "fengdan": item[3], "time": item[5], "concept": item[6] or "-",
            "ban_type": item[7], "lb_count": item[11] if len(item) > 11 else "",
            "lb_height": item[12] if len(item) > 12 else "",
        }
    if tab_type == "ZbPool":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "time": item[5], "concept": item[6] or "-",
        }
    if tab_type == "CzPool":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "concept": item[6] or "-", "turn_rate": item[10] if len(item) > 10 else "",
        }
    if tab_type == "DmPool":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "concept": item[6] or "-", "face_pct": item[10] if len(item) > 10 else "",
        }
    if tab_type == "DtPool":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "concept": item[6] or "-" if len(item) > 6 else "-",
        }
    if tab_type == "FxPool":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "concept": item[6] or "-", "main_flow": item[10] if len(item) > 10 else "",
            "turn_rate": item[11] if len(item) > 11 else "",
        }
    if tab_type == "Qiangchou":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2] if item[2] else "-",
            "jj_chg": item[4] if len(item) > 4 and item[4] else "-",
            "jj_amount": item[5] if len(item) > 5 else "",
            "concept": item[6] if len(item) > 6 and item[6] else "-",
            "turn_rate": item[8] if len(item) > 8 and item[8] else "-",
        }
    return {"code": item[0], "name": item[1], "chg_pct": item[2] if item[2] else "-"}


def print_table(items, cols, title="", color=""):
    """打印格式化的表格。"""
    if title:
        print(f"\n  [{title}] ({len(items)}条)")
    if not items:
        print("  (无数据)")
        return
    # 计算列宽
    widths = {}
    for col_key, col_label in cols:
        widths[col_key] = max(
            len(col_label),
            max((len(str(item.get(col_key, "-"))) for item in items), default=0),
        )
    # 表头
    header = "  " + "  ".join(f"{col_label:{widths[col_key]}s}" for col_key, col_label in cols)
    print(header)
    print("  " + "-" * (len(header) - 2))
    # 数据行
    for item in items:
        row = "  " + "  ".join(f"{str(item.get(col_key, '-')):{widths[col_key]}s}" for col_key, _ in cols)
        print(row)


def show_all(top=20):
    """All 模式 — 竞价强度全景概览（类 PS1 All 模式）。"""
    import datetime
    print()
    print("  " + "=" * 60)
    print(f"    duanxianxia.cn 竞价强度全景")
    print(f"    {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  " + "=" * 60)

    # 1. 涨停委买 Top15
    items, ms = fetch_tab("Daban", top=top)
    print_table(items, [
        ("code", "代码"), ("name", "名称"), ("chg_pct", "涨幅"),
        ("fengdan", "封单"), ("concept", "概念"), ("ban_type", "板型"),
        ("popular", "人气"),
    ], f"涨停委买 (fetch: {ms:.0f}ms, count: {len(items)})")

    # 涨停结构统计
    lb_groups = {}
    for item in items:
        bt = item.get("ban_type", "")
        if "连板" in str(bt):
            lb_groups[bt] = lb_groups.get(bt, 0) + 1
    if lb_groups:
        parts = " → ".join(f"{k}({v}只)" for k, v in sorted(lb_groups.items()))
        print(f"  连板结构: {parts}")

    # 2. 昨日涨停表现
    items, ms = fetch_tab("Ztlast", top=top)
    print_table(items, [
        ("code", "代码"), ("name", "名称"), ("turn_rate", "换手"),
        ("jj_chg", "竞价涨"), ("real_chg", "实时涨"), ("jj_amount", "竞价额"),
        ("jj_vratio", "量比"), ("lb_desc", "连板"),
    ], f"昨日涨停 (fetch: {ms:.0f}ms)")

    jj_up = sum(1 for i in items if i.get("jj_chg") and float(i["jj_chg"]) > 0)
    jj_down = sum(1 for i in items if i.get("jj_chg") and float(i["jj_chg"]) < 0)
    premium = f"{jj_up / len(items) * 100:.0f}%" if items else "0%"
    print(f"  竞价上涨: {jj_up}只  竞价下跌: {jj_down}只  溢价率: {premium}")

    # 3. 竞价爆量
    items, ms = fetch_tab("Vratio", top=top)
    print_table(items, [
        ("code", "代码"), ("name", "名称"), ("chg_pct", "涨幅"),
        ("jj_chg", "竞涨"), ("jj_amount", "竞额"), ("concept", "概念"),
        ("vratio", "量比"), ("turn_rate", "换手"),
    ], f"竞价爆量 (fetch: {ms:.0f}ms)")

    # 4. 竞价净额
    items, ms = fetch_tab("Zhuli", top=top)
    print_table(items, [
        ("code", "代码"), ("name", "名称"), ("chg_pct", "涨幅"),
        ("jj_chg", "竞涨"), ("net_inflow", "净流入"), ("popular", "人气"),
        ("jj_amount", "竞额"), ("concept", "概念"),
    ], f"竞价净额 (fetch: {ms:.0f}ms)")

    # 5. 集合竞价
    items, ms = fetch_tab("Jingjia", top=top)
    if items:
        items.sort(key=lambda x: float(x.get("chg_pct", 0) or 0), reverse=True)
    print_table(items, [
        ("code", "代码"), ("name", "名称"), ("chg_pct", "涨幅"),
        ("jj_amount", "竞额"), ("float_mv", "市值"), ("time", "时间"),
    ], f"集合竞价 (fetch: {ms:.0f}ms)")

    up = sum(1 for i in items if i.get("chg_pct") and float(i["chg_pct"]) > 0)
    down = sum(1 for i in items if i.get("chg_pct") and float(i["chg_pct"]) < 0)
    zt = sum(1 for i in items if i.get("ulimit") == 1)
    dt = sum(1 for i in items if i.get("ulimit") == -1)
    print(f"  上涨:{up} 下跌:{down} 涨停:{zt} 跌停:{dt}")

    # 6-9. 简略展示
    for tab, title in [("Zhaban", "昨炸板"), ("Qiangchou", "竞价抢筹"),
                        ("Duanban", "昨断板"), ("Longhu", "昨上榜")]:
        items, ms = fetch_tab(tab, top=10)
        print_table(items, [
            ("code", "代码"), ("name", "名称"), ("chg_pct", "涨幅"),
            ("jj_chg", "竞涨"), ("concept", "概念"),
        ], f"{title} (fetch: {ms:.0f}ms, count: {len(items)})")


def main():
    p = argparse.ArgumentParser(description="竞价强度数据抓取")
    p.add_argument("--tab", choices=list(TABS.keys()) + ["All"], default="All", help="数据Tab")
    p.add_argument("--top", type=int, default=20, help="输出条数 (0=全部)")
    p.add_argument("--sort", type=str, default="", help="排序参数")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = p.parse_args()

    if args.tab == "All":
        if args.json:
            result = {}
            for tab in TABS:
                items, ms = fetch_tab(tab, top=args.top)
                result[tab] = {"count": len(items), "ms": ms, "data": items}
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            show_all(top=args.top)
    else:
        items, ms = fetch_tab(args.tab, top=args.top, sort_param=args.sort)
        if args.json:
            print(json.dumps({"count": len(items), "ms": ms, "data": items},
                             ensure_ascii=False, indent=2))
        else:
            tab_name = TABS[args.tab]["name"]
            print(f"\n  [{tab_name}] (fetch: {ms:.0f}ms, count: {len(items)})\n")
            for item in items:
                print(json.dumps(item, ensure_ascii=False))


if __name__ == "__main__":
    main()
