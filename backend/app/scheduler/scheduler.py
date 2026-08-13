"""APScheduler 调度器"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.models.job_log import JobLog
from app.services.fund_service import FundService
from app.services.stock_service import StockService
from app.config import settings

logger = logging.getLogger(__name__)


def _new_log(job_id: str, job_name: str) -> int:
    db = SessionLocal()
    log = JobLog(job_id=job_id, job_name=job_name, started_at=datetime.utcnow(), status="running")
    db.add(log)
    db.commit()
    log_id = log.id
    db.close()
    return log_id


def _finish_log(log_id: int, status: str, items: int = 0, err: str = ""):
    db = SessionLocal()
    log = db.query(JobLog).filter(JobLog.id == log_id).first()
    if log:
        log.status = status
        log.items_processed = items
        log.error_message = err[:500] if err else None
        log.finished_at = datetime.utcnow()
        db.commit()
    db.close()


def job_crawl_funds():
    """每日 17:00：抓取基金 + 主力筛选 + 持仓"""
    import asyncio
    log_id = _new_log("sched_funds", "定时抓取基金+持仓")
    try:
        result = asyncio.run(FundService.refresh_all_funds())
        _finish_log(log_id, "success", items=result.get("funds_upserted", 0))
        logger.info("[sched] funds done: %s", result)
    except Exception as e:
        logger.exception("[sched] funds failed")
        _finish_log(log_id, "failed", err=str(e))


def job_crawl_quotes():
    """每 5 分钟：抓取持仓涉及的股票行情"""
    import asyncio
    log_id = _new_log("sched_quotes", "定时刷新持仓股票行情")
    try:
        from app.models.holding import FundHolding
        db = SessionLocal()
        try:
            codes = [c for (c,) in db.query(FundHolding.stock_code).distinct().all() if c]
        finally:
            db.close()
        result = asyncio.run(StockService.refresh_quotes(codes))
        _finish_log(log_id, "success", items=result.get("snapshots", 0))
    except Exception as e:
        logger.exception("[sched] quotes failed")
        _finish_log(log_id, "failed", err=str(e))


def job_crawl_sectors():
    """每日 17:30：抓取行业 + 成分股"""
    import asyncio
    log_id = _new_log("sched_sectors", "定时刷新行业+成分股")
    try:
        result = asyncio.run(StockService.refresh_sectors_and_industries())
        _finish_log(log_id, "success", items=result.get("sectors", 0))
    except Exception as e:
        logger.exception("[sched] sectors failed")
        _finish_log(log_id, "failed", err=str(e))


scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def register_jobs():
    if scheduler.get_jobs():
        return  # 已注册
    scheduler.add_job(
        job_crawl_funds,
        CronTrigger(hour=settings.crawl_fund_hour, minute=settings.crawl_fund_minute),
        id="crawl_funds",
        name="抓取基金列表+持仓",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        job_crawl_sectors,
        CronTrigger(hour=settings.crawl_fund_hour, minute=settings.crawl_fund_minute + 30 if settings.crawl_fund_minute < 30 else settings.crawl_fund_hour + 1),
        id="crawl_sectors",
        name="刷新行业+成分股",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        job_crawl_quotes,
        IntervalTrigger(minutes=settings.crawl_quote_interval_minutes),
        id="crawl_quotes",
        name="刷新持仓股票行情",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("已注册 %d 个调度任务", len(scheduler.get_jobs()))
