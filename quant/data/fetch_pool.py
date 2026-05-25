#!/usr/bin/env python3
"""涨停股票池数据抓取 — 短线侠 duanxianxia.cn API。

覆盖涨停股票池.ps1 的全部 7 个池子。

用法:
  python fetch_pool.py                          # All 模式（全部池子）
  python fetch_pool.py --pool Zt                # 涨停池
  python fetch_pool.py --pool Lb                # 连板池
  python fetch_pool.py --pool Zb                # 炸板池
  python fetch_pool.py --pool Cz                # 冲涨池
  python fetch_pool.py --pool Dt                # 跌停池
  python fetch_pool.py --pool Dm                # 大面池
  python fetch_pool.py --pool Fx                # 分析池（主力资金）
  python fetch_pool.py --top 20 --json          # JSON 输出
"""

import json
import time
import urllib.request
import argparse

BASE_API = "https://duanxianxia.cn/data"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://duanxianxia.cn",
    "Referer": "https://duanxianxia.cn/",
}

POOLS = {
    "Zt": {"name": "涨停池", "api": "getZtPoolData"},
    "Lb": {"name": "连板池", "api": "getLbPoolData"},
    "Zb": {"name": "炸板池", "api": "getZbPoolData"},
    "Cz": {"name": "冲涨池", "api": "getCzPoolData"},
    "Dt": {"name": "跌停池", "api": "getDtPoolData"},
    "Dm": {"name": "大面池", "api": "getDmPoolData"},
    "Fx": {"name": "分析池", "api": "getFxPoolData"},
}


def fetch_pool(pool_type, sort_param=""):
    """抓取单个池子数据。"""
    t0 = time.time()
    url = f"{BASE_API}/{POOLS[pool_type]['api']}"
    if sort_param:
        url = f"{url}/{sort_param}"
    req = urllib.request.Request(url, data=b"", headers=HEADERS, method="POST")
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    ms = (time.time() - t0) * 1000
    items = data.get("list", [])
    parsed = [_parse_item(item, pool_type) for item in items]
    return parsed, ms


def _parse_item(item, pool_type):
    """根据池子类型解析原始数组。"""
    if pool_type == "Zt":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "fengdan": item[3], "time": item[5], "concept": item[6] or "-",
            "ban_desc": item[7], "turnover": item[8], "float_mv": item[9],
            "ban_type": item[10] if len(item) > 10 else "",
        }
    if pool_type == "Lb":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "fengdan": item[3], "time": item[5], "concept": item[6] or "-",
            "ban_desc": item[7], "lb_count": item[11] if len(item) > 11 else "",
            "lb_height": item[12] if len(item) > 12 else "",
        }
    if pool_type == "Zb":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "time": item[5], "concept": item[6] or "-",
        }
    if pool_type == "Cz":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "concept": item[6] or "-", "turn_rate": item[10] if len(item) > 10 else "",
        }
    if pool_type == "Dt":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "concept": item[6] or "-" if len(item) > 6 else "-",
        }
    if pool_type == "Dm":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "concept": item[6] or "-", "face_pct": item[10] if len(item) > 10 else "",
        }
    if pool_type == "Fx":
        return {
            "code": item[0], "name": item[1], "chg_pct": item[2],
            "concept": item[6] or "-", "main_flow": item[10] if len(item) > 10 else "",
            "turn_rate": item[11] if len(item) > 11 else "",
        }
    return {"code": item[0] if item[0] else "-", "name": item[1] if len(item) > 1 else "-"}


def fmt_yi(val):
    """格式化金额。"""
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


def show_all(top=15):
    """All 模式 — 全部池子概览。"""
    import datetime
    print()
    print("  " + "=" * 60)
    print(f"    duanxianxia.cn 股票池全景")
    print(f"    {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  " + "=" * 60)

    for pool_type, info in POOLS.items():
        items, ms = fetch_pool(pool_type)
        items = items[:top]

        print(f"\n  [{info['name']}] (fetch: {ms:.0f}ms, count: {len(items)})")

        if not items:
            print("    (无数据)")
            continue

        for item in items:
            parts = [f"{item['code']} {item['name']}"]
            if "chg_pct" in item:
                chg = item["chg_pct"]
                parts.append(f"{chg:+.2f}%" if isinstance(chg, (int, float)) else str(chg))
            if "ban_desc" in item:
                parts.append(str(item["ban_desc"]))
            if "concept" in item:
                parts.append(str(item["concept"]))
            if "fengdan" in item and item["fengdan"]:
                parts.append(f"封单{fmt_yi(item['fengdan'])}")
            if "main_flow" in item and item["main_flow"]:
                parts.append(f"主力{fmt_yi(item['main_flow'])}")
            if "turn_rate" in item and item["turn_rate"]:
                parts.append(f"换手{item['turn_rate']}%")
            print(f"    {'  '.join(parts)}")


def main():
    p = argparse.ArgumentParser(description="涨停股票池数据抓取")
    p.add_argument("--pool", choices=list(POOLS.keys()) + ["All"],
                   default="All", help="池子类型")
    p.add_argument("--top", type=int, default=20, help="输出条数")
    p.add_argument("--sort", type=str, default="", help="排序参数")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = p.parse_args()

    if args.pool == "All":
        if args.json:
            result = {}
            for pt, info in POOLS.items():
                items, ms = fetch_pool(pt)
                result[pt] = {"name": info["name"], "count": len(items), "ms": round(ms), "data": items[:args.top]}
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            show_all(top=args.top)
    else:
        items, ms = fetch_pool(args.pool, sort_param=args.sort)
        if args.top > 0:
            items = items[:args.top]
        if args.json:
            print(json.dumps({"pool": POOLS[args.pool]["name"], "count": len(items),
                              "ms": round(ms), "data": items}, ensure_ascii=False, indent=2))
        else:
            print(f"\n  [{POOLS[args.pool]['name']}] (fetch: {ms:.0f}ms, count: {len(items)})\n")
            for item in items:
                print(json.dumps(item, ensure_ascii=False))


if __name__ == "__main__":
    main()
