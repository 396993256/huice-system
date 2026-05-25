#!/usr/bin/env python3
"""交易日历和市场要闻 — 短线侠 duanxianxia.cn CDN 数据。

用法:
  python fetch_calendar.py                 # 检查今日是否交易日
  python fetch_calendar.py --news          # 今日政策要闻
"""

import json
import time
import urllib.request
import argparse

DATASOURCE_URL = "https://x.duanxianxia.cn/vendor/stockdata/datasource.json"
JINJI_URL = "https://x.duanxianxia.cn/vendor/stockdata/jinjidata.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://duanxianxia.cn",
    "Referer": "https://duanxianxia.cn/",
}


def fetch_trading_status():
    """获取交易日状态。返回 {istrade, nocache, data_url, base_url}"""
    t0 = time.time()
    req = urllib.request.Request(DATASOURCE_URL, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    data["_ms"] = round((time.time() - t0) * 1000)
    return data


def fetch_daily_news():
    """获取今日政策要闻/紧急数据。返回 {date, html}"""
    t0 = time.time()
    req = urllib.request.Request(JINJI_URL, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    data["_ms"] = round((time.time() - t0) * 1000)
    return data


def is_trading_day():
    """检查今日是否为交易日。返回 True/False"""
    try:
        status = fetch_trading_status()
        return status.get("istrade") is True or status.get("istrade") == 1 or status.get("istrade") == "1"
    except Exception:
        return None


def main():
    p = argparse.ArgumentParser(description="交易日历和市场要闻")
    p.add_argument("--news", action="store_true", help="查看今日要闻")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = p.parse_args()

    if args.news:
        news = fetch_daily_news()
        if args.json:
            print(json.dumps(news, ensure_ascii=False, indent=2))
        else:
            import re
            html = news.get("html", "")
            text = re.sub(r"<[^>]+>", "", html).strip()
            print(f"\n今日要闻 ({news.get('date', '-')})")
            print("-" * 60)
            print(text[:2000] if text else "(空)")
    else:
        status = fetch_trading_status()
        if args.json:
            print(json.dumps(status, ensure_ascii=False, indent=2))
        else:
            trading = is_trading_day()
            label = "交易日" if trading else ("非交易日" if trading is False else "获取失败")
            print(f"\n今日状态: {label}")
            for k, v in status.items():
                if not k.startswith("_"):
                    print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
