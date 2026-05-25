#!/usr/bin/env python3
"""复盘数据 — 向后兼容重导出。

已迁移至 review/ 模块。推荐使用:
    from review import ReviewManager
    rm = ReviewManager()
    data = rm.review("20260522")

原有用法仍可继续使用，但新代码建议直接 import review。
"""

# 向后兼容：所有符号从 review 模块重新导出
from review.fetcher import (
    fupan_date, sentiment_curve, sector_strength, fupan_yidong,
    plate_rotate, longtou_dates, lianban_chart, longtou_stocks, lianban_range,
    fetch, _get_auth,
    INDICATOR_LABELS, ZT_COLUMNS,
    parse_indicators, parse_sector_strength, parse_yidong_rows,
    parse_concept_headers, parse_concept_with_stocks,
    _extract_keywords, group_zt_by_concept,
)

from review.longhu import fetch_longhu_list, fetch_longhu_detail

from review.report import daily_review, dump_review, ReviewManager

# CLI 保持不变
from review.cli import main

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

ENDPOINTS = {
    "fupan_date":    "/api/getFupanDate",
    "sentiment":     "/api/getChartByQingxu",
    "strength":      "/api/getChartByStrong",
    "yidong":        "/api/getFupanByYidong",
    "plate_rotate":  "/api/getPlateDayChart",
    "longtou_dates": "/api/getDatesByLongtou",
    "lianban_chart": "/api/getChartByLianban",
    "lianban_range": "/api/getLianbanRangeData",
}

if __name__ == "__main__":
    main()
