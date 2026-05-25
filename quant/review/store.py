#!/usr/bin/env python3
"""复盘数据持久化 — SQLite 存储 + 历史查询。

用法:
    from review.store import save_review, query_indicators, backfill
    save_review("20260522")                    # 存一天
    df = query_indicators("20260101", "20260522")  # 查时间序列
    backfill()                                 # 回填全部历史
"""

import json
import time
import sqlite3
from pathlib import Path

from review import ReviewManager

DB_PATH = Path(__file__).parent.parent / "data" / "quant.db"


def _conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def init_review_db():
    """创建复盘相关表。"""
    c = _conn()
    c.executescript("""
        -- 每日市场指标（38个指标，一行一天）
        CREATE TABLE IF NOT EXISTS review_indicators (
            trade_date   TEXT PRIMARY KEY,
            data_json    TEXT NOT NULL,   -- {"ZT":115, "DT":5, ...}
            saved_at     TEXT
        );

        -- 每日板块强度
        CREATE TABLE IF NOT EXISTS review_sectors (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date   TEXT NOT NULL,
            code         TEXT NOT NULL,
            name         TEXT NOT NULL,
            strength     INTEGER DEFAULT 0,
            UNIQUE(trade_date, code)
        );
        CREATE INDEX IF NOT EXISTS idx_rs_date ON review_sectors(trade_date);
        CREATE INDEX IF NOT EXISTS idx_rs_name ON review_sectors(name);

        -- 每日涨停股票
        CREATE TABLE IF NOT EXISTS review_zt_stocks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date   TEXT NOT NULL,
            code         TEXT NOT NULL,
            name         TEXT,
            price        REAL,
            chg_pct      TEXT,
            ban_type     TEXT,
            ban_count    TEXT,
            lianban      INTEGER DEFAULT 1,
            seal_amount  TEXT,
            volume       TEXT,
            turn_rate    TEXT,
            reason       TEXT,
            longhu       TEXT,
            concept_group TEXT,
            UNIQUE(trade_date, code)
        );
        CREATE INDEX IF NOT EXISTS idx_zt_date ON review_zt_stocks(trade_date);
        CREATE INDEX IF NOT EXISTS idx_zt_lianban ON review_zt_stocks(trade_date, lianban);

        -- 每日龙虎榜
        CREATE TABLE IF NOT EXISTS review_longhu (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date   TEXT NOT NULL,
            code         TEXT NOT NULL,
            name         TEXT,
            chg_pct      REAL,
            amount       REAL,
            reason       TEXT,
            UNIQUE(trade_date, code)
        );
        CREATE INDEX IF NOT EXISTS idx_lh_date ON review_longhu(trade_date);

        -- 每日概念分组
        CREATE TABLE IF NOT EXISTS review_concept_groups (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date   TEXT NOT NULL,
            concept      TEXT NOT NULL,
            reason       TEXT,
            stock_count  INTEGER DEFAULT 0,
            stocks_json  TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_cg_date ON review_concept_groups(trade_date);
    """)
    c.commit()
    c.close()


def save_review(date=None, dry_run=False):
    """保存指定日复盘数据到 SQLite。失败时抛出异常，不写入脏数据。

    dry_run=True 时只校验不写入，返回 (is_valid, warnings)。
    """
    from loguru import logger as _log

    rm = ReviewManager()
    data = rm.review(date)
    if data.get("error"):
        raise ValueError(f"复盘数据不可用: {data['error']}")

    # ── 数据完整性校验 ──
    warnings = []
    trade_date_raw = data.get("date", "")
    if not trade_date_raw:
        raise ValueError("API 返回数据缺少日期字段")

    trade_date = trade_date_raw.replace("-", "")

    indicators = data.get("indicators", {})
    if not indicators or "ZT" not in indicators:
        warnings.append("市场指标缺失 ZT 字段")
    if "FB" not in indicators:
        warnings.append("市场指标缺失 FB 字段")

    sectors = data.get("sectors", [])
    if not sectors:
        warnings.append("板块强度数据为空")

    zt_stocks = data.get("zt_by_concept", [])
    concept_groups = data.get("concept_groups", [])
    if not zt_stocks and not concept_groups:
        warnings.append("涨停股票和概念分组均为空")

    # 校验涨停股的必需字段
    bad_zt = 0
    for z in zt_stocks:
        if not z.get("code") or not z.get("name"):
            bad_zt += 1
    if bad_zt > 0:
        warnings.append(f"{bad_zt} 条涨停记录缺少代码/名称")

    # 校验概念分组的股票
    bad_cg = 0
    for cg in concept_groups:
        if not cg.get("concept"):
            bad_cg += 1
    if bad_cg > 0:
        warnings.append(f"{bad_cg} 个概念分组缺少概念名称")

    longhu_list = data.get("longhu_list", [])

    if warnings:
        _log.warning(f"[{trade_date}] 数据质量警告: {'; '.join(warnings)}")

    if dry_run:
        c = _conn()
        c.close()
        return len(warnings) == 0, warnings

    # ── 写入数据库 ──
    saved_at = time.strftime("%Y-%m-%d %H:%M:%S")
    c = _conn()

    try:
        # 1. 市场指标
        ind_json = json.dumps(indicators, ensure_ascii=False)
        c.execute("""
            INSERT OR REPLACE INTO review_indicators (trade_date, data_json, saved_at)
            VALUES (?, ?, ?)
        """, (trade_date, ind_json, saved_at))

        # 2. 板块强度
        sector_count = 0
        for s in sectors:
            code = s.get("code", "")
            name = s.get("name", "")
            if not code and not name:
                continue  # 跳过无效行
            c.execute("""
                INSERT OR REPLACE INTO review_sectors (trade_date, code, name, strength)
                VALUES (?, ?, ?, ?)
            """, (trade_date, code, name, s.get("strength", 0)))
            sector_count += 1

        # 3. 涨停股票（含概念分组标记）
        concept_map = {}
        for cg in concept_groups:
            for stk in cg.get("stocks", []):
                code = stk.get("code", "")
                if code:
                    concept_map[code] = cg.get("concept", "")

        zt_count = 0
        for z in zt_stocks:
            code = z.get("code", "")
            name = z.get("name", "")
            if not code or not name:
                continue  # 跳过无效行
            c.execute("""
                INSERT OR REPLACE INTO review_zt_stocks
                (trade_date, code, name, price, chg_pct, ban_type, ban_count, lianban,
                 seal_amount, volume, turn_rate, reason, longhu, concept_group)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_date, code, name,
                float(z.get("price", 0)) if z.get("price") else 0,
                z.get("chg_pct", ""), z.get("ban_type", ""), z.get("ban_count", ""),
                int(z.get("lianban", 0)) if isinstance(z.get("lianban"), (int, float)) else 0,
                z.get("seal_amount", ""), z.get("volume", ""), z.get("turn_rate", ""),
                z.get("reason", ""), z.get("longhu", ""),
                concept_map.get(code, ""),
            ))
            zt_count += 1

        # 4. 龙虎榜
        lh_count = 0
        for lh in longhu_list:
            code = lh.get("code", "")
            if not code:
                continue
            c.execute("""
                INSERT OR REPLACE INTO review_longhu
                (trade_date, code, name, chg_pct, amount, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                trade_date, code, lh.get("name", ""),
                lh.get("chg_pct", 0), lh.get("amount", 0), lh.get("reason", ""),
            ))
            lh_count += 1

        # 5. 概念分组
        cg_count = 0
        for cg in concept_groups:
            concept = cg.get("concept", "")
            if not concept:
                continue
            stocks_json = json.dumps([{
                "code": s.get("code"), "name": s.get("name"),
                "ban_count": s.get("ban_count"), "lianban": s.get("lianban"),
            } for s in cg.get("stocks", [])], ensure_ascii=False)
            c.execute("""
                INSERT INTO review_concept_groups (trade_date, concept, reason, stock_count, stocks_json)
                VALUES (?, ?, ?, ?, ?)
            """, (trade_date, concept, cg.get("reason", ""),
                  cg.get("stock_count", 0), stocks_json))
            cg_count += 1

        c.commit()

        _log.info(
            f"[{trade_date}] 入库: 指标{len(indicators)}项, "
            f"板块{sector_count}, 涨停{zt_count}, 龙虎榜{lh_count}, 概念{cg_count}"
            + (f" (警告: {'; '.join(warnings)})" if warnings else "")
        )

    except Exception:
        c.rollback()
        c.close()
        raise

    c.close()
    return trade_date


# ═══════════════════════════════════════════
# 查询函数
# ═══════════════════════════════════════════

def query_indicators(start_date, end_date, fields=None):
    """查询市场指标时间序列。返回 [{trade_date, ZT, DT, ...}, ...]"""
    import pandas as pd
    c = _conn()
    rows = c.execute("""
        SELECT trade_date, data_json FROM review_indicators
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, (start_date, end_date)).fetchall()
    c.close()

    results = []
    for r in rows:
        item = {"trade_date": r["trade_date"]}
        indicators = json.loads(r["data_json"])
        if fields:
            for f in fields:
                item[f] = indicators.get(f)
        else:
            item.update(indicators)
        results.append(item)

    return pd.DataFrame(results) if results else pd.DataFrame()


def query_sector_trend(name, start_date, end_date):
    """查询板块强度走势。返回 DataFrame"""
    import pandas as pd
    c = _conn()
    rows = c.execute("""
        SELECT trade_date, strength FROM review_sectors
        WHERE name = ? AND trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, (name, start_date, end_date)).fetchall()
    c.close()
    return pd.DataFrame(rows, columns=["trade_date", "strength"]) if rows else pd.DataFrame()


def query_lianban_stats(start_date, end_date):
    """统计连板晋级率。返回 {date: {total, l1, l2, l3, l4plus}}"""
    c = _conn()
    rows = c.execute("""
        SELECT trade_date, lianban, COUNT(*) as cnt
        FROM review_zt_stocks
        WHERE trade_date >= ? AND trade_date <= ?
        GROUP BY trade_date, lianban
        ORDER BY trade_date, lianban
    """, (start_date, end_date)).fetchall()
    c.close()

    from collections import defaultdict
    stats = defaultdict(lambda: {"total": 0, "l1": 0, "l2": 0, "l3": 0, "l4plus": 0})
    for r in rows:
        d = r["trade_date"]
        lb = r["lianban"]
        cnt = r["cnt"]
        stats[d]["total"] += cnt
        if lb == 1:
            stats[d]["l1"] = cnt
        elif lb == 2:
            stats[d]["l2"] = cnt
        elif lb == 3:
            stats[d]["l3"] = cnt
        elif lb >= 4:
            stats[d]["l4plus"] += cnt
    return dict(stats)


def query_zt_by_concept(start_date, end_date, top=5):
    """统计概念板块涨停频次。返回 [{concept, days, total_zt, avg_zt}, ...]"""
    c = _conn()
    rows = c.execute("""
        SELECT concept_group, trade_date, COUNT(*) as cnt
        FROM review_zt_stocks
        WHERE trade_date >= ? AND trade_date <= ? AND concept_group != ''
        GROUP BY concept_group, trade_date
    """, (start_date, end_date)).fetchall()
    c.close()

    from collections import defaultdict
    concept_stats = defaultdict(lambda: {"days": 0, "total_zt": 0})
    for r in rows:
        cg = r["concept_group"]
        concept_stats[cg]["days"] += 1
        concept_stats[cg]["total_zt"] += r["cnt"]

    results = [
        {"concept": k, "days": v["days"], "total_zt": v["total_zt"],
         "avg_zt": round(v["total_zt"] / v["days"], 1)}
        for k, v in sorted(concept_stats.items(), key=lambda x: x[1]["total_zt"], reverse=True)
    ]
    return results[:top] if top else results


def backfill(start_date="20240102", end_date=None, sleep=0.5):
    """回填历史复盘数据。"""
    from review.fetcher import sentiment_curve
    if end_date is None:
        end_date = time.strftime("%Y%m%d")

    print("[backfill] 获取可用日期...")
    sc = sentiment_curve()
    dates_map = sc.get("dates", {})
    if not dates_map:
        print("[backfill] 无日期数据")
        return 0

    available = sorted(dates_map.keys())
    targets = [d for d in available if start_date <= d <= end_date]
    print(f"[backfill] 可用 {len(available)} 天, 目标 {len(targets)} 天")

    saved = 0
    for i, date_str in enumerate(targets):
        try:
            print(f"[backfill] {date_str} ({i+1}/{len(targets)})...", end=" ")
            save_review(date_str)
            print("OK")
            saved += 1
            time.sleep(sleep)
        except Exception as e:
            print(f"SKIP: {e}")
            time.sleep(0.1)

    print(f"[backfill] 完成: 保存 {saved}/{len(targets)} 天")
    return saved


# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="复盘数据持久化")
    p.add_argument("--init", action="store_true", help="初始化表结构")
    p.add_argument("--save", default="", help="保存指定日期 (YYYYMMDD)")
    p.add_argument("--backfill", action="store_true", help="回填全部历史")
    p.add_argument("--stats", action="store_true", help="显示数据统计")
    args = p.parse_args()

    if args.init:
        init_review_db()
        print("复盘表初始化完成")

    if args.save:
        init_review_db()
        trade_date = save_review(args.save)
        print(f"保存完成: {trade_date}")

    if args.backfill:
        init_review_db()
        saved = backfill()
        print(f"回填完成: {saved} 天")

    if args.stats:
        c = _conn()
        tables = ["review_indicators", "review_sectors", "review_zt_stocks",
                   "review_longhu", "review_concept_groups"]
        for t in tables:
            try:
                row = c.execute(f"SELECT COUNT(*) as n FROM {t}").fetchone()
                print(f"  {t}: {row['n']} 条")
            except:
                print(f"  {t}: 表不存在")
        c.close()
