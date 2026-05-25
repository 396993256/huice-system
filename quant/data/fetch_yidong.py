#!/usr/bin/env python3
"""竞价异动数据抓取 — 短线侠 duanxianxia.cn API（需登录）。

用法:
  python fetch_yidong.py                     # 打印异动列表
  python fetch_yidong.py --json              # JSON 输出
"""

import json
import re
import time
import argparse
from collections import Counter
from pathlib import Path

BASE = "https://duanxianxia.cn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": BASE,
    "Referer": f"{BASE}/",
    "X-Requested-With": "XMLHttpRequest",
}


def fetch_yidong(auth):
    """获取竞价异动全景数据（需已登录的 auth 对象）。
    返回 [{type, name, code, ban_desc, time, desc}, ...]
    """
    t0 = time.time()
    data = auth.post("/api/getYidongAll")
    ms = (time.time() - t0) * 1000

    html = data.get("html", "")
    ydtype = data.get("ydtype", "")

    if not html:
        return [], ydtype, ms

    # 解析 HTML 表格
    rows = re.findall(r"<tr class='yd' name='([^']+)'>(.*?)</tr>", html, re.DOTALL)
    events = []
    for name, row_html in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        clean = [re.sub(r"<[^>]+>", "", t).strip() for t in tds]
        events.append({
            "type": name,
            "name": clean[0] if len(clean) > 0 else "",
            "code": clean[1] if len(clean) > 1 else "",
            "ban_desc": clean[3] if len(clean) > 3 else "",
            "time": clean[4] if len(clean) > 4 else "",
            "desc": clean[5] if len(clean) > 5 else "",
        })

    return events, ydtype, ms


def yidong_summary(events):
    """返回异动类型汇总统计。"""
    return dict(Counter(e["type"] for e in events))


def main():
    p = argparse.ArgumentParser(description="竞价异动数据抓取")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = p.parse_args()

    from data.auth import DuanxianxiaAuth

    auth = DuanxianxiaAuth.from_saved()
    if not auth or not auth.logged_in:
        auth = DuanxianxiaAuth()
        ok = auth.login("18507507885", "qq781898")
        if not ok:
            print("登录失败")
            return

    events, ydtype, ms = fetch_yidong(auth)

    if args.json:
        print(json.dumps({
            "ydtype": ydtype,
            "count": len(events),
            "ms": round(ms),
            "summary": yidong_summary(events),
            "data": events,
        }, ensure_ascii=False, indent=2))
        return

    print(f"\n  竞价异动全景 (fetch: {ms:.0f}ms, count: {len(events)})")
    print(f"  类型: {ydtype}")
    print("-" * 90)
    print(f"  {'异动类型':<10s} {'股票':<10s} {'代码':<8s} {'板型':<10s} {'时间':<10s} {'说明'}")
    print("-" * 90)
    for e in events:
        print(f"  {e['type']:<10s} {e['name']:<10s} {e['code']:<8s} "
              f"{e['ban_desc']:<10s} {e['time']:<10s} {e['desc']}")
    print("-" * 90)

    # 统计
    print(f"\n  异动类型分布:")
    for typ, cnt in Counter(e["type"] for e in events).most_common():
        bar = "█" * (cnt // 2)
        print(f"    {typ:<10s} {cnt:>3d}  {bar}")


if __name__ == "__main__":
    main()
