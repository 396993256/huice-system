#!/usr/bin/env python3
"""复盘数据命令行入口。

用法:
    python -m review.cli                      # 今日复盘概览
    python -m review.cli --date 20260522     # 指定日期
    python -m review.cli --type lianban      # 只看连板天梯
    python -m review.cli --type sentiment    # 情绪曲线摘要
    python -m review.cli --json              # JSON 输出
"""

import json
import argparse

from review.fetcher import (
    fupan_date, sentiment_curve, sector_strength,
    lianban_range, plate_rotate, longtou_dates, lianban_chart,
)
from review.report import ReviewManager


def main():
    p = argparse.ArgumentParser(description="复盘数据抓取")
    p.add_argument("--date", default="", help="复盘日期 (YYYYMMDD)")
    p.add_argument("--type", default="all",
                   choices=["all", "sentiment", "strength", "yidong", "lianban",
                            "plate_rotate", "longtou"],
                   help="数据类型")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = p.parse_args()

    rm = ReviewManager()

    if args.type == "all":
        review = rm.review(args.date if args.date else None)

        if args.json:
            print(json.dumps(review, ensure_ascii=False, indent=2, default=str))
            return

        rm.print(review)

    elif args.type == "sentiment":
        data = sentiment_curve()
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(f"\n[情绪曲线] {len(data.get('Aaxis',[]))} 天")
            for l in data.get("legend", [])[:8]:
                print(f"  {l}")

    elif args.type == "strength":
        fd = fupan_date()
        data = sector_strength(date=args.date or fd.get("date", ""))
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(f"\n[板块强度]")

    elif args.type == "lianban":
        fd = fupan_date()
        data = lianban_range(args.date or fd.get("date", ""))
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(f"\n[连板天梯] HTML {len(data.get('html',''))} 字节")

    elif args.type == "plate_rotate":
        data = plate_rotate()
        print(json.dumps(data, ensure_ascii=False, indent=2) if args.json
              else f"\n[板块轮动] {json.dumps(data, ensure_ascii=False)[:200]}")

    elif args.type == "longtou":
        dates = longtou_dates()
        chart = lianban_chart()
        if args.json:
            print(json.dumps({"dates": dates, "chart": chart}, ensure_ascii=False, indent=2))
        else:
            print(f"\n[龙头高度] dates: {len(dates.get('Aaxis',[]))}, "
                  f"chart: {len(chart.get('series',[]))} 条序列")


if __name__ == "__main__":
    main()
