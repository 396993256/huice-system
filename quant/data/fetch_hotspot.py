#!/usr/bin/env python3
"""热点数据抓取 — 短线侠 duanxianxia.cn CDN API。

覆盖热点数据.ps1 的全部功能。

用法:
  python fetch_hotspot.py                        # 全部热点概览
  python fetch_hotspot.py --type Topic           # 题材热点
  python fetch_hotspot.py --type HotHour         # 小时热门股
  python fetch_hotspot.py --type HotDay          # 日热门股
  python fetch_hotspot.py --type Skyrocket       # 飙升股
  python fetch_hotspot.py --type Keyword         # 热搜关键词
  python fetch_hotspot.py --top 10 --json        # JSON 输出
"""

import json
import time
import urllib.request
import argparse

API_URL = "https://x.duanxianxia.cn/vendor/stockdata/hotlist.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://duanxianxia.cn",
    "Referer": "https://duanxianxia.cn/",
}

TYPE_MAP = {
    "Topic":     "stock_topic",
    "HotHour":   "hot_stock_hour",
    "HotDay":    "hot_stock_day",
    "Skyrocket": "skyrocket_hour",
    "Keyword":   "hotkeyword",
}


def fetch_hotlist():
    """获取全部热点数据。"""
    t0 = time.time()
    req = urllib.request.Request(API_URL, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    ms = (time.time() - t0) * 1000
    return data, ms


def show_all(top=10):
    """展示全部热点概览。"""
    import datetime
    data, ms = fetch_hotlist()

    print()
    print("  " + "=" * 60)
    print(f"    duanxianxia.cn 热点数据")
    print(f"    {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  fetch: {ms:.0f}ms")
    print("  " + "=" * 60)

    # 题材热点
    topics = data.get("stock_topic", [])
    print(f"\n  [热点题材] ({len(topics)}条)")
    for t in topics[:top]:
        title = t.get("title", "-")
        heat = int(t.get("rate", 0))
        heat_str = f"{heat / 10000:.0f}万" if heat > 10000 else str(heat)
        print(f"    {t.get('rank', '-')}. {title}  (热度: {heat_str})")

    # 热搜关键词
    keywords = data.get("hotkeyword", [])
    print(f"\n  [热搜关键词] ({len(keywords)}条)")
    for kw in keywords[:top]:
        print(f"    {kw.get('rank', '-')}. {kw.get('keyword', '-')}  ({kw.get('count', '-')}条结果)")

    # 小时热门股
    hour_stocks = data.get("hot_stock_hour", [])
    print(f"\n  [小时热门股 TOP{top}] ({len(hour_stocks)}条)")
    for s in hour_stocks[:top]:
        heat = int(s.get("rate", 0))
        heat_str = f"{heat / 10000:.0f}万" if heat > 10000 else str(heat)
        print(f"    {s.get('rank', '-')}. {s.get('name', '-')}({s.get('code', '-')})  热度: {heat_str}")

    # 日热门股
    day_stocks = data.get("hot_stock_day", [])
    print(f"\n  [日热门股 TOP{top}] ({len(day_stocks)}条)")
    for s in day_stocks[:top]:
        heat = int(s.get("rate", 0))
        heat_str = f"{heat / 10000:.0f}万" if heat > 10000 else str(heat)
        print(f"    {s.get('rank', '-')}. {s.get('name', '-')}({s.get('code', '-')})  热度: {heat_str}")

    # 飙升股
    rising = data.get("skyrocket_hour", [])
    print(f"\n  [飙升股 TOP{top}] ({len(rising)}条)")
    for s in rising[:top]:
        print(f"    {s.get('rank', '-')}. {s.get('name', '-')}({s.get('code', '-')})  热度: {s.get('rate', '-')}")

    total = sum(len(data.get(k, [])) for k in TYPE_MAP.values())
    print(f"\n  总计: {len(topics)}题材 {len(keywords)}关键词 {len(hour_stocks)}时热 "
          f"{len(day_stocks)}日热 {len(rising)}飙升  共{total}条")
    print()


def main():
    p = argparse.ArgumentParser(description="热点数据抓取")
    p.add_argument("--type", choices=list(TYPE_MAP.keys()) + ["All"],
                   default="All", help="热点类型")
    p.add_argument("--top", type=int, default=20, help="输出条数")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = p.parse_args()

    data, ms = fetch_hotlist()

    if args.type == "All":
        if args.json:
            print(json.dumps({"ms": ms, **data}, ensure_ascii=False, indent=2))
        else:
            show_all(top=args.top)
    else:
        field = TYPE_MAP[args.type]
        items = data.get(field, [])
        if args.top > 0:
            items = items[:args.top]
        if args.json:
            print(json.dumps({"type": args.type, "count": len(items), "ms": ms, "data": items},
                             ensure_ascii=False, indent=2))
        else:
            print(f"\n  [{args.type}] (fetch: {ms:.0f}ms, count: {len(items)})\n")
            for item in items:
                print(json.dumps(item, ensure_ascii=False))


if __name__ == "__main__":
    main()
