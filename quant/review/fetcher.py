#!/usr/bin/env python3
"""复盘数据抓取 — 短线侠 duanxianxia.cn API（需登录）。

覆盖"每日复盘""板块轮动""龙头高度""连板天梯"4 个页面的 9 个 API。
"""

import json
import time
import urllib.request

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

# ── 认证 ──

def _get_auth():
    try:
        from data.auth import DuanxianxiaAuth
    except ModuleNotFoundError:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from data.auth import DuanxianxiaAuth
    auth = DuanxianxiaAuth.from_saved()
    if not auth or not auth.logged_in:
        auth = DuanxianxiaAuth()
        auth.login("18507507885", "qq781898")
    return auth


def fetch(endpoint, data=None, auth=None):
    if auth is None:
        auth = _get_auth()
    path = ENDPOINTS.get(endpoint, endpoint)
    return auth.post(path, data or {})


# ── 指标标签 ──

INDICATOR_LABELS = {
    "QX": "市场情绪",
    "KQXY": "赚钱效应(%)",
    "LBGD": "连板高度",
    "CIGAO": "词高",
    "CYBGD": "创业板高度",
    "ZT": "涨停数量",
    "DT": "跌停数量",
    "SZ": "上涨家数",
    "XD": "下跌家数",
    "FB": "封板率(%)",
    "ths_qx": "同花顺情绪",
    "PB": "排版比",
    "ZTBX": "涨停表现(%)",
    "LBBX": "连板表现(%)",
    "PBBX": "排版表现",
    "LB": "连板数量",
    "HSLN": "成交额(亿)",
    "ZHULI": "主力净流入(亿)",
    "ZTLN": "涨停力度",
    "ZBLN": "炸板力度",
    "CYB": "创业板涨停",
    "ZHUBAN": "主板涨停",
    "risk_val": "风险值",
    "risk_avg": "风险均值",
    "yizi_zt": "一字涨停",
    "yizi_dt": "一字跌停",
    "yizi_fd": "一字封单",
    "lh_amount": "龙虎榜成交额",
    "lh_net_value": "龙虎榜净额",
    "jinji_1_2": "晋级1进2(%)",
    "jinji_2_3": "晋级2进3(%)",
    "jinji_3_4": "晋级3进4(%)",
    "jinji_other": "晋级其他(%)",
    "jinji_top": "晋级最高(%)",
    "jinji_lianban": "晋级连板(%)",
    "jinji": "晋级详情",
}

# ── 涨停表头 ──

ZT_COLUMNS = [
    "name", "code", "price", "chg_pct", "ban_type", "ban_count",
    "lianban", "first_seal", "last_seal", "open_count", "seal_amount",
    "volume", "turn_rate", "float_mv_real", "float_mv", "total_mv",
    "reason", "longhu",
]

# ── API 函数 ──

def fupan_date():
    return fetch("fupan_date", {"date": "", "type": "init"})


def sentiment_curve():
    return fetch("sentiment", {})


def sector_strength(date="", platetype="", platelist=""):
    return fetch("strength", {"date": date, "platetype": platetype, "platelist": platelist})


def fupan_yidong(zttype="plate", date=""):
    return fetch("yidong", {"type": zttype, "date": date})


def plate_rotate():
    return fetch("plate_rotate", {})


def longtou_dates():
    return fetch("longtou_dates", {})


def lianban_chart():
    return fetch("lianban_chart", {})


def longtou_stocks(check="", name=""):
    return fetch("/api/ltShowStock", {"check": check, "type": "concept", "name": name})


def lianban_range(date=""):
    return fetch("lianban_range", {"date": date})


# ── 结构化解析 ──

def _find_date_index(dates_map, target_date):
    if not dates_map:
        return -1
    if target_date in dates_map:
        return dates_map[target_date]
    alt1 = target_date.replace("-", "")
    if alt1 in dates_map:
        return dates_map[alt1]
    alt2 = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:8]}" if len(target_date) == 8 else target_date
    if alt2 in dates_map:
        return dates_map[alt2]
    return -1


def parse_indicators(sc_data=None, date=None):
    """从情绪曲线提取指定日市场指标。"""
    if sc_data is None:
        sc_data = sentiment_curve()
    if sc_data.get("result") != "success":
        return {"date": None, "indicators": {}, "labels": INDICATOR_LABELS}

    series = sc_data.get("series", {})
    dates_map = sc_data.get("dates", {})

    if date is None:
        aaxis = sc_data.get("Aaxis", [])
        date = aaxis[-1] if aaxis else None
    date_fmt = date if date and "-" in str(date) else f"{date[:4]}-{date[4:6]}-{date[6:8]}" if date and len(str(date)) == 8 else str(date)

    idx = _find_date_index(dates_map, date_fmt) if date_fmt else -1
    if idx < 0:
        first = list(dates_map.keys())[0] if dates_map else "?"
        last = list(dates_map.keys())[-1] if dates_map else "?"
        return {"date": None, "indicators": {}, "labels": INDICATOR_LABELS,
                "error": f"{date_fmt} 非交易日或无数据（数据覆盖: {first} ~ {last}，仅交易日）"}

    indicators = {}
    for key, s in series.items():
        if isinstance(s, dict):
            data = s.get("data", [])
        elif isinstance(s, list):
            data = s
        else:
            continue
        if not data:
            continue
        try:
            val = data[idx]
        except IndexError:
            continue
        if isinstance(val, str):
            try:
                val = float(val) if "." in val else int(val)
            except ValueError:
                pass
        indicators[key] = val

    return {"date": date_fmt, "indicators": indicators, "labels": INDICATOR_LABELS}


def parse_sector_strength(ss_data=None, date=None, top=15):
    """从板块强度数据提取当日板块排名。"""
    import re
    if ss_data is None:
        ss_data = sector_strength(date=date if date else "")
    if ss_data.get("result") != "success":
        return []

    plates_html = ss_data.get("plates", "") or ""
    raw = re.findall(r"<input[^>]*value='(\d+)'[^>]*name='plate'[^>]*>\s*([^<]+)", plates_html)

    series_list = ss_data.get("series", [])
    strength_map = {}
    for s in series_list:
        name = s.get("name", "")
        data = s.get("data", [])
        if data:
            try:
                val = float(data[-1]) if data[-1] is not None else 0
            except (ValueError, TypeError):
                val = 0
            strength_map[name] = val

    results = []
    for code, text in raw:
        m = re.match(r"(.+?)（(-?\d+)）", text.strip())
        if m:
            results.append({"code": code, "name": m.group(1), "strength": int(m.group(2))})
        else:
            results.append({"code": code, "name": text.strip(), "strength": 0})

    results.sort(key=lambda x: x["strength"], reverse=True)
    return results[:top] if top else results


def parse_yidong_rows(yidong_data=None, date=None):
    """解析涨停 HTML 为结构化行（18列全量）。"""
    import re
    if yidong_data is None:
        yidong_data = fupan_yidong(zttype="plate", date=date if date else "")

    if isinstance(yidong_data, dict):
        html = yidong_data.get("html", "") or ""
    else:
        html = str(yidong_data)

    if not html:
        return []

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
    result = []
    for row_html in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
        clean = [re.sub(r"<[^>]+>", "", t).strip() for t in tds]
        if len(clean) < len(ZT_COLUMNS):
            continue
        item = {}
        for i, key in enumerate(ZT_COLUMNS):
            val = clean[i] if i < len(clean) else ""
            if key in ("lianban", "open_count"):
                try:
                    val = int(val) if val else 0
                except ValueError:
                    pass
            item[key] = val
        result.append(item)
    return result


# ── 概念分组 ──

def parse_concept_headers(html):
    """提取概念分组标题（板块启动理由）。"""
    import re
    if not html:
        return []

    pattern = r"<div class='list-group-item ztitem'[^>]*?>.*?<b[^>]*?>(.*?)</b>(.*?)</span>.*?<div class='ztnum'[^>]*?>.*?<div[^>]*?>(\d+)</div>"
    matches = re.findall(pattern, html, re.DOTALL)

    results = []
    for i, m in enumerate(matches):
        concept = m[0].strip()
        reason = m[1].strip()
        if reason.startswith('：') or reason.startswith(':'):
            reason = reason[1:].strip()
        results.append({
            "concept": concept,
            "reason": reason,
            "stock_count": int(m[2]),
            "table_id": i + 1,
        })
    return results


def parse_concept_with_stocks(html):
    """提取概念分组及每组股票（含板块启动理由+18列全量）。"""
    import re
    if not html:
        return []

    concepts = parse_concept_headers(html)

    table_pattern = r"<table[^>]*id='ztlist_(\d+)'[^>]*>(.*?)</table>"
    tables = re.findall(table_pattern, html, re.DOTALL)

    table_stocks = {}
    for table_id, table_html in tables:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL)
        stocks = []
        for row_html in rows:
            if '<th' in row_html or "class='explain'" in row_html:
                continue
            tds = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
            clean = [re.sub(r"<[^>]+>", "", t).strip() for t in tds]
            if len(clean) < len(ZT_COLUMNS):
                continue
            item = {}
            for i, key in enumerate(ZT_COLUMNS):
                val = clean[i] if i < len(clean) else ""
                if key in ("lianban", "open_count"):
                    try:
                        val = int(val) if val else 0
                    except ValueError:
                        pass
                item[key] = val
            stocks.append(item)
        table_stocks[int(table_id)] = stocks

    for c in concepts:
        c["stocks"] = table_stocks.get(c["table_id"], [])
    return concepts


def _extract_keywords(text):
    import re
    parts = re.split(r'[+、\n\r；;。]', text)
    keywords = []
    for p in parts:
        p = p.strip()
        p = re.sub(r'^[\d]+[）)]', '', p)
        if len(p) >= 2:
            keywords.append(p)
    return keywords


def group_zt_by_concept(stocks, sectors):
    """将涨停股按概念板块分组。"""
    from collections import defaultdict, Counter

    sector_keywords = {}
    for s in sectors:
        name = s['name']
        if len(name) >= 2:
            sector_keywords[name] = s['strength']

    sector_stocks = defaultdict(list)
    for stock in stocks:
        reason = stock.get('reason', '')
        name = stock.get('name', '')
        search_text = f"{reason} {name}"
        reason_keywords = _extract_keywords(reason)

        best_sector = None
        best_score = 0
        for sec_name, sec_strength in sector_keywords.items():
            score = 0
            if sec_name in reason:
                score += 5
            if sec_name in search_text:
                score += 2
            for kw in reason_keywords:
                if sec_name in kw or kw in sec_name:
                    score += 3
                    break
            if sec_strength > 1000:
                score += 0.5
            if score > best_score:
                best_score = score
                best_sector = sec_name

        if best_sector and best_score >= 2:
            sector_stocks[best_sector].append(stock)

    result = []
    for sec_name, sec_stocks in sorted(sector_stocks.items(), key=lambda x: len(x[1]), reverse=True):
        all_keywords = []
        for s in sec_stocks:
            all_keywords.extend(_extract_keywords(s.get('reason', '')))

        kw_counter = Counter(all_keywords)
        stop_words = {'公司', '产品', '业务', '应用', '市场', '客户', '目前', '预计',
                      '已实现', '可用于', '主要', '相关', '该产品', '其中'}
        top_kw = [(k, c) for k, c in kw_counter.most_common(15)
                  if k not in stop_words and len(k) >= 2]

        sec_info = next((s for s in sectors if s['name'] == sec_name), None)
        strength = sec_info['strength'] if sec_info else 0

        result.append({
            "sector_name": sec_name,
            "strength": strength,
            "stock_count": len(sec_stocks),
            "stocks": sec_stocks,
            "top_keywords": top_kw[:8],
            "summary": " + ".join([k for k, _ in top_kw[:5]]),
        })

    return result
