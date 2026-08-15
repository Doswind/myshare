"""K 线数据 API

GET  /api/stocks/{code}/kline         — 查询 K 线（按 period 聚合）
POST /api/stocks/{code}/kline/fetch    — 触发该股 K 线增量抓取（补数据用）

Job 路由在 /api/jobs/kline/*（见 api/jobs.py）
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.schemas.kline import KLineResponse
from app.services.kline_service import (
    HISTORY_YEARS, ADJUST_DEFAULT, get_kline, fetch_and_store_one,
)

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(get_current_user)])


def _default_from() -> str:
    return (datetime.utcnow() - timedelta(days=365 * HISTORY_YEARS)).strftime("%Y-%m-%d")


def _default_to() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


@router.get("/{code}/kline", response_model=KLineResponse)
async def get_stock_kline(
    code: str,
    db: Session = Depends(get_db),
    from_: Optional[str] = Query(None, alias="from", description="起始日期 YYYY-MM-DD"),
    to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    period: str = Query("daily", description="daily/weekly/monthly/yearly"),
    adjust: str = Query(ADJUST_DEFAULT, description="目前仅支持 qfq"),
    refresh: bool = Query(False, description="图表打开时强制刷当日"),
):
    """单只股票 K 线查询（后端按 period 聚合）"""
    if adjust != ADJUST_DEFAULT:
        raise HTTPException(400, f"adjust 仅支持 {ADJUST_DEFAULT}")
    if period not in {"daily", "weekly", "monthly", "yearly"}:
        raise HTTPException(400, "period 必须为 daily/weekly/monthly/yearly")

    from_date = from_ or _default_from()
    to_date = to or _default_to()

    try:
        result = get_kline(code, from_date, to_date, period=period, adjust=adjust, refresh=refresh, db=db)
    except Exception as e:
        logger.exception("get_kline failed for %s", code)
        raise HTTPException(500, f"K 线查询失败：{e}")

    if result is None:
        raise HTTPException(404, f"股票 {code} 不存在")

    return result


@router.post("/{code}/kline/fetch")
async def fetch_stock_kline(
    code: str,
    db: Session = Depends(get_db),
):
    """触发单只股票 K 线增量抓取（同步返回结果）

    - 按 tracking 表的 last_trade_date 增量抓取
    - 新股票（无游标）首次自动抓 HISTORY_YEARS 年
    - 已 paused 的股票不会被重新抓（需先 unpause）
    - 股票代码不存在 → 404

    返回 {ok, code, status, bars, last_trade_date, elapsed_sec}
    """
    from app.models.stock import Stock
    if not db.query(Stock).filter(Stock.code == code).first():
        raise HTTPException(404, f"股票 {code} 不存在")

    t0 = time.time()
    try:
        result = fetch_and_store_one(code, db)
    except Exception as e:
        logger.exception("fetch_stock_kline failed for %s", code)
        raise HTTPException(500, f"抓取失败：{e}")
    elapsed = round(time.time() - t0, 2)

    # 透传 kline_service 的结果 + elapsed（注意字段名映射：service 返回 last_date）
    return {
        "ok": result["status"] == "success",
        "code": result["code"],
        "status": result["status"],   # success / failed / empty / paused
        "bars": result.get("bars", 0),
        "last_trade_date": result.get("last_date"),
        "elapsed_sec": elapsed,
    }