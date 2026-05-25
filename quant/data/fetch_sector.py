#!/usr/bin/env python3
"""板块数据抓取 — 短线侠 duanxianxia.cn API。

用法:
  python fetch_sector.py                    # 打印板块强度排行
  python fetch_sector.py --top 20           # TOP 20
  python fetch_sector.py --flow             # 含主力资金流（逐板块聚合）
  python fetch_sector.py --json             # JSON 输出
  python fetch_sector.py --sector 801660    # 查看成分股
"""

import json
import sys
import time
import urllib.request
import urllib.parse
import argparse

API_STRONG = "https://duanxianxia.cn/api/getLiveByStrong"
API_STOCKS = "https://duanxianxia.cn/data/getKaipanStock/web"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://duanxianxia.cn",
    "Referer": "https://duanxianxia.cn/",
}


def fetch_sectors():
    """获取全部板块强度 + 市场情绪。"""
    req = urllib.request.Request(API_STRONG, data=b"platelist=&type=strong", headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())

    plates = []
    for key, p in data["plates"].items():
        plates.append({
            "rank": int(key),
            "name": p["name"],
            "strength": int(p["val"]),
            "code": p["code"],
            "ztcount": int(p["ztcount"]),
        })
    plates.sort(key=lambda x: x["strength"], reverse=True)

    sentiment = None
    if "qxlive" in data and data["qxlive"]:
        q = data["qxlive"]
        series = q.get("series", {})
        axis_raw = q.get("Aaxis", "")
        if isinstance(axis_raw, list):
            axis = axis_raw
        elif isinstance(axis_raw, str):
            axis = axis_raw.split()
        else:
            axis = []
        if series and axis:
            idx = len(axis) - 1
            sentiment = {
                "time": axis[idx],
                "emotion": int(series.get("QX", [0])[idx]),
                "zt_count": int(series.get("ZT", [0])[idx]),
                "dt_count": int(series.get("DT", [0])[idx]),
                "lose_effect": int(series.get("KQXY", [0])[idx]),
                "main_flow": series.get("HSLN", [0])[idx],
                "lianban_height": int(series.get("LBGD", [0])[idx]),
                "up_count": int(series.get("SZ", [0])[idx]),
                "down_count": int(series.get("XD", [0])[idx]),
                "seal_rate": series.get("PB", [0])[idx],
                "zt_yesterday": series.get("ZTBX", [0])[idx],
                "lb_yesterday": series.get("LBBX", [0])[idx],
            }

    return plates, sentiment


def fetch_sector_stocks(code):
    """获取板块成分股。返回 [{code, name, chg_pct, jj_chg, ban_count, float_mv,
    jj_amount, turnover, net_inflow, main_net_in, lianban, longhu, turn_rate, vol_ratio}]"""
    req = urllib.request.Request(
        API_STOCKS,
        data=urllib.parse.urlencode({"plateCode": code}).encode(),
        headers=HEADERS,
    )
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())

    stocks = []
    for item in data.get("list", []):
        stocks.append({
            "code": item[0],
            "name": item[1],
            "chg_pct": item[2],
            "jj_chg": item[3],
            "ban_count": item[4],
            "float_mv": item[5],
            "jj_amount": item[6],
            "turnover": item[7],
            "jj_vol": item[8],
            "jj_amount2": item[9],
            "net_inflow": item[10],
            "main_net_in": item[11],
            "lianban": item[12],
            "longhu": item[13],
            "turn_rate": item[14],
            "vol_ratio": item[15],
        })
    return stocks


def fmt_yi(val):
    if val is None or val == 0:
        return "    -"
    yi = val / 1e8
    return f"{yi:+.1f}亿"


def main():
    p = argparse.ArgumentParser(description="板块数据抓取")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--flow", action="store_true", help="含主力资金流")
    p.add_argument("--json", action="store_true")
    p.add_argument("--sector", type=str, help="查看板块成分股 (如 801660=通信)")
    args = p.parse_args()

    if args.sector:
        stocks = fetch_sector_stocks(args.sector)
        if args.json:
            print(json.dumps(stocks, ensure_ascii=False, indent=2))
        else:
            print(f"\n板块 {args.sector} 成分股 ({len(stocks)}只)")
            print("-" * 85)
            for s in stocks:
                print(f"{s['code']} {s['name']:<8s} "
                      f"涨幅{s['chg_pct']:+.1f}% "
                      f"竞涨{s['jj_chg']:+.1f}% "
                      f"{s['lianban'] or '-'} "
                      f"主力{fmt_yi(s['main_net_in'])} "
                      f"换手{s['turn_rate']:.1f}%")
        return

    plates, sentiment = fetch_sectors()

    if args.json:
        out = {"plates": plates[:args.top], "sentiment": sentiment}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    # 文本输出
    if sentiment:
        print(f"\n市场情绪 | {sentiment['time']}")
        print(f"  情绪:{sentiment['emotion']}  涨停:{sentiment['zt_count']}  "
              f"跌停:{sentiment['dt_count']}  上涨:{sentiment['up_count']}  "
              f"下跌:{sentiment['down_count']}")
        flow = sentiment['main_flow']
        flow_label = "主力净流入" if flow >= 0 else "主力净流出"
        print(f"  {flow_label}:{abs(flow)}亿  封板率:{sentiment['seal_rate']}%  "
              f"连板高度:{sentiment['lianban_height']}")

    if args.flow:
        print(f"\n{'板块':<10s} {'强度':>5s} {'涨停':>4s} {'主力净流入':>10s} {'成分股':>6s}")
        print("-" * 55)
        results = []
        for p in plates[:args.top]:
            try:
                stocks = fetch_sector_stocks(p["code"])
                total_main = sum(s["main_net_in"] for s in stocks if s["main_net_in"])
                total_net = sum(s["net_inflow"] for s in stocks if s["net_inflow"])
                results.append((p["name"], p["strength"], p["ztcount"], total_main, total_net, len(stocks)))
            except Exception as e:
                results.append((p["name"], p["strength"], p["ztcount"], 0, 0, 0))
            time.sleep(0.12)

        results.sort(key=lambda x: x[3], reverse=True)
        for name, strength, zt, flow, net_flow, count in results:
            print(f"{name:<10s} {strength:>5d} {zt:>3d}只 主力{fmt_yi(flow)} 总{fmt_yi(net_flow)} ({count}股)")
    else:
        print(f"\n{'排名':<5s} {'板块':<10s} {'强度':>6s} {'涨停':>4s}")
        print("-" * 40)
        for i, p in enumerate(plates[:args.top]):
            print(f"{i+1:<5d} {p['name']:<10s} {p['strength']:>6d} {p['ztcount']:>4d}")


if __name__ == "__main__":
    main()
