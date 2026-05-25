#!/usr/bin/env python3
"""慧策复盘分析引擎 — 板块持续性 / 情绪周期 / 连板矩阵 / 主线识别 / 复盘选股。

用法:
    from review.analytics import (
        sector_persistence, sentiment_cycle, lianban_matrix,
        mainline_identifier, review_screener,
    )

    # 板块持续性
    df = sector_persistence()

    # 情绪周期拐点
    sc = sentiment_cycle()
    inflection_dates = sc[sc["inflection"]]

    # 连板胜率矩阵
    lm = lianban_matrix()
    print(lm["matrix"])       # 晋级率矩阵
    print(lm["summary"])      # 汇总统计

    # 主线识别
    ml = mainline_identifier()

    # 复盘驱动选股
    stocks = review_screener()

    # 命令行
    python -m review.analytics                        # 板块持续性报告
    python -m review.analytics --sentiment            # 情绪周期拐点
    python -m review.analytics --lianban              # 连板胜率矩阵
    python -m review.analytics --mainline             # 主线识别
    python -m review.analytics --screener             # 复盘选股
"""

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

DB_PATH = Path(__file__).parent.parent / "data" / "quant.db"


def _conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _calc_streaks(dates):
    """计算连续出现序列。dates 已排序的日期列表。
    返回 (max_streak, streak_count, streak_lengths)。
    streak_count 结构: {1: 次数, 2: 次数, 3: 次数, 4: 次数, 5+: 次数}
    """
    if not dates:
        return 0, {}, []

    sorted_dates = sorted(set(dates))
    streaks = []
    current = [sorted_dates[0]]

    for d in sorted_dates[1:]:
        # 检查是否为相邻交易日（间隔 ≤ 4 天，覆盖周末+假期）
        from datetime import datetime, timedelta
        prev = datetime.strptime(current[-1], "%Y%m%d")
        curr = datetime.strptime(d, "%Y%m%d")
        if (curr - prev).days <= 4:
            current.append(d)
        else:
            streaks.append(len(current))
            current = [d]
    streaks.append(len(current))

    max_streak = max(streaks) if streaks else 0
    streak_count = defaultdict(int)
    for s in streaks:
        if s >= 5:
            streak_count["5+"] += 1
        else:
            streak_count[s] += 1

    return max_streak, dict(streak_count), streaks


def sector_persistence(start_date="20250101", end_date="20991231", min_days=3):
    """板块持续性分析。

    返回 DataFrame，列:
        concept    — 概念名称
        days       — 出现总天数
        max_streak — 最长连续天数
        avg_stocks — 平均涨停股数
        streak_1   — 单日游次数
        streak_2   — 2日轮动次数
        streak_3   — 3日热点次数
        streak_4   — 4日热点次数
        streak_5plus— 5+日主线次数
        last_seen  — 最近出现日期
        active_5d  — 近5日是否活跃
        active_10d — 近10日是否活跃
        active_20d — 近20日是否活跃
        persistence_score — 持续性综合评分
        category   — 主线/热点/轮动/一日游
    """
    c = _conn()
    rows = c.execute("""
        SELECT concept, trade_date, stock_count, stocks_json, reason
        FROM review_concept_groups
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, (start_date, end_date)).fetchall()
    c.close()

    if not rows:
        return pd.DataFrame()

    # 按概念聚合
    concept_data = defaultdict(lambda: {
        "dates": [],
        "total_stocks": 0,
        "appearances": 0,
        "reasons": [],
        "stocks_map": {},  # date -> stock_names
    })

    for r in rows:
        concept = r["concept"]
        d = concept_data[concept]
        d["dates"].append(r["trade_date"])
        d["total_stocks"] += r["stock_count"]
        d["appearances"] += 1
        if r["reason"]:
            d["reasons"].append(r["reason"])
        try:
            stocks = json.loads(r["stocks_json"])
            d["stocks_map"][r["trade_date"]] = [s.get("name", "") for s in stocks]
        except (json.JSONDecodeError, TypeError):
            pass

    # 计算指标
    results = []
    for concept, data in concept_data.items():
        max_streak, streak_count, all_streaks = _calc_streaks(data["dates"])
        days = data["appearances"]
        avg_stocks = round(data["total_stocks"] / days, 1) if days > 0 else 0
        last_seen = max(data["dates"]) if data["dates"] else ""

        # 分类
        if max_streak >= 5:
            category = "主线"
        elif max_streak >= 3:
            category = "热点"
        elif max_streak >= 2:
            category = "轮动"
        else:
            category = "一日游"

        # 综合评分: 天数权重 0.3 + 最长连续权重 0.4 + 平均涨停数归一化 0.3
        # 先用原始值，后续归一化
        persistence_score = days * 0.3 + max_streak * 0.4 + avg_stocks * 0.3

        results.append({
            "concept": concept,
            "days": days,
            "max_streak": max_streak,
            "avg_stocks": avg_stocks,
            "streak_1": streak_count.get(1, 0),
            "streak_2": streak_count.get(2, 0),
            "streak_3": streak_count.get(3, 0),
            "streak_4": streak_count.get(4, 0),
            "streak_5plus": streak_count.get("5+", 0),
            "last_seen": last_seen,
            "persistence_score": round(persistence_score, 1),
            "category": category,
            # 保留原始数据
            "_dates": data["dates"],
            "_reasons": data["reasons"][:5],
            "_sample_stocks": list(data["stocks_map"].values())[:3] if data["stocks_map"] else [],
        })

    df = pd.DataFrame(results)
    df = df.sort_values("persistence_score", ascending=False).reset_index(drop=True)

    # 计算活跃度
    from datetime import datetime, timedelta
    today = datetime.now()
    ref = {
        "active_5d": 5,
        "active_10d": 10,
        "active_20d": 20,
    }
    for col, days_back in ref.items():
        cutoff = (today - timedelta(days=days_back)).strftime("%Y%m%d")
        df[col] = df["last_seen"].apply(lambda x: x >= cutoff)

    # 过滤出现天数太少的噪声
    df = df[df["days"] >= min_days]

    return df


def persistence_report(df=None):
    """生成板块持续性文字报告。"""
    if df is None:
        df = sector_persistence()

    if df.empty:
        return "暂无数据"

    lines = []
    lines.append("=" * 64)
    lines.append("  板块持续性分析报告")
    lines.append("=" * 64)

    # 概览统计
    total = len(df)
    main_line = len(df[df["category"] == "主线"])
    hot = len(df[df["category"] == "热点"])
    rotate = len(df[df["category"] == "轮动"])
    one_day = len(df[df["category"] == "一日游"])

    lines.append(f"\n总计 {total} 个概念板块（出现 ≥3 天）")
    lines.append(f"  主线(5+连续): {main_line:4d} 个  ({main_line/total*100:5.1f}%)")
    lines.append(f"  热点(3-4连续): {hot:4d} 个  ({hot/total*100:5.1f}%)")
    lines.append(f"  轮动(2连续):   {rotate:4d} 个  ({rotate/total*100:5.1f}%)")
    lines.append(f"  一日游:        {one_day:4d} 个  ({one_day/total*100:5.1f}%)")

    # TOP 主线
    lines.append(f"\n{'─' * 64}")
    lines.append("TOP 15 持续性最强板块")
    lines.append(f"{'概念':<14s} {'天数':>5s} {'最长连续':>8s} {'均涨停':>6s} {'分类':>6s} {'末次':>10s}")
    lines.append("-" * 64)
    for _, row in df.head(15).iterrows():
        lines.append(
            f"{row['concept']:<14s} {int(row['days']):5d} "
            f"{int(row['max_streak']):8d} {row['avg_stocks']:6.1f} "
            f"{row['category']:>6s} {row['last_seen']:>10s}"
        )

    # 近期活跃的主线
    lines.append(f"\n{'─' * 64}")
    lines.append("近10日活跃板块（按持续性排序）")
    active_10 = df[df["active_10d"]].head(12)
    lines.append(f"{'概念':<14s} {'天数':>5s} {'最长连续':>8s} {'均涨停':>6s} {'分类':>6s}")
    lines.append("-" * 48)
    for _, row in active_10.iterrows():
        lines.append(
            f"{row['concept']:<14s} {int(row['days']):5d} "
            f"{int(row['max_streak']):8d} {row['avg_stocks']:6.1f} "
            f"{row['category']:>6s}"
        )

    # 持续性分布
    lines.append(f"\n{'─' * 64}")
    lines.append("持续性分布")
    bins = [
        ("一日游 (max=1)", len(df[df["max_streak"] == 1])),
        ("轮动 (max=2)", len(df[df["max_streak"] == 2])),
        ("热点 (max=3-4)", len(df[df["max_streak"].isin([3, 4])])),
        ("主线 (max≥5)", len(df[df["max_streak"] >= 5])),
    ]
    for label, count in bins:
        bar = "█" * (count // max(1, total // 40))
        lines.append(f"  {label:<20s} {count:4d} {bar}")

    lines.append("=" * 64)
    return "\n".join(lines)


def top_persistent_concepts(n=15, active_only=False):
    """快捷查询：持续性最强的 N 个板块。"""
    df = sector_persistence()
    if active_only:
        df = df[df["active_20d"]]
    return df.head(n)


def concept_timeline(concept, start_date="20250101", end_date="20991231"):
    """查询单个概念的活跃时间线。返回 DataFrame。

    每行: trade_date, stock_count, stocks, reason
    """
    c = _conn()
    rows = c.execute("""
        SELECT trade_date, stock_count, stocks_json, reason
        FROM review_concept_groups
        WHERE concept = ? AND trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, (concept, start_date, end_date)).fetchall()
    c.close()

    data = []
    for r in rows:
        try:
            stocks = json.loads(r["stocks_json"])
            names = [s.get("name", "") for s in stocks]
        except (json.JSONDecodeError, TypeError):
            names = []
        data.append({
            "trade_date": r["trade_date"],
            "stock_count": r["stock_count"],
            "stocks": names,
            "reason": r["reason"] or "",
        })
    return pd.DataFrame(data) if data else pd.DataFrame()


def streak_heatmap(start_date="20250101", end_date="20991231", top_n=20):
    """生成板块持续性热力图数据。

    返回 {concepts: [...], dates: [...], matrix: [[counts]]}
    matrix[i][j] 表示第 i 个概念在第 j 天有涨停的股票数。
    """
    df = sector_persistence(start_date, end_date, min_days=5)
    top = df.head(top_n)

    # 收集所有相关日期
    all_dates = set()
    concept_dates = {}
    for _, row in top.iterrows():
        dates = set(row["_dates"])
        all_dates.update(dates)
        concept_dates[row["concept"]] = dates

    sorted_dates = sorted(all_dates)
    sorted_concepts = list(top["concept"])

    # 构建矩阵
    c = _conn()
    matrix = []
    for concept in sorted_concepts:
        row_data = []
        date_set = concept_dates[concept]
        for d in sorted_dates:
            if d in date_set:
                r = c.execute("""
                    SELECT stock_count FROM review_concept_groups
                    WHERE concept = ? AND trade_date = ?
                """, (concept, d)).fetchone()
                row_data.append(r["stock_count"] if r else 0)
            else:
                row_data.append(0)
        matrix.append(row_data)
    c.close()

    return {
        "concepts": sorted_concepts,
        "dates": sorted_dates,
        "matrix": matrix,
    }


# ═══════════════════════════════════════════
# 情绪周期拐点识别
# ═══════════════════════════════════════════

def sentiment_cycle(start_date="20250101", end_date="20991231"):
    """情绪周期拐点识别 — 基于 38 个市场指标识别冰点/退潮/修复/高潮。

    返回 DataFrame，列:
        trade_date      — 交易日
        ZT, DT, FB, QX  — 原始指标
        zt_ma5, dt_ma5  — 5日均值
        composite        — 综合情绪 Z-score
        phase            — 冰点/退潮/修复/高潮
        inflection       — 是否为拐点
        inflection_type  — 顶(高潮转退潮) / 底(冰点转修复)
    """
    c = _conn()
    rows = c.execute("""
        SELECT trade_date, data_json FROM review_indicators
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, (start_date, end_date)).fetchall()
    c.close()

    if not rows:
        return pd.DataFrame()

    records = []
    for r in rows:
        ind = json.loads(r["data_json"])
        records.append({
            "trade_date": r["trade_date"],
            "ZT": ind.get("ZT", 0),
            "DT": ind.get("DT", 0),
            "FB": ind.get("FB", 0),
            "PB": ind.get("PB", 0),
            "QX": ind.get("QX", 50),
            "SZ": ind.get("SZ", 0),
            "XD": ind.get("XD", 0),
            "LBGD": ind.get("LBGD", 0),
            "ZBLN": ind.get("ZBLN", 0),
            "ZHULI": ind.get("ZHULI", 0),
            "jinji_1_2": ind.get("jinji_1_2"),
            "jinji_2_3": ind.get("jinji_2_3"),
            "jinji_3_4": ind.get("jinji_3_4"),
            "yizi_zt": ind.get("yizi_zt", 0),
            "yizi_dt": ind.get("yizi_dt", 0),
            "lh_amount": ind.get("lh_amount", 0),
            "risk_val": ind.get("risk_val", 0),
        })

    df = pd.DataFrame(records)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")

    # 计算均值和标准差（滚动窗口）
    for col in ["ZT", "DT", "FB", "QX"]:
        df[f"{col}_ma5"] = df[col].rolling(5, min_periods=1).mean()
        df[f"{col}_std"] = df[col].rolling(20, min_periods=5).std()
        mean = df[col].mean()
        std = df[col].std()
        df[f"{col}_z"] = (df[col] - mean) / std if std > 0 else 0

    # 综合情绪分（加权 Z-score）
    # ZT+(正相关) DT-(负相关) FB+(正相关) QX+(正相关) jinji_1_2+(正相关)
    df["jinji_1_2_v"] = pd.to_numeric(df["jinji_1_2"], errors="coerce").fillna(0)
    jinji_mean = df["jinji_1_2_v"].mean()
    jinji_std = df["jinji_1_2_v"].std()
    df["jinji_z"] = (df["jinji_1_2_v"] - jinji_mean) / jinji_std if jinji_std > 0 else 0

    df["composite"] = (
        df["ZT_z"] * 0.3
        - df["DT_z"] * 0.2
        + df["FB_z"] * 0.25
        + df["QX_z"] * 0.15
        + df["jinji_z"] * 0.1
    )

    # 分类阶段
    def _phase(c):
        if c >= 1.0:
            return "高潮"
        elif c >= 0.3:
            return "修复偏暖"
        elif c > -0.3:
            return "修复"
        elif c > -1.0:
            return "退潮"
        else:
            return "冰点"

    df["phase"] = df["composite"].apply(_phase)

    # 识别拐点
    phases = df["phase"].tolist()
    inflection = [False] * len(phases)
    inflection_type = [""] * len(phases)

    for i in range(1, len(phases)):
        prev, curr = phases[i - 1], phases[i]
        if prev != curr:
            inflection[i] = True
            # 判断方向
            phase_order = {"冰点": 0, "退潮": 1, "修复": 2, "修复偏暖": 3, "高潮": 4}
            if phase_order.get(curr, 2) > phase_order.get(prev, 2):
                inflection_type[i] = "底"  # 情绪转好
            else:
                inflection_type[i] = "顶"  # 情绪转差

    df["inflection"] = inflection
    df["inflection_type"] = inflection_type

    return df


def sentiment_summary(sc=None):
    """生成情绪周期摘要。"""
    if sc is None:
        sc = sentiment_cycle()

    if sc.empty:
        return "暂无数据"

    current = sc.iloc[-1]
    inflection_dates = sc[sc["inflection"]]

    lines = [
        "=" * 56,
        "  情绪周期拐点识别",
        "=" * 56,
        f"\n当前情绪: {current['phase']}  (composite={current['composite']:.2f})",
        f"涨停: {int(current['ZT'])}  跌停: {int(current['DT'])}  封板率: {current['FB']:.1f}%",
        f"1进2晋级: {current['jinji_1_2']}%  连板高度: {int(current['LBGD'])}",
        f"\n历史拐点 ({len(inflection_dates)} 次):",
    ]

    recent = inflection_dates.tail(10)
    for _, row in recent.iterrows():
        arrow = "↑" if row["inflection_type"] == "底" else "↓"
        lines.append(
            f"  {row['trade_date'].strftime('%Y-%m-%d')} {arrow} {row['phase']} "
            f"(ZT:{int(row['ZT'])}, DT:{int(row['DT'])}, FB:{row['FB']:.0f}%)"
        )

    # 阶段统计
    phase_counts = sc["phase"].value_counts()
    lines.append(f"\n阶段分布 (共{len(sc)}天):")
    for p in ["高潮", "修复偏暖", "修复", "退潮", "冰点"]:
        cnt = phase_counts.get(p, 0)
        bar = "█" * (cnt // 2)
        lines.append(f"  {p:<8s} {cnt:4d}天 {bar}")

    lines.append("=" * 56)
    return "\n".join(lines)


# ═══════════════════════════════════════════
# 连板胜率矩阵
# ═══════════════════════════════════════════

def lianban_matrix(start_date="20250101", end_date="20991231"):
    """连板胜率矩阵 — 计算各连板高度的晋级率和分歧板率。

    返回 dict:
        matrix      — DataFrame，行=起始连板, 列=[总数, 晋级, 晋级率, 分歧板数, 分歧板率]
        timeline    — DataFrame，每日各层级晋级率
        current     — dict，当前最近的各层级晋级率
    """
    c = _conn()

    # 获取所有涨停记录，按日期排序
    rows = c.execute("""
        SELECT trade_date, code, name, lianban, ban_type
        FROM review_zt_stocks
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date, lianban DESC
    """, (start_date, end_date)).fetchall()
    c.close()

    if not rows:
        return {"matrix": pd.DataFrame(), "timeline": pd.DataFrame(), "current": {}}

    # 按日期分组
    date_stocks = defaultdict(list)  # date -> [{code, lianban, ban_type}]
    for r in rows:
        date_stocks[r["trade_date"]].append({
            "code": r["code"],
            "lianban": r["lianban"],
            "ban_type": r["ban_type"],
        })

    sorted_dates = sorted(date_stocks.keys())

    # 计算每日晋级率
    daily_rates = []
    for i in range(len(sorted_dates) - 1):
        d1, d2 = sorted_dates[i], sorted_dates[i + 1]
        stocks_d1 = {s["code"]: s for s in date_stocks[d1]}
        stocks_d2 = {s["code"]: s for s in date_stocks[d2]}

        # 各层级统计
        for lb in range(1, 8):
            d1_at_level = [s for s in date_stocks[d1] if s["lianban"] == lb]
            if not d1_at_level:
                continue

            total = len(d1_at_level)
            # 晋级: d2 中出现且连板数 = lb+1
            advanced = sum(
                1 for s in d1_at_level
                if s["code"] in stocks_d2 and stocks_d2[s["code"]]["lianban"] == lb + 1
            )
            # 分歧板: d1 当天 ban_type 含"分歧"（涨停质量差）
            zhaban = sum(
                1 for s in d1_at_level
                if "分歧" in s["ban_type"]
            )

            daily_rates.append({
                "trade_date": d2,
                "level": lb,
                "total": total,
                "advanced": advanced,
                "rate": round(advanced / total * 100, 1),
                "zhaban": zhaban,
                "zhaban_rate": round(zhaban / total * 100, 1),
            })

    dr_df = pd.DataFrame(daily_rates) if daily_rates else pd.DataFrame()

    # 汇总矩阵
    if not dr_df.empty:
        matrix_rows = []
        for lb in range(1, 8):
            level_data = dr_df[dr_df["level"] == lb]
            if level_data.empty:
                continue
            total = level_data["total"].sum()
            advanced = level_data["advanced"].sum()
            zhaban_cnt = level_data["zhaban"].sum()
            matrix_rows.append({
                "连板": f"{lb}→{lb+1}",
                "样本数": total,
                "晋级数": advanced,
                "晋级率": round(advanced / total * 100, 1),
                "分歧板数": zhaban_cnt,
                "分歧板率": round(zhaban_cnt / total * 100, 1),
            })

        # 7+ 合并
        high_data = dr_df[dr_df["level"] >= 7]
        if not high_data.empty:
            total = high_data["total"].sum()
            advanced = high_data["advanced"].sum()
            zhaban_cnt = high_data["zhaban"].sum()
            matrix_rows.append({
                "连板": "7+→8+",
                "样本数": total,
                "晋级数": advanced,
                "晋级率": round(advanced / total * 100, 1) if total > 0 else 0,
                "分歧板数": zhaban_cnt,
                "分歧板率": round(zhaban_cnt / total * 100, 1) if total > 0 else 0,
            })

        matrix = pd.DataFrame(matrix_rows)
    else:
        matrix = pd.DataFrame()

    # 最近一天的各层级晋级率
    current = {}
    if not dr_df.empty:
        latest_date = dr_df["trade_date"].max()
        latest = dr_df[dr_df["trade_date"] == latest_date]
        for _, row in latest.iterrows():
            current[f"{int(row['level'])}进{int(row['level'])+1}"] = f"{row['rate']:.1f}%"

    return {
        "matrix": matrix,
        "timeline": dr_df,
        "current": current,
    }


def lianban_report(lm=None):
    """生成连板胜率文字报告。"""
    if lm is None:
        lm = lianban_matrix()

    matrix = lm["matrix"]
    if matrix.empty:
        return "暂无连板数据"

    lines = [
        "=" * 64,
        "  连板胜率矩阵",
        "=" * 64,
        f"\n{'晋级路径':<12s} {'样本数':>6s} {'晋级数':>6s} {'晋级率':>8s} {'分歧板率':>8s}",
        "-" * 44,
    ]

    for _, row in matrix.iterrows():
        rate_bar = "█" * int(row["晋级率"] / 5)
        lines.append(
            f"{row['连板']:<12s} {int(row['样本数']):6d} {int(row['晋级数']):6d} "
            f"{row['晋级率']:7.1f}% {rate_bar}"
        )

    lines.append("-" * 44)

    # 当前各层级
    if lm["current"]:
        lines.append(f"\n最新晋级率: {lm['current']}")

    lines.append("=" * 64)
    return "\n".join(lines)


# ═══════════════════════════════════════════
# 主线识别器
# ═══════════════════════════════════════════

def mainline_identifier(lookback=10):
    """自动识别当前市场主线板块。

    综合以下因素打分:
        - 近期活跃度（最近 lookback 天内出现天数）
        - 涨停强度（平均涨停股数）
        - 趋势（涨停数是增加还是减少）
        - 持续性历史（最长连续天数）
        - 高度（板块内最高连板）

    返回 DataFrame，列:
        concept       — 概念名称
        recent_days   — 近期出现天数
        avg_zt        — 近期日均涨停数
        trend         — 扩张/收缩/持平
        total_score   — 综合得分
        confidence    — 主线置信度
        label         — 主线/热点支线/轮动/观望
    """
    c = _conn()

    # 获取最近 N 天有数据的所有概念分组
    today = datetime.now()
    cutoff = (today - timedelta(days=30)).strftime("%Y%m%d")

    rows = c.execute("""
        SELECT concept, trade_date, stock_count, stocks_json
        FROM review_concept_groups
        WHERE trade_date >= ?
        ORDER BY trade_date
    """, (cutoff,)).fetchall()
    c.close()

    if not rows:
        return pd.DataFrame()

    # 组织数据
    concept_data = defaultdict(lambda: {"dates": [], "stocks_by_date": {}, "total_stocks": 0})
    all_dates = sorted(set(r["trade_date"] for r in rows))
    recent_cutoff = all_dates[-lookback] if len(all_dates) >= lookback else all_dates[0]

    for r in rows:
        concept = r["concept"]
        concept_data[concept]["dates"].append(r["trade_date"])
        concept_data[concept]["total_stocks"] += r["stock_count"]
        concept_data[concept]["stocks_by_date"][r["trade_date"]] = r["stock_count"]

    # 计算得分
    results = []
    for concept, data in concept_data.items():
        recent_dates = [d for d in data["dates"] if d >= recent_cutoff]
        recent_days = len(recent_dates)
        if recent_days == 0:
            continue

        # 近期日均涨停
        recent_stocks = [data["stocks_by_date"][d] for d in recent_dates]
        avg_zt = np.mean(recent_stocks)

        # 趋势：比较前后半段
        half = max(1, len(recent_dates) // 2)
        first_half_avg = np.mean(recent_stocks[:half])
        second_half_avg = np.mean(recent_stocks[half:])
        if second_half_avg > first_half_avg * 1.15:
            trend = "扩张"
            trend_score = 1.5
        elif second_half_avg < first_half_avg * 0.85:
            trend = "收缩"
            trend_score = 0.7
        else:
            trend = "持平"
            trend_score = 1.0

        # 连续性：最近是否连续出现
        sorted_recent = sorted(recent_dates)
        consecutive = 1
        for i in range(len(sorted_recent) - 1, 0, -1):
            d1 = datetime.strptime(sorted_recent[i - 1], "%Y%m%d")
            d2 = datetime.strptime(sorted_recent[i], "%Y%m%d")
            if (d2 - d1).days <= 4:
                consecutive += 1
            else:
                break

        # 综合得分
        score = (
            recent_days / lookback * 40  # 出场率 0-40分
            + min(avg_zt, 15) / 15 * 25  # 涨停强度 0-25分
            + trend_score * 15           # 趋势 0-15分
            + min(consecutive, 10) / 10 * 20  # 连续性 0-20分
        )

        # 置信度和标签
        if score >= 70:
            confidence = "高"
            label = "主线"
        elif score >= 50:
            confidence = "中"
            label = "热点支线"
        elif score >= 30:
            confidence = "低"
            label = "轮动"
        else:
            confidence = "观望"
            label = "观望"

        results.append({
            "concept": concept,
            "recent_days": recent_days,
            "lookback": lookback,
            "avg_zt": round(avg_zt, 1),
            "trend": trend,
            "consecutive": consecutive,
            "total_score": round(score, 1),
            "confidence": confidence,
            "label": label,
        })

    df = pd.DataFrame(results)
    if df.empty:
        return df

    df = df.sort_values("total_score", ascending=False).reset_index(drop=True)
    return df


def mainline_report(ml=None):
    """生成主线识别文字报告。"""
    if ml is None:
        ml = mainline_identifier()

    if ml.empty:
        return "暂无数据"

    lines = [
        "=" * 56,
        "  主线识别器",
        "=" * 56,
    ]

    main_lines = ml[ml["label"] == "主线"]
    hot_lines = ml[ml["label"] == "热点支线"]

    lines.append(f"\n主线 ({len(main_lines)}):")
    for _, row in main_lines.iterrows():
        lines.append(
            f"  {row['concept']:<14s} 得分{row['total_score']:5.1f}  "
            f"涨停{row['avg_zt']:4.1f}只/日  {row['trend']}"
        )

    lines.append(f"\n热点支线 ({len(hot_lines)}):")
    for _, row in hot_lines.head(8).iterrows():
        lines.append(
            f"  {row['concept']:<14s} 得分{row['total_score']:5.1f}  "
            f"涨停{row['avg_zt']:4.1f}只/日  {row['trend']}"
        )

    lines.append("=" * 56)
    return "\n".join(lines)


# ═══════════════════════════════════════════
# 复盘驱动选股
# ═══════════════════════════════════════════

def review_screener(date=None, top=30):
    """基于复盘数据多因子评分选股。

    评分因子:
        1. 板块强度 (0-25分) — 所属概念是否为主线/热点
        2. 连板位置 (0-20分) — 2-3板最优（有空间+有辨识度）
        3. 涨停质量 (0-20分) — 一字板/强板 vs 弱板/分歧板
        4. 龙虎榜加持 (0-15分) — 是否有龙虎榜数据
        5. 概念集中度 (0-20分) — 涨停股多=板块效应强

    返回 DataFrame，按总分降序。
    """
    c = _conn()

    if date is None:
        # 取最近复盘日期
        row = c.execute("SELECT MAX(trade_date) as d FROM review_zt_stocks").fetchone()
        date = row["d"] if row else datetime.now().strftime("%Y%m%d")

    # 获取当日涨停股票
    zt_rows = c.execute("""
        SELECT z.code, z.name, z.lianban, z.ban_type, z.seal_amount,
               z.volume, z.turn_rate, z.reason, z.longhu, z.concept_group
        FROM review_zt_stocks z
        WHERE z.trade_date = ?
    """, (date,)).fetchall()

    if not zt_rows:
        c.close()
        return pd.DataFrame()

    # 获取当日概念分组
    cg_rows = c.execute("""
        SELECT concept, stock_count, stocks_json
        FROM review_concept_groups
        WHERE trade_date = ?
    """, (date,)).fetchall()

    # 主线识别
    ml = mainline_identifier()
    mainline_concepts = set(ml[ml["label"].isin(["主线", "热点支线"])]["concept"].tolist())
    concept_counts = {r["concept"]: r["stock_count"] for r in cg_rows}

    # 获取近5日的个股涨停持续情况
    all_dates = c.execute("""
        SELECT DISTINCT trade_date FROM review_zt_stocks
        WHERE trade_date <= ?
        ORDER BY trade_date DESC
        LIMIT 5
    """, (date,)).fetchall()
    recent_dates = [r["trade_date"] for r in all_dates]

    c.close()

    # 评分
    results = []
    for z in zt_rows:
        concept = z["concept_group"]
        score = 0.0
        details = []

        # 1. 板块强度 (0-25)
        if concept in mainline_concepts:
            if concept in set(ml[ml["label"] == "主线"]["concept"].tolist()):
                score += 25
                details.append("主线板块+25")
            else:
                score += 18
                details.append("热点支线+18")
        else:
            score += 5
            details.append("非主线+5")

        # 2. 连板位置 (0-20)
        lb = z["lianban"] if z["lianban"] else 1
        if lb == 1:
            score += 12
            details.append("首板+12")
        elif lb == 2:
            score += 20
            details.append("二板+20")
        elif lb == 3:
            score += 18
            details.append("三板+18")
        elif lb in (4, 5):
            score += 12
            details.append(f"{lb}板+12")
        else:
            score += 5
            details.append(f"高位{lb}板+5")

        # 3. 涨停质量 (0-20)
        ban_type = z["ban_type"] or ""
        if "一字" in ban_type:
            score += 20
            details.append("一字板+20")
        elif "强" in ban_type or "T字" in ban_type:
            score += 16
            details.append("强板+16")
        elif "回封" in ban_type:
            score += 10
            details.append("回封+10")
        elif "弱" in ban_type or "分歧" in ban_type:
            score += 5
            details.append("弱板+5")
        else:
            score += 12
            details.append("普通板+12")

        # 4. 龙虎榜加持 (0-15)
        if z["longhu"] and z["longhu"] != "0":
            score += 15
            details.append("龙虎榜+15")

        # 5. 概念集中度 (0-20)
        cnt = concept_counts.get(concept, 1)
        if cnt >= 10:
            score += 20
        elif cnt >= 6:
            score += 15
        elif cnt >= 3:
            score += 10
        else:
            score += 3
        details.append(f"板块{cnt}只+{min(20, cnt*2)}")

        results.append({
            "code": z["code"],
            "name": z["name"],
            "lianban": lb,
            "ban_type": ban_type,
            "concept": concept,
            "seal_amount": z["seal_amount"] or "",
            "turn_rate": z["turn_rate"] or "",
            "has_longhu": bool(z["longhu"] and z["longhu"] != "0"),
            "score": round(score, 1),
            "details": " | ".join(details),
        })

    df = pd.DataFrame(results)
    df = df.sort_values("score", ascending=False).reset_index(drop=True)

    # 加标签
    def _tag(score):
        if score >= 80:
            return "S级"
        elif score >= 65:
            return "A级"
        elif score >= 50:
            return "B级"
        return "C级"

    df["grade"] = df["score"].apply(_tag)

    return df.head(top) if top else df


# ═══════════════════════════════════════════
# 市场宽度指标
# ═══════════════════════════════════════════

def market_breadth(start_date="20250101", end_date="20991231"):
    """市场宽度分析 — 涨跌比、新高新低、赚钱效应趋势。

    返回 dict:
        daily       — DataFrame，每日涨跌比/情绪/新高新低
        summary     — dict，汇总统计
        trend       — str，当前趋势（扩张/收敛/极端）
        signal      — str，交易信号
    """
    c = _conn()
    rows = c.execute("""
        SELECT trade_date, data_json FROM review_indicators
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, (start_date, end_date)).fetchall()
    c.close()

    if not rows:
        return {"daily": pd.DataFrame(), "summary": {}, "trend": "无数据", "signal": "无数据"}

    records = []
    for r in rows:
        ind = json.loads(r["data_json"])
        up = ind.get("SZ", 0)
        down = ind.get("XD", 0)
        zt = ind.get("ZT", 0)
        dt = ind.get("DT", 0)
        total = up + down
        records.append({
            "trade_date": r["trade_date"],
            "up_count": up,
            "down_count": down,
            "total": total,
            "up_ratio": round(up / total * 100, 1) if total > 0 else 50,
            "zt_count": zt,
            "dt_count": dt,
            "zt_dt_ratio": round(zt / max(dt, 1), 1),
            "emotion": ind.get("QX", 50),
            "market_cap_flow": ind.get("HSLN", 0),
        })

    df = pd.DataFrame(records)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")

    # 计算滚动指标
    df["up_ratio_ma5"] = df["up_ratio"].rolling(5, min_periods=1).mean()
    df["breadth_z"] = (df["up_ratio"] - df["up_ratio"].mean()) / df["up_ratio"].std()

    # 宽度状态分类
    latest = df.iloc[-1]
    breadth_z = latest["breadth_z"]

    if breadth_z >= 1.5:
        trend = "极端乐观 — 涨跌比远超均值，注意过热"
    elif breadth_z >= 0.5:
        trend = "扩张 — 赚钱效应扩散，可积极参与"
    elif breadth_z >= -0.5:
        trend = "中性 — 涨跌均衡，结构性行情"
    elif breadth_z >= -1.5:
        trend = "收敛 — 赚钱效应收窄，控制仓位"
    else:
        trend = "极端悲观 — 普跌格局，防御为主"

    # 交易信号
    if breadth_z >= 1.5 and latest["zt_count"] >= 100:
        signal = "⚠ 情绪过热 + 宽度极值 → 注意高位风险"
    elif breadth_z >= 0.5 and latest["up_ratio"] > 55:
        signal = "✅ 宽度扩张 + 赚钱效应好 → 积极做多"
    elif breadth_z <= -1.0:
        signal = "🛑 宽度极值冰点 → 等待企稳信号"
    elif breadth_z <= -0.5:
        signal = "⚠ 宽度收敛 → 控制仓位，精选个股"
    elif df["breadth_z"].iloc[-2] < -0.5 and breadth_z > -0.3:
        signal = "🔥 冰点修复信号 → 关注情绪拐点"
    else:
        signal = "➡ 中性 — 跟随主线，正常操作"

    # 汇总
    summary = {
        "latest_up_ratio": float(latest["up_ratio"]),
        "latest_zt": int(latest["zt_count"]),
        "latest_dt": int(latest["dt_count"]),
        "breadth_z": round(float(breadth_z), 2),
        "up_ratio_ma5": round(float(latest["up_ratio_ma5"]), 1),
        "market_flow": float(latest["market_cap_flow"]),
    }

    return {"daily": df, "summary": summary, "trend": trend, "signal": signal}


def market_breadth_report():
    """生成市场宽度文字报告。"""
    mb = market_breadth()
    if mb["daily"].empty:
        return "暂无数据"

    df = mb["daily"]
    s = mb["summary"]

    lines = [
        "=" * 56,
        "  市场宽度分析",
        "=" * 56,
        f"\n当前涨跌比: {s['latest_up_ratio']}%",
        f"涨跌比5日均值: {s['up_ratio_ma5']}%",
        f"宽度Z-score: {s['breadth_z']}",
        f"涨停/跌停比: {s['latest_zt']}/{s['latest_dt']}",
        f"主力资金: {s['market_flow']}亿",
        f"\n状态: {mb['trend']}",
        f"信号: {mb['signal']}",
        "",
        "近10日涨跌比变化:",
    ]

    for _, row in df.tail(10).iterrows():
        bar = "█" * int(row["up_ratio"] / 5)
        lines.append(f"  {row['trade_date'].strftime('%m-%d')} {row['up_ratio']:5.1f}% {bar}")

    lines.append("=" * 56)
    return "\n".join(lines)


# ═══════════════════════════════════════════
# 资金流向趋势分析
# ═══════════════════════════════════════════

def capital_flow_trend(start_date="20250101", end_date="20991231"):
    """板块资金流向趋势分析 — 识别资金持续流入/流出的板块。

    返回 DataFrame，列:
        concept      — 板块名称
        total_flow   — 累计资金净流入（全周期）
        recent_flow  — 近5日资金净流入
        flow_days    — 净流入天数
        out_days     — 净流出天数
        net_ratio    — 净流入天数占比
        trend        — 持续流入/流入偏多/均衡/流出偏多/持续流出
        avg_stocks   — 平均涨停数
    """
    c = _conn()

    # 获取概念分组数据（含涨停数，用于估算资金热度）
    rows = c.execute("""
        SELECT concept, trade_date, stock_count
        FROM review_concept_groups
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, (start_date, end_date)).fetchall()
    c.close()

    if not rows:
        return pd.DataFrame()

    # 组织结构
    concept_data = defaultdict(lambda: {"dates": [], "stock_counts": []})
    all_dates = sorted(set(r["trade_date"] for r in rows))

    for r in rows:
        concept_data[r["concept"]]["dates"].append(r["trade_date"])
        concept_data[r["concept"]]["stock_counts"].append(r["stock_count"])

    # 计算资金热度 = 涨停数 × 强度替代（无法直接获取资金流时用涨停数作为代理变量）
    results = []
    for concept, data in concept_data.items():
        dates = data["dates"]
        counts = data["stock_counts"]
        if len(dates) < 3:
            continue

        # 计算日均涨停变化作为"资金流"代理
        df_temp = pd.DataFrame({"date": pd.to_datetime(dates, format="%Y%m%d"), "count": counts})
        df_temp = df_temp.sort_values("date")
        df_temp["count_ma3"] = df_temp["count"].rolling(3, min_periods=1).mean()
        df_temp["flow_change"] = df_temp["count"].diff()

        # 流入/流出判断（涨停数增加=资金流入，减少=流出）
        flow_days = int((df_temp["flow_change"] > 0).sum())
        out_days = int((df_temp["flow_change"] < 0).sum())
        total_days = len(df_temp)

        # 近5日
        recent = df_temp.tail(5)
        recent_flow = int(recent["flow_change"].sum())

        net_ratio = flow_days / max(total_days, 1) * 100

        if net_ratio >= 65:
            trend = "持续流入"
        elif net_ratio >= 55:
            trend = "流入偏多"
        elif net_ratio >= 45:
            trend = "均衡"
        elif net_ratio >= 35:
            trend = "流出偏多"
        else:
            trend = "持续流出"

        results.append({
            "concept": concept,
            "total_days": total_days,
            "total_flow_proxy": int(sum(counts)),
            "recent_flow": recent_flow,
            "flow_days": flow_days,
            "out_days": out_days,
            "net_ratio": round(net_ratio, 1),
            "trend": trend,
            "avg_stocks": round(sum(counts) / total_days, 1) if total_days > 0 else 0,
            "last_count": counts[-1] if counts else 0,
        })

    df = pd.DataFrame(results)
    if df.empty:
        return df
    return df.sort_values("net_ratio", ascending=False).reset_index(drop=True)


def capital_flow_report():
    """生成资金流向文字报告。"""
    cf = capital_flow_trend()
    if cf.empty:
        return "暂无数据"

    lines = [
        "=" * 64,
        "  资金流向趋势分析（基于涨停数变化代理）",
        "=" * 64,
        f"\n{'板块':<14s} {'天数':>5s} {'均涨停':>7s} {'流入天':>6s} {'流出天':>6s} {'占比':>7s} {'趋势':<10s}",
        "-" * 64,
    ]

    for _, row in cf.head(20).iterrows():
        lines.append(
            f"{row['concept']:<14s} {int(row['total_days']):5d} "
            f"{row['avg_stocks']:7.1f} {int(row['flow_days']):6d} "
            f"{int(row['out_days']):6d} {row['net_ratio']:6.1f}% {row['trend']:<10s}"
        )

    # 流入/流出TOP
    lines.append(f"\n持续流入板块 TOP5:")
    inflow = cf[cf["trend"].isin(["持续流入", "流入偏多"])].head(5)
    for _, row in inflow.iterrows():
        lines.append(f"  {row['concept']} — {row['net_ratio']:.0f}%流入, 日均{row['avg_stocks']}只涨停")

    lines.append(f"\n持续流出板块 TOP5:")
    outflow = cf[cf["trend"].isin(["持续流出", "流出偏多"])].head(5)
    for _, row in outflow.iterrows():
        lines.append(f"  {row['concept']} — {(100-row['net_ratio']):.0f}%流出, 日均{row['avg_stocks']}只涨停")

    lines.append("=" * 64)
    return "\n".join(lines)


# ═══════════════════════════════════════════
# 概念轮动速度
# ═══════════════════════════════════════════

def concept_rotation_speed(start_date="20250101", end_date="20991231", window=5):
    """概念轮动速度分析 — 衡量市场风格切换频率。

    轮动速度快 = 每日热点概念更换频繁 = 适合短线快进快出
    轮动速度慢 = 主线持续 = 适合持股待涨

    返回 dict:
        daily       — DataFrame，每日轮动速度
        current     — float，当前轮动速度
        avg         — float，平均轮动速度
        trend       — str，加速/稳定/减速
        signal      — str，策略建议
    """
    c = _conn()
    rows = c.execute("""
        SELECT trade_date, concept FROM review_concept_groups
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, (start_date, end_date)).fetchall()
    c.close()

    if not rows:
        return {"daily": pd.DataFrame(), "current": 0, "avg": 0, "trend": "无数据", "signal": "无数据"}

    # 按日期分组
    date_concepts = defaultdict(set)
    for r in rows:
        date_concepts[r["trade_date"]].add(r["concept"])

    sorted_dates = sorted(date_concepts.keys())

    # 计算每日轮动速度 = 与前一日的概念重叠度（越低轮动越快）
    records = []
    for i, date in enumerate(sorted_dates):
        curr_set = date_concepts[date]
        if i == 0:
            overlap_pct = 100
            new_concepts = len(curr_set)
            gone_concepts = 0
        else:
            prev_set = date_concepts[sorted_dates[i - 1]]
            common = curr_set & prev_set
            overlap_pct = round(len(common) / max(len(prev_set), 1) * 100, 1)
            new_concepts = len(curr_set - prev_set)
            gone_concepts = len(prev_set - curr_set)

        rotation_speed = 100 - overlap_pct  # 0=完全持续, 100=完全轮动
        records.append({
            "trade_date": date,
            "concept_count": len(curr_set),
            "overlap_pct": overlap_pct,
            "rotation_speed": rotation_speed,
            "new_concepts": new_concepts,
            "gone_concepts": gone_concepts,
        })

    df = pd.DataFrame(records)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df["speed_ma5"] = df["rotation_speed"].rolling(window, min_periods=1).mean()

    current_speed = float(df["speed_ma5"].iloc[-1])
    avg_speed = float(df["rotation_speed"].mean())

    # 趋势判断
    if len(df) >= 5:
        recent_avg = df["speed_ma5"].tail(3).mean()
        older_avg = df["speed_ma5"].iloc[-6:-3].mean() if len(df) >= 6 else recent_avg
        if recent_avg > older_avg * 1.2:
            speed_trend = "加速轮动"
        elif recent_avg < older_avg * 0.8:
            speed_trend = "减速（主线凝聚）"
        else:
            speed_trend = "稳定"
    else:
        speed_trend = "数据不足"

    # 策略信号
    if current_speed > 70:
        signal = "⚡ 高速轮动 — 热点一日游，快进快出，不恋战"
    elif current_speed > 50:
        signal = "🔄 中速轮动 — 2-3日热点，短线操作"
    elif current_speed > 30:
        signal = "📈 低速轮动 — 主线持续，可持股待涨"
    else:
        signal = "🔒 主线锁定 — 板块持续性极强，重仓主线"

    return {
        "daily": df,
        "current": round(current_speed, 1),
        "avg": round(avg_speed, 1),
        "trend": speed_trend,
        "signal": signal,
    }


def rotation_report():
    """生成概念轮动速度文字报告。"""
    rs = concept_rotation_speed()
    if rs["daily"].empty:
        return "暂无数据"

    lines = [
        "=" * 56,
        "  概念轮动速度分析",
        "=" * 56,
        f"\n当前轮动速度: {rs['current']}%  (历史均值: {rs['avg']}%)",
        f"趋势: {rs['trend']}",
        f"信号: {rs['signal']}",
        f"\n近10日轮动变化:",
    ]

    for _, row in rs["daily"].tail(10).iterrows():
        bar = "█" * int(row["rotation_speed"] / 5)
        label = "高速" if row["rotation_speed"] > 60 else ("中速" if row["rotation_speed"] > 40 else "低速")
        lines.append(
            f"  {row['trade_date'].strftime('%m-%d')} "
            f"速度{row['rotation_speed']:5.1f}% {label:<4s} {bar}"
        )

    lines.append("=" * 56)
    return "\n".join(lines)


# ═══════════════════════════════════════════
# 封板质量分析
# ═══════════════════════════════════════════

def seal_quality_analysis(start_date="20250101", end_date="20991231"):
    """封板质量统计分析 — 各板型的出现频率和次日表现。

    返回 dict:
        matrix      — DataFrame，各板型的统计
        by_date     — DataFrame，每日封板质量分布
        summary     — dict，当前汇总
    """
    c = _conn()
    rows = c.execute("""
        SELECT trade_date, code, name, lianban, ban_type, seal_amount
        FROM review_zt_stocks
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, (start_date, end_date)).fetchall()
    c.close()

    if not rows:
        return {"matrix": pd.DataFrame(), "by_date": pd.DataFrame(), "summary": {}}

    # 分类封板类型
    def classify_seal(ban_type):
        bt = ban_type or ""
        if "一字" in bt:
            return "一字板"
        elif "T字" in bt:
            return "T字板"
        elif "回封" in bt:
            return "回封板"
        elif "分歧" in bt:
            return "分歧板"
        elif "弱" in bt:
            return "弱板"
        elif "强" in bt:
            return "强板"
        else:
            return "普通板"

    # 统计各板型
    seal_stats = defaultdict(lambda: {"count": 0, "codes": []})
    daily_seal = defaultdict(lambda: defaultdict(int))

    for r in rows:
        seal_type = classify_seal(r["ban_type"])
        seal_stats[seal_type]["count"] += 1
        seal_stats[seal_type]["codes"].append(r["code"])
        daily_seal[r["trade_date"]][seal_type] += 1

    # 矩阵
    total = sum(s["count"] for s in seal_stats.values())
    matrix_rows = []
    for seal_type, stats in sorted(seal_stats.items(), key=lambda x: x[1]["count"], reverse=True):
        matrix_rows.append({
            "封板类型": seal_type,
            "数量": stats["count"],
            "占比": round(stats["count"] / total * 100, 1) if total > 0 else 0,
        })

    matrix = pd.DataFrame(matrix_rows)

    # 每日分布
    sorted_dates = sorted(daily_seal.keys())
    daily_rows = []
    for d in sorted_dates:
        row = {"trade_date": d}
        row.update(dict(daily_seal[d]))
        daily_rows.append(row)

    by_date = pd.DataFrame(daily_rows) if daily_rows else pd.DataFrame()

    # 汇总
    latest_date = sorted_dates[-1] if sorted_dates else ""
    latest_seals = daily_seal.get(latest_date, {})
    quality_score = (
        latest_seals.get("一字板", 0) * 100
        + latest_seals.get("T字板", 0) * 80
        + latest_seals.get("强板", 0) * 60
        + latest_seals.get("回封板", 0) * 50
        + latest_seals.get("普通板", 0) * 40
        - latest_seals.get("分歧板", 0) * 20
        - latest_seals.get("弱板", 0) * 40
    )
    total_seals = sum(latest_seals.values())
    avg_quality = round(quality_score / max(total_seals, 1), 1)

    return {
        "matrix": matrix,
        "by_date": by_date,
        "summary": {
            "latest_date": latest_date,
            "total_zt": total_seals,
            "quality_score": avg_quality,
            "seal_distribution": latest_seals,
        },
    }


def seal_quality_report():
    """生成封板质量文字报告。"""
    sq = seal_quality_analysis()
    if sq["matrix"].empty:
        return "暂无数据"

    s = sq["summary"]

    lines = [
        "=" * 56,
        "  封板质量分析",
        "=" * 56,
        f"\n最近交易日: {s['latest_date']}",
        f"涨停总数: {s['total_zt']}",
        f"封板质量评分: {s['quality_score']} (越高越好)",
        f"\n封板类型分布:",
    ]

    for seal_type, count in sorted(s["seal_distribution"].items(), key=lambda x: x[1], reverse=True):
        pct = round(count / s["total_zt"] * 100, 1) if s["total_zt"] > 0 else 0
        bar = "█" * (count // max(1, s["total_zt"] // 20))
        lines.append(f"  {seal_type:<8s} {count:4d} ({pct:5.1f}%) {bar}")

    lines.append(f"\n全周期统计 ({len(sq['by_date'])}天):")
    lines.append(f"{'封板类型':<10s} {'数量':>6s} {'占比':>7s}")
    lines.append("-" * 28)
    for _, row in sq["matrix"].iterrows():
        lines.append(f"{row['封板类型']:<10s} {int(row['数量']):6d} {row['占比']:6.1f}%")

    # 质量解读
    if s["quality_score"] >= 70:
        lines.append(f"\n解读: 封板质量优秀，一字/强板占主导，市场做多意愿强")
    elif s["quality_score"] >= 50:
        lines.append(f"\n解读: 封板质量良好，主流板块封板稳固")
    elif s["quality_score"] >= 30:
        lines.append(f"\n解读: 封板质量一般，分歧较大，注意风险")
    else:
        lines.append(f"\n解读: 封板质量差，弱板/分歧板居多，慎追涨停")

    lines.append("=" * 56)
    return "\n".join(lines)


# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="慧策复盘分析引擎")
    p.add_argument("--sentiment", action="store_true", help="情绪周期拐点识别")
    p.add_argument("--lianban", action="store_true", help="连板胜率矩阵")
    p.add_argument("--mainline", action="store_true", help="主线识别器")
    p.add_argument("--screener", action="store_true", help="复盘驱动选股")
    p.add_argument("--breadth", action="store_true", help="市场宽度分析")
    p.add_argument("--flow", action="store_true", help="资金流向趋势分析")
    p.add_argument("--rotation", action="store_true", help="概念轮动速度分析")
    p.add_argument("--seal", action="store_true", help="封板质量分析")
    p.add_argument("--concept", type=str, default="", help="查询指定概念的时间线")
    p.add_argument("--top", type=int, default=20, help="显示前 N 条")
    p.add_argument("--active", action="store_true", help="仅显示近20日活跃")
    p.add_argument("--min-days", type=int, default=3, help="最少出现天数")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = p.parse_args()

    if args.sentiment:
        sc = sentiment_cycle()
        if args.json:
            out = sc.copy()
            out["trade_date"] = out["trade_date"].astype(str)
            print(out.to_json(orient="records", force_ascii=False, indent=2))
        else:
            print(sentiment_summary(sc))

    elif args.lianban:
        lm = lianban_matrix()
        if args.json:
            print(json.dumps({
                "matrix": lm["matrix"].to_dict(orient="records"),
                "current": lm["current"],
            }, ensure_ascii=False, indent=2))
        else:
            print(lianban_report(lm))

    elif args.mainline:
        ml = mainline_identifier()
        if args.json:
            print(ml.to_json(orient="records", force_ascii=False, indent=2))
        else:
            print(mainline_report(ml))

    elif args.screener:
        stocks = review_screener(top=args.top)
        if args.json:
            print(stocks.to_json(orient="records", force_ascii=False, indent=2))
        else:
            print(f"\n{'=' * 56}")
            print(f"  复盘驱动选股 (TOP {args.top})")
            print(f"{'=' * 56}")
            print(f"\n{'评级':<6s} {'代码':<8s} {'名称':<10s} {'连板':<5s} {'类型':<8s} {'概念':<14s} {'得分':>5s}")
            print("-" * 64)
            for _, row in stocks.iterrows():
                print(f"{row['grade']:<6s} {row['code']:<8s} {row['name']:<10s} "
                      f"{int(row['lianban'])}板{'':<3s} {row['ban_type']:<8s} "
                      f"{row['concept']:<14s} {row['score']:5.1f}")

    elif args.breadth:
        mb = market_breadth()
        if args.json:
            out = mb["daily"].copy()
            out["trade_date"] = out["trade_date"].astype(str)
            print(json.dumps({
                "summary": mb["summary"],
                "trend": mb["trend"],
                "signal": mb["signal"],
                "daily": out.to_dict(orient="records"),
            }, ensure_ascii=False, indent=2, default=str))
        else:
            print(market_breadth_report())

    elif args.flow:
        cf = capital_flow_trend()
        if args.json:
            print(cf.head(args.top).to_json(orient="records", force_ascii=False, indent=2))
        else:
            print(capital_flow_report())

    elif args.rotation:
        rs = concept_rotation_speed()
        if args.json:
            out = rs["daily"].copy()
            out["trade_date"] = out["trade_date"].astype(str)
            print(json.dumps({
                "current": rs["current"],
                "avg": rs["avg"],
                "trend": rs["trend"],
                "signal": rs["signal"],
            }, ensure_ascii=False, indent=2))
        else:
            print(rotation_report())

    elif args.seal:
        sq = seal_quality_analysis()
        if args.json:
            print(json.dumps({
                "matrix": sq["matrix"].to_dict(orient="records"),
                "summary": sq["summary"],
            }, ensure_ascii=False, indent=2, default=str))
        else:
            print(seal_quality_report())

    elif args.concept:
        tl = concept_timeline(args.concept)
        if tl.empty:
            print(f"未找到概念: {args.concept}")
        else:
            print(f"\n[{args.concept}] 时间线 ({len(tl)} 天)")
            for _, row in tl.iterrows():
                print(f"  {row['trade_date']} | {row['stock_count']}只 | {', '.join(row['stocks'][:5])}")
            streaks = _calc_streaks(tl["trade_date"].tolist())
            print(f"\n最长连续: {streaks[0]}天, 分布: {streaks[1]}")

    else:
        # 默认：板块持续性
        df = sector_persistence(min_days=args.min_days)
        if args.json:
            out = df.drop(columns=[c for c in df.columns if c.startswith("_")], errors="ignore")
            print(out.head(args.top).to_json(orient="records", force_ascii=False, indent=2))
        else:
            print(persistence_report(df))
