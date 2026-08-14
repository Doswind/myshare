"""APScheduler 调度器（配置驱动）

每个抓取任务从 crawl_config 表读取配置：
  - cron_type=off       → 不注册
  - cron_type=daily     → 每天 time_of_day 触发
  - cron_type=interval  → 每 interval_minutes 触发；可设 window_start/end + trading_only
修改配置后调 reload_job(key) 重新注册
"""
import asyncio
import logging
from datetime import datetime, time as dtime
from functools import wraps
from typing import Optional, Dict, Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.models.job_log import JobLog
from app.models.crawl_config import CrawlConfig
from app.services.fund_service import FundService
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)


# ---------- 日志辅助 ----------
def _new_log(job_id: str, job_name: str) -> int:
    db = SessionLocal()
    try:
        log = JobLog(job_id=job_id, job_name=job_name, started_at=datetime.utcnow(), status="running")
        db.add(log)
        db.commit()
        return log.id
    finally:
        db.close()


def _finish_log(log_id: int, status: str, items: int = 0, err: str = ""):
    db = SessionLocal()
    try:
        log = db.query(JobLog).filter(JobLog.id == log_id).first()
        if log:
            log.status = status
            log.items_processed = items
            log.error_message = err[:500] if err else None
            log.finished_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


# ---------- 任务函数 ----------
def _run_async(coro):
    """在线程池里跑 async 协程"""
    return asyncio.run(coro)


def job_funds_full():
    log_id = _new_log("sched_funds_full", "定时：基金列表+持仓")
    try:
        result = _run_async(FundService.refresh_all_funds())
        _finish_log(log_id, "success", items=result.get("funds_upserted", 0))
        logger.info("[sched] funds_full done: %s", result)
    except Exception as e:
        logger.exception("[sched] funds_full failed")
        _finish_log(log_id, "failed", err=str(e))


def job_fund_nav():
    """每日 20:30 抓基金正式净值 + 基金详情（评级/经理）

    合并原因：
    - 净值更新后紧接着刷详情，逻辑连贯
    - 都是交易日晚上跑，用户少配一个任务
    - fund_details 抓的是主力基金详情（500 只），3-5 分钟即可完成
    """
    log_id = _new_log("sched_fund_nav", "定时：基金净值+详情")
    try:
        from app.scrapers.eastmoney_funds import EastmoneyFundsScraper

        async def _run():
            sc = EastmoneyFundsScraper()
            try:
                db = SessionLocal()
                try:
                    # 阶段 1：抓基金列表（净值/规模/收益率）
                    total = 0
                    for ft in FundService.FUND_TYPES:
                        items = await sc.fetch_all_streaming(ft, max_pages=60, on_batch=None)
                        cnt = FundService.upsert_funds(db, items)
                        total += cnt
                    FundService.recalc_main_flag(db)
                    logger.info("[sched] fund_nav: 净值抓取完成，%d funds", total)

                    # 阶段 2：抓主力基金详情（评级/经理/管理人）
                    from app.models.fund import Fund
                    codes = [c for (c,) in db.query(Fund.code).filter(Fund.is_main == 1).all()]
                    detail_result = await FundService.refresh_fund_details(codes)
                    logger.info("[sched] fund_nav: 详情抓取完成，%d funds",
                                detail_result.get("updated", 0))
                    return {"funds_upserted": total, "details_updated": detail_result.get("updated", 0)}
                finally:
                    db.close()
            finally:
                await sc.close()

        result = _run_async(_run())
        _finish_log(log_id, "success",
                    items=(result.get("funds_upserted", 0) + result.get("details_updated", 0)))
        logger.info("[sched] fund_nav done: %s", result)
    except Exception as e:
        logger.exception("[sched] fund_nav failed")
        _finish_log(log_id, "failed", err=str(e))


def job_quotes():
    log_id = _new_log("sched_quotes", "定时：持仓股票行情")
    try:
        from app.models.holding import FundHolding
        db = SessionLocal()
        try:
            codes = [c for (c,) in db.query(FundHolding.stock_code).distinct().all() if c]
        finally:
            db.close()
        result = _run_async(StockService.refresh_quotes(codes))
        _finish_log(log_id, "success", items=result.get("snapshots", 0))
    except Exception as e:
        logger.exception("[sched] quotes failed")
        _finish_log(log_id, "failed", err=str(e))


def job_sectors():
    log_id = _new_log("sched_sectors", "定时：行业+成分股")
    try:
        result = _run_async(StockService.refresh_sectors_and_industries())
        _finish_log(log_id, "success", items=result.get("sectors", 0))
    except Exception as e:
        logger.exception("[sched] sectors failed")
        _finish_log(log_id, "failed", err=str(e))


def job_stock_details():
    log_id = _new_log("sched_stock_details", "定时：股票详情(行业)")
    try:
        result = _run_async(StockService.refresh_stock_details())
        _finish_log(log_id, "success", items=result.get("details", 0))
    except Exception as e:
        logger.exception("[sched] stock_details failed")
        _finish_log(log_id, "failed", err=str(e))


# job_key → 实际函数
JOB_REGISTRY: Dict[str, Callable] = {
    "funds_full": job_funds_full,
    "fund_nav": job_fund_nav,
    "quotes": job_quotes,
    "sectors": job_sectors,
    "stock_details": job_stock_details,
}


# ---------- 交易日 / 窗口判断 ----------
def _parse_hhmm(s: str) -> Optional[dtime]:
    """'HH:MM' → time；空串或解析失败返回 None"""
    if not s:
        return None
    try:
        h, m = s.split(":")
        return dtime(int(h), int(m))
    except (ValueError, AttributeError):
        return None


def _is_trading_day(d: Optional[datetime] = None) -> bool:
    """A 股交易日判断（精确：周末 + 节假日 + 调休补班都算）

    依赖 chinese_calendar 库，覆盖 2004-2026 A 股日历
    库不覆盖的远期日期（如 2027+）降级为周末判断
    """
    from datetime import date
    target = (d or datetime.now()).date()
    try:
        # is_workday: True=调休补班的周末 / 工作日；False=法定节假日 / 正常周末
        # 交易日 = 是工作日 且 不是周末
        from chinese_calendar import is_workday, is_holiday
        # is_workday 已经包含了"是工作日（含调休补班的周末）"的判断
        # A 股交易日 = is_workday=True
        return bool(is_workday(target))
    except (NotImplementedError, ValueError):
        # 远期日期库不支持 → 降级为周末判断
        return target.weekday() < 5


def _in_window(now_t: dtime, start: Optional[dtime], end: Optional[dtime]) -> bool:
    """判断 now_t 是否在 [start, end] 内；支持跨天（如 22:00-06:00）"""
    if start is None and end is None:
        return True
    if start is None:
        return now_t <= end
    if end is None:
        return now_t >= start
    if start <= end:
        return start <= now_t <= end
    # 跨天
    return now_t >= start or now_t <= end


# ---------- 调度器 ----------
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def _build_trigger(cfg: CrawlConfig):
    """根据配置构造 trigger（None 表示不调度）"""
    if not cfg.enabled or cfg.cron_type == "off":
        return None
    if cfg.cron_type == "daily":
        t = _parse_hhmm(cfg.time_of_day) or dtime(17, 0)
        return CronTrigger(hour=t.hour, minute=t.minute, timezone="Asia/Shanghai")
    if cfg.cron_type == "interval":
        return IntervalTrigger(minutes=max(1, cfg.interval_minutes or 5), timezone="Asia/Shanghai")
    return None


def _should_run_now(cfg: CrawlConfig) -> bool:
    """interval 模式下的运行时窗口判断（每次执行时由 job 函数自己检查）"""
    # 这个判断放在 job 函数里更合适（因为 trigger 控制的是触发时机，触发后还要判断窗口）
    return True


def _register_one(cfg: CrawlConfig) -> bool:
    """注册单个任务；返回是否成功"""
    if cfg.job_key not in JOB_REGISTRY:
        logger.warning("未知 job_key: %s", cfg.job_key)
        return False
    trigger = _build_trigger(cfg)
    if trigger is None:
        # 关闭或不支持的任务，先移除
        try:
            scheduler.remove_job(cfg.job_key)
        except Exception:
            pass
        return False

    # interval + window：用 IntervalTrigger；job 函数里再加窗口守卫
    # 简单做法：直接交给 trigger，job 内部用 _should_run_in_window 守卫
    try:
        scheduler.add_job(
            JOB_REGISTRY[cfg.job_key],
            trigger=trigger,
            id=cfg.job_key,
            name=cfg.display_name,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        return True
    except Exception as e:
        logger.exception("注册任务 %s 失败: %s", cfg.job_key, e)
        return False


def _wrap_with_window_guard(cfg: CrawlConfig, fn: Callable) -> Callable:
    """给任务加守卫：
    - trading_only_locked=True 的任务：强制 trading_only=True（防 DB 被改）
    - trading_only=True 且非交易日 → 跳过
    - interval 模式下，窗口外 → 跳过
    - daily 模式：每天都执行（窗口不适用）
    """
    win_s = _parse_hhmm(cfg.window_start)
    win_e = _parse_hhmm(cfg.window_end)
    is_interval = cfg.cron_type == "interval"
    # locked 任务：无视 DB 字段，强制 True
    trading = bool(cfg.trading_only) or bool(cfg.trading_only_locked)

    @wraps(fn)
    def wrapped():
        now_t = datetime.now().time()
        if trading and not _is_trading_day():
            logger.debug("[sched] %s 跳过（非交易日）", cfg.job_key)
            return
        if is_interval and not _in_window(now_t, win_s, win_e):
            logger.debug("[sched] %s 跳过（不在窗口 %s-%s）", cfg.job_key, cfg.window_start, cfg.window_end)
            return
        fn()

    return wrapped


def register_jobs():
    """首次启动：把所有启用任务注册到调度器（所有任务都套窗口/交易日守卫）"""
    db = SessionLocal()
    try:
        configs = db.query(CrawlConfig).all()
    finally:
        db.close()

    count = 0
    for cfg in configs:
        raw = _unwrap(JOB_REGISTRY.get(cfg.job_key))
        if raw is None:
            continue
        # 所有任务都包（trading_only 守卫对 daily 也生效；窗口仅 interval 检查）
        JOB_REGISTRY[cfg.job_key] = _wrap_with_window_guard(cfg, raw)
        if _register_one(cfg):
            count += 1
    logger.info("已注册 %d 个调度任务", count)


def reload_job(job_key: str) -> bool:
    """重新注册某个任务（用户改完配置后调用）"""
    db = SessionLocal()
    try:
        cfg = db.query(CrawlConfig).filter(CrawlConfig.job_key == job_key).first()
    finally:
        db.close()

    if not cfg:
        return False

    raw = _unwrap(JOB_REGISTRY.get(job_key))
    if raw is None:
        return False

    JOB_REGISTRY[job_key] = _wrap_with_window_guard(cfg, raw)
    return _register_one(cfg)


def _unwrap(fn) -> Optional[Callable]:
    """如果 fn 是 wrapped（带窗口守卫），沿 __wrapped__ 取出原始 fn"""
    if fn is None:
        return None
    return getattr(fn, "__wrapped__", None) or fn


def reload_all():
    """全部重新注册（用户保存整张配置表时调用）"""
    register_jobs()
