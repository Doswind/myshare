"""任务调度 API"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.deps import get_db
from app.models.job_log import JobLog
from app.services.fund_service import FundService
from app.services.stock_service import StockService
from app.scheduler.scheduler import scheduler

logger = logging.getLogger(__name__)
router = APIRouter()


async def _run_with_log(job_id: str, job_name: str, coro_factory):
    """后台任务包装：写日志"""
    from app.database import SessionLocal
    db = SessionLocal()
    log = JobLog(job_id=job_id, job_name=job_name, started_at=datetime.utcnow(), status="running")
    db.add(log)
    db.commit()
    log_id = log.id
    db.close()

    db = SessionLocal()
    log = db.query(JobLog).filter(JobLog.id == log_id).first()
    try:
        result = await coro_factory()
        log.status = "success"
        log.items_processed = result.get("snapshots") or result.get("funds_upserted") or result.get("sectors") or 0
        log.finished_at = datetime.utcnow()
        db.commit()
        logger.info("Job %s done: %s", job_id, result)
    except Exception as e:
        logger.exception("Job %s failed", job_id)
        log.status = "failed"
        log.error_message = str(e)[:500]
        log.finished_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


@router.get("")
async def list_jobs(db: Session = Depends(get_db)):
    """最近的 50 条任务日志"""
    rows = db.query(JobLog).order_by(desc(JobLog.started_at)).limit(50).all()
    return [r.to_dict() for r in rows]


@router.get("/scheduled")
async def list_scheduled():
    """当前已注册的所有调度任务"""
    out = []
    for job in scheduler.get_jobs():
        next_run = None
        try:
            next_run = job.next_run_time.isoformat() if job.next_run_time else None
        except (AttributeError, TypeError):
            # scheduler 未启动时 next_run_time 可能不可用
            pass
        out.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run,
            "trigger": str(job.trigger),
        })
    return out


@router.post("/funds/refresh")
async def trigger_fund_refresh(background: BackgroundTasks):
    """手动触发：刷新基金 + 持仓"""
    async def _task():
        return await FundService.refresh_all_funds()

    log_id = await _log_start("manual_funds", "手动刷新基金")
    asyncio.create_task(_run_with_log_id("manual_funds", "手动刷新基金", _task, log_id))
    return {"status": "started", "job_id": "manual_funds", "log_id": log_id}


@router.post("/quotes/refresh")
async def trigger_quote_refresh(background: BackgroundTasks, only_holdings: bool = True):
    """手动触发：刷新行情"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        if only_holdings:
            from app.models.holding import FundHolding
            codes = [c for (c,) in db.query(FundHolding.stock_code).distinct().all() if c]
        else:
            from app.models.stock import Stock
            codes = [c for (c,) in db.query(Stock.code).all() if c]
    finally:
        db.close()

    async def _task():
        return await StockService.refresh_quotes(codes)

    log_id = await _log_start("manual_quotes", f"手动刷新行情({len(codes)}只)")
    asyncio.create_task(_run_with_log_id("manual_quotes", f"手动刷新行情({len(codes)}只)", _task, log_id))
    return {"status": "started", "job_id": "manual_quotes", "log_id": log_id, "stock_count": len(codes)}


@router.post("/sectors/refresh")
async def trigger_sector_refresh(background: BackgroundTasks):
    """手动触发：刷新行业 + 成分股"""
    async def _task():
        return await StockService.refresh_sectors_and_industries()

    log_id = await _log_start("manual_sectors", "手动刷新行业")
    asyncio.create_task(_run_with_log_id("manual_sectors", "手动刷新行业", _task, log_id))
    return {"status": "started", "job_id": "manual_sectors", "log_id": log_id}


@router.post("/stock-details/refresh")
async def trigger_stock_detail_refresh(background: BackgroundTasks):
    """手动触发：单股详情（行业/名称回填，emweb 端点，push2 限流时仍可用）"""
    async def _task():
        return await StockService.refresh_stock_details()

    log_id = await _log_start("manual_stock_details", "手动刷新股票详情")
    asyncio.create_task(_run_with_log_id("manual_stock_details", "手动刷新股票详情", _task, log_id))
    return {"status": "started", "job_id": "manual_stock_details", "log_id": log_id}


@router.post("/fund-details/refresh")
async def trigger_fund_detail_refresh(background: BackgroundTasks, only_main: bool = True):
    """手动触发：基金详情（风险等级 / 评级 / 经理 / 管理人）
    only_main: True = 只刷主力基金（is_main=1，约 500 只，3-5 分钟）
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        if only_main:
            from app.models.fund import Fund
            codes = [c for (c,) in db.query(Fund.code).filter(Fund.is_main == 1).all()]
        else:
            codes = [c for (c,) in db.query(Fund.code).all()]
    finally:
        db.close()

    async def _task():
        return await FundService.refresh_fund_details(codes)

    log_id = await _log_start("manual_fund_details", f"手动刷新基金详情({len(codes)}只)")
    asyncio.create_task(_run_with_log_id("manual_fund_details", f"手动刷新基金详情({len(codes)}只)", _task, log_id))
    return {"status": "started", "job_id": "manual_fund_details", "log_id": log_id, "fund_count": len(codes)}


@router.get("/{log_id}")
async def get_log(log_id: int, db: Session = Depends(get_db)):
    log = db.query(JobLog).filter(JobLog.id == log_id).first()
    if not log:
        raise HTTPException(404, "log not found")
    return log.to_dict()


# ---- 内部辅助 ----
async def _log_start(job_id: str, job_name: str) -> int:
    from app.database import SessionLocal
    db = SessionLocal()
    log = JobLog(job_id=job_id, job_name=job_name, started_at=datetime.utcnow(), status="running")
    db.add(log)
    db.commit()
    log_id = log.id
    db.close()
    return log_id


async def _run_with_log_id(job_id: str, job_name: str, coro_factory, log_id: int):
    from app.database import SessionLocal
    db = SessionLocal()
    log = db.query(JobLog).filter(JobLog.id == log_id).first()
    try:
        result = await coro_factory()
        log.status = "success"
        log.items_processed = (
            result.get("snapshots")
            or result.get("funds_upserted")
            or result.get("sectors")
            or result.get("stock_mappings")
            or 0
        )
        log.finished_at = datetime.utcnow()
        db.commit()
        logger.info("Job %s done: %s", job_id, result)
    except Exception as e:
        logger.exception("Job %s failed", job_id)
        log.status = "failed"
        log.error_message = str(e)[:500]
        log.finished_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()
