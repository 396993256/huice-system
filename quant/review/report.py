#!/usr/bin/env python3
"""每日复盘报告 — 整合 duanxianxia API + akshare 龙虎榜。"""

import json
import time

from review.fetcher import (
    fupan_date, sentiment_curve, sector_strength, fupan_yidong,
    plate_rotate, longtou_dates, lianban_chart, lianban_range,
    parse_indicators, parse_sector_strength, parse_yidong_rows,
    parse_concept_with_stocks, INDICATOR_LABELS,
)
from review.longhu import fetch_longhu_list


class ReviewManager:
    """复盘管理器 — 一站式复盘数据入口。

    用法:
        from review import ReviewManager

        rm = ReviewManager()
        data = rm.review("20260522")
        # → {date, indicators, sectors, concept_groups, zt_by_concept,
        #     zt_by_lianban, longhu_list, lianban_html}
        rm.print(data)  # 格式化输出
        rm.dump("20260522", "review.json")  # 导出 JSON
    """

    def __init__(self):
        self._auth = None

    def review(self, date=None):
        """一站式每日复盘。

        参数:
            date: '20260522' 或 '2026-05-22'，None 取最新
        返回:
            {date, indicators, indicator_labels, sectors, concept_groups,
             zt_by_concept, zt_by_lianban, longhu_list, lianban_html}
        """
        if date is None:
            fd = fupan_date()
            date = fd.get("date", "")
            if not date:
                sc_temp = sentiment_curve()
                aaxis = sc_temp.get("Aaxis", [])
                date = aaxis[-1] if aaxis else ""

        sc = sentiment_curve()
        ind = parse_indicators(sc, date=date)
        if ind.get("error"):
            return {"date": date, "error": ind["error"],
                    "indicators": {}, "indicator_labels": INDICATOR_LABELS,
                    "sectors": [], "concept_groups": [],
                    "zt_by_concept": [], "zt_by_lianban": [],
                    "longhu_list": [], "lianban_html": ""}

        date_str = date.replace("-", "") if date else ""
        ss = sector_strength(date=date_str) if date_str else sector_strength()
        sectors = parse_sector_strength(ss, top=None) if ss else []

        yi_plate = fupan_yidong(zttype="plate", date=date_str) if date_str else fupan_yidong(zttype="plate")
        yi_lianban = fupan_yidong(zttype="lianban", date=date_str) if date_str else fupan_yidong(zttype="lianban")

        plate_html = yi_plate.get("html", "") if yi_plate else ""
        concept_groups = parse_concept_with_stocks(plate_html)

        zt_by_concept = parse_yidong_rows(yi_plate) if yi_plate else []
        zt_by_lianban = parse_yidong_rows(yi_lianban) if yi_lianban else []
        lr = lianban_range(date=date_str) if date_str else lianban_range()

        lh_list = []
        try:
            lh_list = fetch_longhu_list(date_str) if date_str else []
        except Exception:
            pass

        lh_codes = {item["code"] for item in lh_list}
        for z in zt_by_concept:
            if z.get("code") in lh_codes:
                z["longhu_detail"] = True
        for z in zt_by_lianban:
            if z.get("code") in lh_codes:
                z["longhu_detail"] = True

        return {
            "date": ind["date"] or date,
            "indicators": ind["indicators"],
            "indicator_labels": INDICATOR_LABELS,
            "sectors": sectors,
            "concept_groups": concept_groups,
            "zt_by_concept": zt_by_concept,
            "zt_by_lianban": zt_by_lianban,
            "longhu_list": lh_list,
            "lianban_html": lr.get("html", "") if lr else "",
        }

    def dump(self, date=None, filepath=None):
        """导出今日复盘全景 JSON。"""
        if date is None:
            fd = fupan_date()
            date = fd.get("date", "")

        result = {
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "date": date,
            "review": self.review(date),
            "sentiment": sentiment_curve(),
            "strength": sector_strength(date=date),
            "yidong": fupan_yidong(date=date),
            "plate_rotate": plate_rotate(),
            "longtou_dates": longtou_dates(),
            "lianban_chart": lianban_chart(),
            "lianban_range": lianban_range(date=date),
        }
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            print(f"已导出到 {filepath}")
        return result

    @staticmethod
    def print(data):
        """格式化打印复盘报告。"""
        date = data["date"]
        ind = data.get("indicators", {})
        labels = data.get("indicator_labels", {})

        print(f"\n  {'='*60}")
        print(f"  每日复盘 — {date}")
        print(f"  {'='*60}")

        core_keys = ["ZT", "DT", "LBGD", "FB", "KQXY", "HSLN", "ZHULI", "ZTBX", "LBBX", "SZ", "XD"]
        print(f"\n  [市场指标]")
        for k in core_keys:
            v = ind.get(k)
            label = labels.get(k, k)
            if v is not None:
                unit = "%" if k in ("FB", "KQXY", "ZTBX", "LBBX") else "亿" if k in ("HSLN", "ZHULI") else ""
                print(f"    {label}: {v}{unit}")

        jinji_keys = ["jinji_1_2", "jinji_2_3", "jinji_3_4", "jinji_lianban"]
        print(f"\n  [晋级率]")
        for k in jinji_keys:
            v = ind.get(k)
            label = labels.get(k, k)
            if v is not None:
                print(f"    {label}: {v}%")

        sectors = data.get("sectors", [])
        print(f"\n  [板块强度 TOP10]")
        for i, s in enumerate(sectors[:10]):
            print(f"    {i+1:>2}. {s['name']}  {s['strength']}")

        cgs = data.get("concept_groups", [])
        print(f"\n  [概念分组·板块启动理由] {len(cgs)} 组")
        for cg in cgs[:8]:
            print(f"    {cg['concept']}（{cg['stock_count']}只涨停）")
            if cg.get('reason'):
                print(f"      → {cg['reason']}")

        zt_concept = data.get("zt_by_concept", [])
        zt_lianban = data.get("zt_by_lianban", [])
        print(f"\n  [涨停复盘（按概念）] {len(zt_concept)} 只")
        for z in zt_concept[:8]:
            print(f"    {z['name']}({z['code']})  {z['chg_pct']}  {z['ban_type']}  "
                  f"{z['ban_count']}  封单{z['seal_amount']}  换手{z['turn_rate']}  {z['longhu']}")

        print(f"\n  [涨停复盘（按连板）] {len(zt_lianban)} 只")
        for z in zt_lianban[:8]:
            lh_flag = " [龙虎榜]" if z.get("longhu_detail") else ""
            print(f"    {z['name']}({z['code']})  {z['chg_pct']}  {z['ban_type']}  "
                  f"{z['ban_count']}  L{z['lianban']}  封单{z['seal_amount']}  "
                  f"换手{z['turn_rate']}  {z['longhu']}{lh_flag}")

        longhu_list = data.get("longhu_list", [])
        print(f"\n  [龙虎榜] {len(longhu_list)} 只上榜")
        if longhu_list:
            print(f"    席位明细可调用 ReviewManager.get_seats() 或 fetch_longhu_detail(code, date)")
            for lh in longhu_list[:10]:
                print(f"    {lh['name']}({lh['code']})  {lh['chg_pct']:+.2f}%  {lh['reason']}")

        print()


# ── 向后兼容别名 ──

def daily_review(date=None):
    return ReviewManager().review(date)


def dump_review(date=None, filepath=None):
    return ReviewManager().dump(date, filepath)
