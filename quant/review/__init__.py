#!/usr/bin/env python3
"""慧策复盘模块 — 统一复盘数据入口。

用法:
    from review import ReviewManager

    rm = ReviewManager()
    data = rm.review("20260522")
    rm.print(data)
    rm.dump("20260522", "review.json")

    # 单独查询
    from review import fetch_longhu_list, fetch_longhu_detail
    seats = fetch_longhu_detail("603186", "20260522")
"""

from review.report import ReviewManager, daily_review, dump_review

from review.fetcher import (
    # API 函数
    fupan_date, sentiment_curve, sector_strength, fupan_yidong,
    plate_rotate, longtou_dates, lianban_chart, longtou_stocks, lianban_range,
    # 解析函数
    parse_indicators, parse_sector_strength, parse_yidong_rows,
    parse_concept_headers, parse_concept_with_stocks,
    group_zt_by_concept,
    # 常量
    INDICATOR_LABELS, ZT_COLUMNS,
)

from review.longhu import fetch_longhu_list, fetch_longhu_detail

from review.store import (
    init_review_db, save_review,
    query_indicators, query_sector_trend, query_lianban_stats,
    query_zt_by_concept, backfill,
)

__all__ = [
    "ReviewManager",
    "daily_review", "dump_review",
    "fupan_date", "sentiment_curve", "sector_strength", "fupan_yidong",
    "plate_rotate", "longtou_dates", "lianban_chart", "longtou_stocks", "lianban_range",
    "parse_indicators", "parse_sector_strength", "parse_yidong_rows",
    "parse_concept_headers", "parse_concept_with_stocks",
    "group_zt_by_concept",
    "fetch_longhu_list", "fetch_longhu_detail",
    "init_review_db", "save_review",
    "query_indicators", "query_sector_trend", "query_lianban_stats",
    "query_zt_by_concept", "backfill",
    "INDICATOR_LABELS", "ZT_COLUMNS",
]
