"""日 K 历史行情服务

核心逻辑：
- 抓取：按 holdings_pool 遍历，调 AKShare，按 tracking 表决定 full/incremental
- 写入：UPSERT 主表 + UPDATE tracking 游标
- 查询：主表 daily/按 period 聚合
- 失败：tenacity 重试 → consecutive_failures 累加 → 5 次 paused
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import select, and_, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.database import SessionLocal
from app.models.kline import StockKlineDaily, StockKlineTracking
from app.models.stock import Stock
from app.scrapers.market_data import MarketDataClient
from app.services.holdings_pool import get_holdings_pool

logger = logging.getLogger(__name__)


# ---------- 调参常量 ----------
PER_STOCK_DELAY_SEC = 0.4          # 单只间隔（限流）
BATCH_SIZE = 50                    # 每批股票数
BATCH_PAUSE_SEC = 5                # 批间隔（让东财喘口气）
HISTORY_YEARS = 6                  # 全量跨度
MAX_CONSECUTIVE_FAILURES = 5       # 连续失败阈值（达到则 paused）
ADJUST_DEFAULT = "qfq"              # 仅前复权


# ---------- 工具 ----------
def _today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _in_kline_window(now: Optional[datetime] = None) -> bool:
    """判断当前是否在 A 股交易时段 09:30–15:00（含午休，粗粒度即可）"""
    from datetime import datetime as _dt
    t = (now or _dt.now()).time()
    from datetime import time as _time
    return _time(9, 30) <= t <= _time(15, 0)


def _is_trading_day(now: Optional[datetime] = None) -> bool:
    """A 股交易日判断（懒加载 chinese_calendar，库不覆盖的远期降级为周末判断）"""
    from datetime import datetime as _dt
    target = (now or _dt.now()).date()
    try:
        from chinese_calendar import is_workday
        return bool(is_workday(target))
    except (NotImplementedError, ValueError, ImportError):
        return target.weekday() < 5


def _df_to_dicts(df: pd.DataFrame) -> list[dict]:
    """AKShare DataFrame → 行 dict 列表（NaN → None，时间戳 → ISO）"""
    if df is None or df.empty:
        return []
    df = df.where(pd.notnull(df), None)
    records = df.to_dict("records")
    for r in records:
        if "日期" in r and hasattr(r["日期"], "isoformat"):
            r["日期"] = r["日期"].strftime("%Y-%m-%d")
    return records


def _code(s: object) -> str:
    text = str(s).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6)


# ---------- 抓取（含重试） ----------
# 单独重试装饰器：网络/解析错误时重试；4xx/参数错误立即抛
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, ValueError)),
    reraise=True,
)
def _fetch_history(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """调用 AKShare 抓单只股票的历史日 K（前复权）"""
    client = MarketDataClient(cache_dir=settings.db_path.replace("fund_analyzer.db", "kline_cache"))
    try:
        df = client.get_stock_history(
            stock_code=code,
            start_date=start_date,
            end_date=end_date,
            period="daily",
            adjust=ADJUST_DEFAULT,
        )
    except Exception as e:
        logger.warning("[kline] fetch %s %s→%s failed: %s", code, start_date, end_date, e)
        raise
    if df is None or df.empty:
        return pd.DataFrame()
    return df


# ---------- 单只抓取+入库 ----------
def _upsert_bars(db: Session, code: str, bars: list[dict], source: str = "akshare") -> int:
    """批量 UPSERT 单只股票的 bars，返回写入行数（去重后）"""
    if not bars:
        return 0
    now = _now_iso()
    rows = []
    for b in bars:
        rows.append({
            "代码": code,
            "日期": b.get("日期"),
            "复权": ADJUST_DEFAULT,
            "开盘": b.get("开盘"),
            "最高": b.get("最高"),
            "最低": b.get("最低"),
            "收盘": b.get("收盘"),
            "成交量": b.get("成交量"),
            "成交额": b.get("成交额"),
            "振幅": b.get("振幅"),
            "涨跌幅": b.get("涨跌幅"),
            "涨跌额": b.get("涨跌额"),
            "换手率": b.get("换手率"),
            "数据源": source,
            "抓取时间": now,
        })

    stmt = sqlite_insert(StockKlineDaily).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["代码", "日期", "复权"],
        set_={
            "开盘": stmt.excluded.开盘,
            "最高": stmt.excluded.最高,
            "最低": stmt.excluded.最低,
            "收盘": stmt.excluded.收盘,
            "成交量": stmt.excluded.成交量,
            "成交额": stmt.excluded.成交额,
            "振幅": stmt.excluded.振幅,
            "涨跌幅": stmt.excluded.涨跌幅,
            "涨跌额": stmt.excluded.涨跌额,
            "换手率": stmt.excluded.换手率,
            "数据源": stmt.excluded.数据源,
            "抓取时间": stmt.excluded.抓取时间,
        },
    )
    db.execute(stmt)
    return len(rows)


def _get_or_create_tracking(db: Session, code: str) -> StockKlineTracking:
    row = db.query(StockKlineTracking).filter(StockKlineTracking.code == code).first()
    if row:
        return row
    row = StockKlineTracking(code=code)
    db.add(row)
    db.flush()
    return row


def _set_tracking_success(db: Session, code: str, last_trade_date: str, bars_count: int) -> None:
    row = _get_or_create_tracking(db, code)
    row.last_trade_date = last_trade_date
    row.last_attempt_at = _now_iso()
    row.consecutive_failures = 0
    row.paused = False
    row.paused_reason = None
    row.total_bars = (row.total_bars or 0) + bars_count
    db.flush()


def _set_tracking_failure(db: Session, code: str, reason: str = "fetch_failed") -> bool:
    """记录失败，必要时 paused。返回是否触发 paused"""
    row = _get_or_create_tracking(db, code)
    row.last_attempt_at = _now_iso()
    row.consecutive_failures = (row.consecutive_failures or 0) + 1
    triggered_paused = False
    if row.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        row.paused = True
        row.paused_reason = "max_failures"
        triggered_paused = True
    db.flush()
    return triggered_paused


def _is_paused(db: Session, code: str) -> bool:
    row = db.query(StockKlineTracking).filter(StockKlineTracking.code == code).first()
    return bool(row and row.paused)


def fetch_and_store_one(
    code: str,
    db: Optional[Session] = None,
) -> dict:
    """抓取并入库单只股票的 K 线（增量）

    有 last_trade_date 游标时按游标增量抓；无游标（新股票）时自动抓 HISTORY_YEARS 年。
    """
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        code = _code(code)
        # 检查暂停状态
        if _is_paused(db, code):
            return {"code": code, "status": "paused", "bars": 0}

        # 决定抓取区间
        tracking = db.query(StockKlineTracking).filter(StockKlineTracking.code == code).first()
        today = _today_str()
        if tracking is None or not tracking.last_trade_date:
            # 首次：抓满 HISTORY_YEARS 年
            start = (datetime.utcnow() - timedelta(days=365 * HISTORY_YEARS)).strftime("%Y%m%d")
            end = today.replace("-", "")
        else:
            # 增量：含 last_trade_date 当天 → UPSERT 覆写当日
            start = tracking.last_trade_date.replace("-", "")
            end = today.replace("-", "")

        # 调用 AKShare
        try:
            df = _fetch_history(code, start, end)
        except Exception:
            triggered = _set_tracking_failure(db, code)
            db.commit()
            return {
                "code": code,
                "status": "paused" if triggered else "failed",
                "bars": 0,
            }

        if df.empty:
            triggered = _set_tracking_failure(db, code)
            db.commit()
            return {
                "code": code,
                "status": "paused" if triggered else "empty",
                "bars": 0,
            }

        bars = _df_to_dicts(df)
        # 提取本次范围的最后一天
        last_date = bars[-1].get("日期") if bars else None

        # UPSERT 入库 + 更新 tracking
        written = _upsert_bars(db, code, bars)
        if last_date:
            _set_tracking_success(db, code, last_date, written)
        db.commit()
        return {"code": code, "status": "success", "bars": written, "last_date": last_date}
    finally:
        if own_db:
            db.close()


def fetch_and_store_all(
    db: Optional[Session] = None,
    codes: Optional[list[str]] = None,
    progress_cb=None,
) -> dict:
    """遍历池中所有股票增量抓取并入库

    每只按各自 last_trade_date 抓增量（新股票自动抓 HISTORY_YEARS 年）。
    codes：可选白名单（仅抓这些）；默认用 holdings_pool
    progress_cb(done, total, last_result)：每只完成后回调（用于前端进度展示）
    """
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        pool = codes if codes else get_holdings_pool(db)
        total = len(pool)
        if total == 0:
            return {"total": 0, "success": 0, "failed": 0, "paused": 0}

        success = 0
        failed = 0
        paused = 0
        for i, code in enumerate(pool, 1):
            # 跳过 paused 的（需管理员 unpause 复活）
            if _is_paused(db, code):
                paused += 1
                if progress_cb:
                    progress_cb(i, total, {"code": code, "status": "skipped_paused"})
                continue

            result = fetch_and_store_one(code, db)
            if result["status"] == "success":
                success += 1
            elif result["status"] == "paused":
                paused += 1
                failed += 1
            else:
                failed += 1

            if progress_cb:
                progress_cb(i, total, result)

            # 限流：单只间隔 + 每批暂停
            if i < total:
                time.sleep(PER_STOCK_DELAY_SEC)
                if i % BATCH_SIZE == 0:
                    logger.info("[kline] 批次 %d 暂停 %ds", i // BATCH_SIZE, BATCH_PAUSE_SEC)
                    time.sleep(BATCH_PAUSE_SEC)

        db.commit()
        return {"total": total, "success": success, "failed": failed, "paused": paused}
    finally:
        if own_db:
            db.close()


# ---------- 失败/复活管理 ----------
def unpause(db: Session, code: str) -> bool:
    """手动复活单只股票（清零失败计数 + 取消 paused）"""
    code = _code(code)
    row = db.query(StockKlineTracking).filter(StockKlineTracking.code == code).first()
    if not row:
        return False
    row.paused = False
    row.paused_reason = None
    row.consecutive_failures = 0
    db.commit()
    return True


def refresh_today(db: Optional[Session] = None, code: str = "") -> bool:
    """强制刷新当日 bar（K 线图打开时调用）"""
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        code = _code(code)
        # 不走 tracking，直接抓今天
        today = _today_str().replace("-", "")
        df = _fetch_history(code, today, today)
        if df.empty:
            return False
        bars = _df_to_dicts(df)
        if not bars:
            return False
        _upsert_bars(db, code, bars)
        last_date = bars[-1].get("日期")
        if last_date:
            _set_tracking_success(db, code, last_date, 0)
        db.commit()
        return True
    except Exception as e:
        logger.warning("[kline] refresh_today %s failed: %s", code, e)
        db.rollback()
        return False
    finally:
        if own_db:
            db.close()


def refresh_kline(code: str, db: Optional[Session] = None) -> dict:
    """刷新单只 K 线（供图表打开/刷新/盘中轮询调用）

    - 游标落后（last_trade_date < today）→ 先 fetch_and_store_one 补齐历史增量
      （兜底漏跑的定时任务；含今日；paused 内部跳过）
    - 交易日且在 09:30–15:00 窗口内 → refresh_today 抓当日实时 bar 覆写
    两步都 UPSERT 入库并推进游标，保证再次进入读 DB 数据准确。
    """
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        code = _code(code)
        today = _today_str()
        tracking = db.query(StockKlineTracking).filter(StockKlineTracking.code == code).first()
        behind = tracking is None or not tracking.last_trade_date or tracking.last_trade_date < today

        backfilled = None
        if behind:
            backfilled = fetch_and_store_one(code, db)

        intraday = False
        if _is_trading_day() and _in_kline_window():
            intraday = refresh_today(db, code)

        return {"code": code, "behind": behind, "backfilled": backfilled, "intraday": intraday}
    finally:
        if own_db:
            db.close()


# ---------- 查询 ----------
def _query_daily_bars(
    db: Session, code: str, from_date: str, to_date: str
) -> list[dict]:
    """从主表查日 K（区间过滤）"""
    rows = (
        db.query(StockKlineDaily)
        .filter(
            and_(
                StockKlineDaily.code == code,
                StockKlineDaily.adjust == ADJUST_DEFAULT,
                StockKlineDaily.trade_date >= from_date,
                StockKlineDaily.trade_date <= to_date,
            )
        )
        .order_by(StockKlineDaily.trade_date.asc())
        .all()
    )
    return [r.to_dict() for r in rows]


def _aggregate_bars(bars: list[dict], period: str) -> list[dict]:
    """daily → weekly/monthly/yearly 聚合（纯 Python 实现，用标准库 isocalendar）"""
    if period == "daily" or not bars:
        return bars

    from datetime import date as _date

    if period == "weekly":
        # ISO 周：YYYY-Www（用 date.isocalendar()，正确处理跨年周）
        def bucket_key(d: str) -> str:
            y, m, day = map(int, d.split("-"))
            iso_year, iso_week, _ = _date(y, m, day).isocalendar()
            return f"{iso_year}-W{iso_week:02d}"
    elif period == "monthly":
        bucket_key = lambda d: d[:7]  # YYYY-MM
    elif period == "yearly":
        bucket_key = lambda d: d[:4]  # YYYY
    else:
        return bars

    buckets: dict[str, dict] = {}
    for b in bars:
        k = bucket_key(b["日期"])
        if k not in buckets:
            buckets[k] = {
                "日期": b["日期"],       # 组内首根日期（实际显示用组末）
                "开盘": b.get("开盘"),
                "最高": b.get("最高"),
                "最低": b.get("最低"),
                "收盘": b.get("收盘"),
                "成交量": b.get("成交量") or 0,
                "成交额": b.get("成交额") or 0,
                "振幅": b.get("振幅"),
                "涨跌幅": b.get("涨跌幅"),
                "涨跌额": b.get("涨跌额"),
                "换手率": b.get("换手率"),
                "_dates": [b["日期"]],
            }
        else:
            v = buckets[k]
            v["最高"] = max(v["最高"] or 0, b.get("最高") or 0) if (v["最高"] and b.get("最高")) else (v["最高"] or b.get("最高"))
            v["最低"] = min(v["最低"] or 0, b.get("最低") or 0) if (v["最低"] and b.get("最低")) else (v["最低"] or b.get("最低"))
            v["成交量"] = (v["成交量"] or 0) + (b.get("成交量") or 0)
            v["成交额"] = (v["成交额"] or 0) + (b.get("成交额") or 0)
            v["收盘"] = b.get("收盘")        # 末根的收盘
            v["日期"] = b["日期"]        # 末根的日期
            v["涨跌额"] = b.get("涨跌额")
            v["涨跌幅"] = b.get("涨跌幅")
            v["_dates"].append(b["日期"])

    # 清理临时字段
    result = []
    for k in sorted(buckets.keys()):
        v = buckets[k]
        v.pop("_dates", None)
        result.append(v)
    return result


def get_kline(
    code: str,
    from_date: str,
    to_date: str,
    period: str = "daily",
    adjust: str = ADJUST_DEFAULT,
    refresh: bool = False,
    db: Optional[Session] = None,
) -> dict:
    """对外主查询接口

    返回 {code, adjust, period, bars, data_as_of, is_intraday, source, truncated}
    """
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        code = _code(code)
        # 先确保股票存在
        exists = db.query(Stock).filter(Stock.code == code).first()
        if not exists:
            return None  # 调用方 404

        # 图表打开时刷新：游标落后先补历史，交易时段再刷当日实时 bar
        if refresh and to_date >= _today_str():
            refresh_kline(code, db)

        bars = _query_daily_bars(db, code, from_date, to_date)
        bars = _aggregate_bars(bars, period)

        # 元数据
        tracking = db.query(StockKlineTracking).filter(StockKlineTracking.code == code).first()
        data_as_of = tracking.last_attempt_at if tracking else None
        last_trade = tracking.last_trade_date if tracking else None
        paused = bool(tracking.paused) if tracking else False
        today = _today_str()
        is_intraday = bool(last_trade == today) if last_trade else False
        truncated = bool(bars and bars[-1].get("日期") < today)

        return {
            "code": code,
            "adjust": adjust,
            "period": period,
            "bars": bars,
            "data_as_of": data_as_of,
            "is_intraday": is_intraday,
            "source": "akshare",
            "truncated": truncated,
            "paused": paused,
        }
    finally:
        if own_db:
            db.close()


def get_tracking_status(db: Session) -> dict:
    """全池跟踪状态汇总"""
    total = db.query(StockKlineTracking).count()
    paused = db.query(StockKlineTracking).filter(StockKlineTracking.paused == True).count()
    never = db.query(StockKlineTracking).filter(StockKlineTracking.last_trade_date.is_(None)).count()
    return {
        "total": total,
        "paused": paused,
        "never_fetched": never,
    }