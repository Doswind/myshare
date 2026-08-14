"""任务调度 API"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.deps import get_db, get_current_user, require_admin
from app.models.job_log import JobLog
from app.services.fund_service import FundService
from app.services.stock_service import StockService
from app.scheduler.scheduler import scheduler
from app.models.rbac import User
from app.utils.job_guard import JobGuard

logger = logging.getLogger(__name__)
router = APIRouter()

# 任务级超时：30 分钟（覆盖最大的「刷新基金」全流程：~5000 基金流式 + 500 主力持仓并发）
JOB_TIMEOUT_SECONDS = 30 * 60


async def _run_with_log_id(job_id: str, job_name: str, coro_factory, log_id: int):
    """后台任务包装：写日志（含整体超时与异常恢复）

    任务级 30 分钟超时：超过则标记 failed 并释放 JobGuard
    任何异常都会被捕获并写入日志
    """
    from app.database import SessionLocal
    db = SessionLocal()
    log = db.query(JobLog).filter(JobLog.id == log_id).first()
    try:
        # 用 wait_for 给整个任务级加超时
        result = await asyncio.wait_for(coro_factory(), timeout=JOB_TIMEOUT_SECONDS)
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
    except asyncio.TimeoutError:
        logger.error("Job %s 超时（%ds）", job_id, JOB_TIMEOUT_SECONDS)
        log.status = "failed"
        log.error_message = f"任务执行超过 {JOB_TIMEOUT_SECONDS // 60} 分钟未完成，已自动终止"
        log.finished_at = datetime.utcnow()
        db.commit()
    except asyncio.CancelledError:
        logger.warning("Job %s 被取消", job_id)
        log.status = "failed"
        log.error_message = "任务被取消"
        log.finished_at = datetime.utcnow()
        db.commit()
        raise
    except Exception as e:
        logger.exception("Job %s failed", job_id)
        log.status = "failed"
        log.error_message = str(e)[:500]
        log.finished_at = datetime.utcnow()
        db.commit()
    finally:
        JobGuard.release(job_id)
        db.close()


def _acquire_or_fail(job_id: str) -> None:
    """获取任务锁 / 冷却检查：
    - 任务正在跑 → 409
    - 任务在冷却期 → 429（带 remaining_seconds）
    """
    if JobGuard.is_running(job_id):
        raise HTTPException(409, f"任务 {job_id} 正在运行中，请等待当前任务完成后再试")
    remain = JobGuard.cooldown_remaining(job_id)
    if remain > 0:
        # 429 Too Many Requests，前端按 remaining_seconds 倒计时
        raise HTTPException(
            status_code=429,
            detail=f"任务 {job_id} 冷却中，请 {remain} 秒后再试",
            headers={"Retry-After": str(remain), "X-Cooldown-Remaining": str(remain)},
        )
    if not JobGuard.acquire_sync(job_id):
        # 双保险：上面已经检查过 running，但被并发抢占时再走一次
        raise HTTPException(409, f"任务 {job_id} 正在运行中，请等待当前任务完成后再试")


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
    _acquire_or_fail("manual_funds")
    async def _task():
        return await FundService.refresh_all_funds()
    log_id = await _log_start("manual_funds", "手动刷新基金")
    asyncio.create_task(_run_with_log_id("manual_funds", "手动刷新基金", _task, log_id))
    return {"status": "started", "job_id": "manual_funds", "log_id": log_id}


@router.post("/quotes/refresh")
async def trigger_quote_refresh(background: BackgroundTasks, only_holdings: bool = True):
    """手动触发：刷新行情"""
    _acquire_or_fail("manual_quotes")
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
    _acquire_or_fail("manual_sectors")
    async def _task():
        return await StockService.refresh_sectors_and_industries()
    log_id = await _log_start("manual_sectors", "手动刷新行业")
    asyncio.create_task(_run_with_log_id("manual_sectors", "手动刷新行业", _task, log_id))
    return {"status": "started", "job_id": "manual_sectors", "log_id": log_id}


@router.post("/stock-details/refresh")
async def trigger_stock_detail_refresh(background: BackgroundTasks):
    """手动触发：单股详情（行业/名称回填，emweb 端点，push2 限流时仍可用）"""
    _acquire_or_fail("manual_stock_details")
    async def _task():
        return await StockService.refresh_stock_details()
    log_id = await _log_start("manual_stock_details", "手动刷新股票详情")
    asyncio.create_task(_run_with_log_id("manual_stock_details", "手动刷新股票详情", _task, log_id))
    return {"status": "started", "job_id": "manual_stock_details", "log_id": log_id}


@router.post("/fund-details/refresh")
async def trigger_fund_detail_refresh(background: BackgroundTasks, only_main: bool = True):
    """手动触发：基金详情（风险等级 / 评级 / 经理 / 管理人）
    only_main: True = 只刷主力基金（is_main=1，约 500 只，3-5 分钟）

    注意：fund_details 已合并到 fund_nav 定时任务中，此端点保留用于单独手动触发。
    JobGuard 锁与 manual_fund_nav 共享，避免同时跑净值+详情冲突。
    """
    _acquire_or_fail("manual_fund_nav")  # 共享锁，避免与净值任务冲突
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
    log_id = await _log_start("manual_fund_nav", f"手动刷新基金详情({len(codes)}只)")
    asyncio.create_task(_run_with_log_id("manual_fund_nav", f"手动刷新基金详情({len(codes)}只)", _task, log_id))
    return {"status": "started", "job_id": "manual_fund_nav", "log_id": log_id, "fund_count": len(codes)}


# ---- 维护接口 ----
@router.get("/running")
async def list_running_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """查看当前正在运行的任务（含 JobGuard 内存锁 + 数据库 running 状态 + 冷却期）"""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=2)
    return {
        "in_memory_locks": JobGuard.list_running(),
        "cooldowns": JobGuard.list_cooldowns(),  # job_id -> 剩余秒数
        "db_running_recent": [
            r.to_dict() for r in db.query(JobLog)
            .filter(JobLog.status == "running", JobLog.started_at >= cutoff)
            .order_by(desc(JobLog.started_at))
            .all()
        ],
    }


@router.post("/cleanup-stuck")
async def cleanup_stuck_jobs(
    stuck_minutes: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """清理卡住的 running 任务（running 状态超过 stuck_minutes 分钟视为卡死）

    行为：
    - 把所有超时卡死的 JobLog 标记为 failed + 写明原因
    - 释放 JobGuard 中的同名任务锁

    需要管理员权限（避免误操作清掉别人的活跃任务）
    """
    from datetime import timedelta
    if not user.is_admin:
        raise HTTPException(403, "仅管理员可清理卡住的任务")
    cutoff = datetime.utcnow() - timedelta(minutes=stuck_minutes)
    stuck = (
        db.query(JobLog)
        .filter(JobLog.status == "running", JobLog.started_at < cutoff)
        .all()
    )
    cleaned = []
    for log in stuck:
        log.status = "failed"
        log.error_message = f"卡住超时（>{stuck_minutes} 分钟），已被清理"
        log.finished_at = datetime.utcnow()
        # 释放 JobGuard
        JobGuard.force_release(log.job_id)
        cleaned.append({"log_id": log.id, "job_id": log.job_id, "started_at": log.started_at.isoformat()})
    db.commit()
    return {"cleaned_count": len(cleaned), "cleaned": cleaned}


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
