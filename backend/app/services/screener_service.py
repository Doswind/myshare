"""选股分析 v2 —— 基于真实数据的主力资金 × 价格位置双榜

数据来源（均为已有真实数据，不触发抓取）：
- fund_holding：主力持仓明细（最新报告期 vs 上一报告期 → 加减仓）
- fund：基金业绩/规模/评级（基金质量）
- stock_kline_daily：日 K（价格位置/趋势）
- stock：名称/行业

产出两榜：
- 进场榜（主力加仓/新进）、退场榜（主力减仓/退出），各取综合排序 Top 20。
- 只分析「同时具备 ≥2 报告期持仓 且 有近 1 年 K 线」的股票。
"""
from __future__ import annotations

import logging
import statistics
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.fund import Fund
from app.models.holding import FundHolding
from app.models.kline import StockKlineDaily
from app.models.stock import Stock

logger = logging.getLogger(__name__)

# ---------- 调参常量 ----------
ADJUST = "qfq"
MIN_BARS = 120            # 至少 120 个交易日才算「有近 1 年 K 线」
TOP_N = 20               # 每榜取前 20
ENRICH_N = 60            # 排序后先富化前 N 只（补 K 线），再筛出有 K 线的 Top 20
_CACHE_TTL = 300         # 榜单缓存 5 分钟
_cache: dict = {"ts": 0.0, "data": None}


# ---------- K 线因子 ----------
def _mean(xs) -> Optional[float]:
    return sum(xs) / len(xs) if xs else None


def _pct_rank(seq, value) -> float:
    """value 在 seq 中的百分位（0-100）"""
    if not seq:
        return 0.0
    return round(sum(1 for x in seq if x <= value) / len(seq) * 100, 1)


def _rsi(closes, period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 1)


def _ma_dir(closes, period: int) -> str:
    """MA 方向：比较当前 MA 与 5 日前 MA"""
    if len(closes) < period + 5:
        return "—"
    now = _mean(closes[-period:])
    prev = _mean(closes[-period - 5:-5])
    if now is None or prev is None or prev == 0:
        return "—"
    chg = (now - prev) / prev
    if chg > 0.005:
        return "上涨"
    if chg < -0.005:
        return "下跌"
    return "平"


def compute_kline_factors(db: Session, code: str) -> Optional[dict]:
    """从 stock_kline_daily 计算价格位置/趋势因子；数据不足返回 None"""
    rows = (
        db.query(StockKlineDaily.close, StockKlineDaily.volume)
        .filter(StockKlineDaily.code == code, StockKlineDaily.adjust == ADJUST)
        .order_by(StockKlineDaily.trade_date.asc())
        .all()
    )
    closes = [float(r.close) for r in rows if r.close is not None]
    vols = [float(r.volume) for r in rows if r.volume is not None]
    if len(closes) < MIN_BARS:
        return None

    last = closes[-1]
    w1 = closes[-250:]
    w3 = closes[-750:]
    ma20 = _mean(closes[-20:])
    ma60 = _mean(closes[-60:]) if len(closes) >= 60 else _mean(closes)
    std60 = statistics.pstdev(closes[-60:]) if len(closes) >= 60 else statistics.pstdev(closes)
    std20 = statistics.pstdev(closes[-20:])
    upper = (ma20 or last) + 2 * std20
    lower = (ma20 or last) - 2 * std20
    boll_pos = round((last - lower) / (upper - lower) * 100, 1) if upper > lower else 50.0

    # 连续下跌天数
    cd = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] < closes[i - 1]:
            cd += 1
        else:
            break

    vol_ratio = round(vols[-1] / (_mean(vols[-20:]) or vols[-1]), 2) if len(vols) >= 20 else None
    ret_20d = round((last / closes[-21] - 1) * 100, 1) if len(closes) >= 21 else None
    ret_60d = round((last / closes[-61] - 1) * 100, 1) if len(closes) >= 61 else None

    return {
        "latest_price": round(last, 2),
        "factors": {
            "pct_rank_1y": _pct_rank(w1, last),
            "pct_rank_3y": _pct_rank(w3, last),
            "drawdown_1y": round((last / max(w1) - 1) * 100, 1),
            "vs_ma60_z": round((last - ma60) / std60, 2) if std60 else 0.0,
            "rsi_14": _rsi(closes) or 0.0,
            "boll_pos": boll_pos,
            "consecutive_down": cd,
            "volume_ratio_20d": vol_ratio if vol_ratio is not None else 0.0,
        },
        "trend": {
            "ma20_dir": _ma_dir(closes, 20),
            "ma60_dir": _ma_dir(closes, 60),
            "ma250_dir": _ma_dir(closes, 250),
            "ret_20d": ret_20d if ret_20d is not None else 0.0,
            "ret_60d": ret_60d if ret_60d is not None else 0.0,
        },
    }


# ---------- 主力资金动向（fund_holding 季度对比） ----------
def _report_dates(db: Session) -> list[str]:
    """全部报告期，降序"""
    return [
        d for (d,) in db.query(FundHolding.report_date)
        .distinct().order_by(FundHolding.report_date.desc()).all()
        if d
    ]


def _fund_ret_map(db: Session) -> dict:
    """fund_code -> (ret_1y, scale_yi, name, rating)"""
    out = {}
    for f in db.query(Fund.code, Fund.name, Fund.ret_1y, Fund.scale_yi, Fund.rating).all():
        out[f.code] = {
            "name": f.name, "ret_1y": f.ret_1y, "scale_yi": f.scale_yi, "rating": f.rating,
        }
    return out


def compute_all_capital(db: Session, r1: str, r0: Optional[str]) -> dict:
    """批量计算每只股票在最新报告期 r1 相对上一期 r0 的主力资金动向。

    返回 {code: capital_dict}，capital_dict 含 fund_count/total_mv_yi/mv_change_pct_qoq/
    funds_add/cut/new/exit/avg_fund_ret_1y/smart_money_index/stock_name。
    """
    fund_info = _fund_ret_map(db)

    # 最新期：stock -> {fund_code: mv(万元)}
    r1_map: dict = {}
    r1_name: dict = {}
    for h in db.query(FundHolding.stock_code, FundHolding.fund_code,
                      FundHolding.market_value, FundHolding.stock_name)\
               .filter(FundHolding.report_date == r1).all():
        r1_map.setdefault(h.stock_code, {})[h.fund_code] = h.market_value or 0.0
        if h.stock_name:
            r1_name.setdefault(h.stock_code, h.stock_name)

    # 上一期：stock -> {fund_code: mv}
    r0_map: dict = {}
    if r0:
        for h in db.query(FundHolding.stock_code, FundHolding.fund_code, FundHolding.market_value)\
                   .filter(FundHolding.report_date == r0).all():
            r0_map.setdefault(h.stock_code, {})[h.fund_code] = h.market_value or 0.0

    result: dict = {}
    for code, funds_now in r1_map.items():
        funds_prev = r0_map.get(code, {})
        total_now = sum(funds_now.values())
        total_prev = sum(funds_prev.values())
        funds_add = funds_cut = funds_new = 0
        for fc, mv in funds_now.items():
            prev = funds_prev.get(fc)
            if prev is None:
                funds_new += 1
            elif mv > prev:
                funds_add += 1
            elif mv < prev:
                funds_cut += 1
        funds_exit = sum(1 for fc in funds_prev if fc not in funds_now)

        rets = [fund_info.get(fc, {}).get("ret_1y") for fc in funds_now]
        rets = [r for r in rets if r is not None]
        avg_ret = round(statistics.median(rets), 1) if rets else 0.0
        win = round(sum(1 for r in rets if r > 0) / len(rets), 2) if rets else 0.0

        if total_prev > 0:
            mv_chg = round((total_now - total_prev) / total_prev * 100, 1)
        elif total_now > 0:
            mv_chg = None  # 全为新进（无上期基数）
        else:
            mv_chg = 0.0

        result[code] = {
            "stock_name": r1_name.get(code, code),
            "fund_count": len(funds_now),
            "total_mv_yi": round(total_now / 1e4, 2),
            "mv_change_pct_qoq": mv_chg,
            "funds_add": funds_add,
            "funds_cut": funds_cut,
            "funds_new": funds_new,
            "funds_exit": funds_exit,
            "avg_fund_ret_1y": avg_ret,
            "smart_money_index": win,
        }
    return result


# ---------- 方向判定 / 排序分 / 一句话理由 ----------
def _direction(cap: dict) -> Optional[str]:
    mv = cap["mv_change_pct_qoq"]
    base = 100.0 if mv is None else mv
    net = (cap["funds_add"] + cap["funds_new"]) - (cap["funds_cut"] + cap["funds_exit"])
    signal = base + net * 2
    if signal > 0:
        return "in"
    if signal < 0:
        return "out"
    return None


def _capital_score(cap: dict, direction: str) -> float:
    mv = cap["mv_change_pct_qoq"]
    base = 100.0 if mv is None else mv
    if direction == "in":
        return (min(base, 200)
                + (cap["funds_add"] + cap["funds_new"]) * 3
                + cap["avg_fund_ret_1y"] * 0.3
                + cap["smart_money_index"] * 10)
    # out：减仓越猛越靠前
    return (min(-base, 200)
            + (cap["funds_cut"] + cap["funds_exit"]) * 3)


def _pos_label(pct: float) -> str:
    if pct < 25:
        return "低"
    if pct < 50:
        return "中"
    if pct < 75:
        return "偏高"
    return "高"


def _build_reason(name: str, code: str, direction: str, cap: dict, kf: Optional[dict]) -> str:
    parts = [f"{name} {code} |"]
    if kf:
        pct = kf["factors"]["pct_rank_1y"]
        parts.append(f"近1年价格处于 {pct:.0f}% {_pos_label(pct)}位，")
    mv = cap["mv_change_pct_qoq"]
    n = cap["fund_count"]
    if direction == "in":
        if mv is None:
            parts.append(f"上季度 {cap['funds_new']} 只主力基金新进建仓")
        else:
            extra = f"（新进 {cap['funds_new']} 只）" if cap["funds_new"] else ""
            parts.append(f"上季度 {n} 只主力基金合计加仓 {mv:+.0f}%{extra}")
        win_cnt = round(cap["smart_money_index"] * n)
        if win_cnt:
            parts.append(f"，其中 {win_cnt} 只近1年跑赢（中位收益 {cap['avg_fund_ret_1y']:+.0f}%）")
    else:
        chg = "" if mv is None else f" {mv:+.0f}%"
        extra = f"（退出 {cap['funds_exit']} 只）" if cap["funds_exit"] else ""
        parts.append(f"上季度 {n} 只主力基金合计减仓{chg}{extra}")
    return "".join(parts) + "。"


# ---------- 上下文缓存 ----------
def _stock_info_map(db: Session, codes: list) -> dict:
    out: dict = {}
    if not codes:
        return out
    for s in db.query(Stock.code, Stock.name, Stock.industry_name)\
               .filter(Stock.code.in_(codes)).all():
        out[s.code] = {"name": s.name, "industry": s.industry_name or ""}
    return out


def _get_context(db: Session) -> dict:
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < _CACHE_TTL:
        return _cache["data"]
    dates = _report_dates(db)
    r1 = dates[0] if dates else None
    r0 = dates[1] if len(dates) >= 2 else None
    caps = compute_all_capital(db, r1, r0) if r1 else {}
    ctx = {"dates": dates, "r1": r1, "r0": r0, "caps": caps}
    _cache["data"] = ctx
    _cache["ts"] = now
    return ctx


def invalidate_cache() -> None:
    _cache["data"] = None
    _cache["ts"] = 0.0


# ---------- 公共 API ----------
def get_industries(db: Optional[Session] = None) -> list:
    own = db is None
    if own:
        db = SessionLocal()
    try:
        ctx = _get_context(db)
        codes = list(ctx["caps"].keys())
        info = _stock_info_map(db, codes)
        seen = []
        for c in codes:
            ind = info.get(c, {}).get("industry")
            if ind and ind not in seen:
                seen.append(ind)
        return sorted(seen)
    finally:
        if own:
            db.close()


def get_holders(db: Optional[Session], code: str):
    own = db is None
    if own:
        db = SessionLocal()
    try:
        ctx = _get_context(db)
        r1 = ctx["r1"]
        if not r1:
            return []
        fund_info = _fund_ret_map(db)
        rows = db.query(FundHolding).filter(
            FundHolding.report_date == r1, FundHolding.stock_code == code,
        ).all()
        items = []
        for h in rows:
            fi = fund_info.get(h.fund_code, {})
            items.append({
                "fund_code": h.fund_code,
                "fund_name": fi.get("name") or h.fund_code,
                "scale_yi": round(fi.get("scale_yi") or 0.0, 0),
                "ret_1y": round(fi.get("ret_1y") or 0.0, 1),
                "ratio_net": round(h.ratio_net or 0.0, 1),
                "market_value_wan": round(h.market_value or 0.0, 0),
            })
        items.sort(key=lambda x: x["market_value_wan"], reverse=True)
        return items
    finally:
        if own:
            db.close()


def get_boards(db: Optional[Session] = None) -> dict:
    """两榜：进场 / 退场，各 Top 20。仅含数据齐全（有 ≥2 报告期 + 近 1 年 K 线）的股票。"""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        ctx = _get_context(db)
        r1, r0, caps = ctx["r1"], ctx["r0"], ctx["caps"]
        if not r1:
            return {"in": [], "out": [], "report_dates": [], "data_as_of": None,
                    "note": "暂无持仓数据，请先抓取基金持仓。"}
        if not r0:
            return {"in": [], "out": [], "report_dates": ctx["dates"][:1], "data_as_of": r1,
                    "note": "仅有一个报告期，无法计算加减仓；两榜需至少两个季度的持仓数据（下季度抓取积累后可用）。"}

        buckets: dict = {"in": [], "out": []}
        for code, cap in caps.items():
            d = _direction(cap)
            if d:
                buckets[d].append((code, cap, _capital_score(cap, d)))

        def finalize(side: list, direction: str) -> list:
            side.sort(key=lambda t: t[2], reverse=True)
            picked = []
            for code, cap, cscore in side[:ENRICH_N]:
                kf = compute_kline_factors(db, code)
                if kf is None:
                    continue  # 无 K 线 → 数据不齐，剔除
                pct = kf["factors"]["pct_rank_1y"]
                final = cscore + ((60 - pct) if direction == "in" else (pct - 40)) * 0.5
                picked.append((code, cap, kf, final))
                if len(picked) >= TOP_N:
                    break
            picked.sort(key=lambda t: t[3], reverse=True)
            return picked[:TOP_N]

        in_picked = finalize(buckets["in"], "in")
        out_picked = finalize(buckets["out"], "out")
        info = _stock_info_map(db, [c for c, _, _, _ in in_picked + out_picked])

        def to_item(code, cap, kf, direction):
            name = info.get(code, {}).get("name") or cap["stock_name"]
            industry = info.get(code, {}).get("industry", "")
            return {
                "code": code, "name": name, "industry": industry, "direction": direction,
                "reason": _build_reason(name, code, direction, cap, kf),
                "fund_count": cap["fund_count"],
                "mv_change_pct_qoq": cap["mv_change_pct_qoq"],
                "funds_add": cap["funds_add"], "funds_cut": cap["funds_cut"],
                "funds_new": cap["funds_new"], "funds_exit": cap["funds_exit"],
                "avg_fund_ret_1y": cap["avg_fund_ret_1y"],
                "smart_money_index": cap["smart_money_index"],
                "pct_rank_1y": kf["factors"]["pct_rank_1y"],
                "latest_price": kf["latest_price"],
            }

        return {
            "in": [to_item(c, cap, kf, "in") for c, cap, kf, _ in in_picked],
            "out": [to_item(c, cap, kf, "out") for c, cap, kf, _ in out_picked],
            "report_dates": ctx["dates"][:2],
            "data_as_of": r1,
            "note": None,
        }
    finally:
        if own:
            db.close()


_ZERO_FACTORS = {
    "pct_rank_1y": 0.0, "pct_rank_3y": 0.0, "drawdown_1y": 0.0, "vs_ma60_z": 0.0,
    "rsi_14": 0.0, "boll_pos": 0.0, "consecutive_down": 0, "volume_ratio_20d": 0.0,
}
_ZERO_TREND = {
    "ma20_dir": "—", "ma60_dir": "—", "ma250_dir": "—", "ret_20d": 0.0, "ret_60d": 0.0,
}


def get_factors(db: Optional[Session], code: str):
    """单只完整因子（供 FactorPanel / AI prompt）。无任何真实数据时返回 None。"""
    own = db is None
    if own:
        db = SessionLocal()
    try:
        ctx = _get_context(db)
        cap = ctx["caps"].get(code)
        kf = compute_kline_factors(db, code)
        if cap is None and kf is None:
            return None
        info = _stock_info_map(db, [code]).get(code, {})
        name = info.get("name") or (cap or {}).get("stock_name") or code
        industry = info.get("industry", "")
        direction = _direction(cap) if cap else None
        capital = {
            "fund_count": (cap or {}).get("fund_count", 0),
            "total_mv_yi": (cap or {}).get("total_mv_yi", 0.0),
            "mv_change_pct_qoq": (cap or {}).get("mv_change_pct_qoq", 0.0),
            "avg_fund_ret_1y": (cap or {}).get("avg_fund_ret_1y", 0.0),
            "smart_money_index": (cap or {}).get("smart_money_index", 0.0),
            "funds_add": (cap or {}).get("funds_add", 0),
            "funds_cut": (cap or {}).get("funds_cut", 0),
            "funds_new": (cap or {}).get("funds_new", 0),
            "funds_exit": (cap or {}).get("funds_exit", 0),
        }
        return {
            "code": code, "name": name, "industry": industry,
            "latest_price": kf["latest_price"] if kf else None,
            "market_cap_wan_yi": None,
            "factors": kf["factors"] if kf else dict(_ZERO_FACTORS),
            "capital": capital,
            "valuation": {"pe_ttm": None, "pe_pct_rank_3y": None, "pb": None},
            "trend": kf["trend"] if kf else dict(_ZERO_TREND),
            "direction": direction,
            "reason": _build_reason(name, code, direction, cap, kf) if (cap and direction) else None,
            "data_as_of": ctx["r1"],
        }
    finally:
        if own:
            db.close()
