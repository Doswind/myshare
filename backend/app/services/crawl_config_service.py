"""抓取配置服务

数据存到 crawl_config 表（持久化，重启不丢）
用户可在 Settings 页面编辑，编辑后通过 scheduler.reload_job() 重新注册 APScheduler 任务
"""
import logging
from typing import List, Dict, Any, Optional

from app.database import SessionLocal
from app.models.crawl_config import CrawlConfig

logger = logging.getLogger(__name__)


# 默认配置（首次启动写入）
DEFAULTS: List[Dict[str, Any]] = [
    {
        "job_key": "funds_full",
        "display_name": "基金列表+持仓",
        "cron_type": "daily",
        "time_of_day": "20:30",
        "enabled": True,
        "description": "全量抓基金列表 + 主力基金最新季报持仓，约 10-15 分钟",
    },
    {
        "job_key": "fund_nav",
        "display_name": "基金正式净值",
        "cron_type": "daily",
        "time_of_day": "20:35",
        "enabled": True,
        "description": "基金公司 20:00 后公布当日净值，覆盖估算值",
    },
    {
        "job_key": "quotes",
        "display_name": "持仓股票行情",
        "cron_type": "interval",
        "interval_minutes": 5,
        "window_start": "09:30",
        "window_end": "15:00",
        "trading_only": True,
        "enabled": True,
        "description": "刷新 500+ 只持仓股行情（交易时段每 N 分钟）",
    },
    {
        "job_key": "sectors",
        "display_name": "行业+成分股",
        "cron_type": "daily",
        "time_of_day": "21:00",
        "enabled": True,
        "description": "刷新 24 个行业板块 + 成分股，反向填充 stock.industry_name",
    },
    {
        "job_key": "fund_details",
        "display_name": "基金详情(评级/经理)",
        "cron_type": "daily",
        "time_of_day": "22:00",
        "enabled": True,
        "description": "回填主力基金的风险等级 / 评级 / 经理 / 管理人",
    },
    {
        "job_key": "stock_details",
        "display_name": "股票详情(行业)",
        "cron_type": "daily",
        "time_of_day": "22:30",
        "enabled": True,
        "description": "回填持仓股的 industry_name（emweb 单股接口）",
    },
]


class CrawlConfigService:
    """抓取任务配置 CRUD"""

    @staticmethod
    def seed_defaults() -> None:
        """首次启动：写入默认配置（已存在则跳过）"""
        db = SessionLocal()
        try:
            existing = {r.job_key for r in db.query(CrawlConfig).all()}
            added = 0
            for d in DEFAULTS:
                if d["job_key"] in existing:
                    continue
                row = CrawlConfig(**d)
                db.add(row)
                added += 1
            if added:
                db.commit()
                logger.info("初始化抓取配置：新增 %d 条", added)
        finally:
            db.close()

    @staticmethod
    def list_all() -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            rows = db.query(CrawlConfig).order_by(CrawlConfig.job_key).all()
            return [r.to_dict() for r in rows]
        finally:
            db.close()

    @staticmethod
    def get(job_key: str) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            row = db.query(CrawlConfig).filter(CrawlConfig.job_key == job_key).first()
            return row.to_dict() if row else None
        finally:
            db.close()

    @staticmethod
    def update(job_key: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """部分更新（白名单字段）"""
        allowed = {
            "display_name", "cron_type", "interval_minutes", "time_of_day",
            "window_start", "window_end", "trading_only", "enabled", "description",
        }
        db = SessionLocal()
        try:
            row = db.query(CrawlConfig).filter(CrawlConfig.job_key == job_key).first()
            if not row:
                # 自动用 defaults 补一条
                default = next((d for d in DEFAULTS if d["job_key"] == job_key), None)
                if not default:
                    raise ValueError(f"未知任务: {job_key}")
                row = CrawlConfig(**default)
                db.add(row)
                db.commit()
                db.refresh(row)
            for k, v in updates.items():
                if k in allowed:
                    setattr(row, k, v)
            db.commit()
            db.refresh(row)
            return row.to_dict()
        finally:
            db.close()

    @staticmethod
    def bulk_update(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量更新（Settings 页面保存整张表用）"""
        out = []
        for it in items:
            key = it.get("job_key")
            if not key:
                continue
            data = {k: v for k, v in it.items() if k != "job_key"}
            out.append(CrawlConfigService.update(key, data))
        return out

    @staticmethod
    def reset_all() -> List[Dict[str, Any]]:
        """重置为默认"""
        db = SessionLocal()
        try:
            db.query(CrawlConfig).delete()
            db.commit()
        finally:
            db.close()
        CrawlConfigService.seed_defaults()
        return CrawlConfigService.list_all()
