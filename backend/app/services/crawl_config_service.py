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
# 原则：没必要就不抓 → 所有任务默认 trading_only=True
DEFAULTS: List[Dict[str, Any]] = [
    {
        "job_key": "funds_full",
        "display_name": "基金列表+持仓",
        "cron_type": "daily",
        "time_of_day": "20:30",
        "trading_only": True,
        "enabled": True,
        "description": "全量抓基金列表 + 主力基金最新季报持仓，约 10-15 分钟",
    },
    {
        "job_key": "fund_nav",
        "display_name": "基金正式净值",
        "cron_type": "daily",
        "time_of_day": "20:35",
        "trading_only": True,
        "enabled": True,
        "description": "基金公司 20:00 后公布当日净值，覆盖估算值（节假日不抓）",
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
        "description": "刷新 500+ 只持仓股行情（仅交易时段）",
    },
    {
        "job_key": "sectors",
        "display_name": "行业+成分股",
        "cron_type": "daily",
        "time_of_day": "21:00",
        "trading_only": True,
        "enabled": True,
        "description": "刷新 24 个行业板块 + 成分股，反向填充 stock.industry_name（交易日抓）",
    },
    {
        "job_key": "fund_details",
        "display_name": "基金详情(评级/经理)",
        "cron_type": "daily",
        "time_of_day": "22:00",
        "trading_only": True,
        "enabled": True,
        "description": "回填主力基金的风险等级 / 评级 / 经理 / 管理人（评级/经理节假日变化极少，交易日抓即可）",
    },
    {
        "job_key": "stock_details",
        "display_name": "股票详情(行业)",
        "cron_type": "daily",
        "time_of_day": "22:30",
        "trading_only": True,
        "enabled": True,
        "description": "回填持仓股的 industry_name（行业名称稳定，交易日抓）",
    },
]


class CrawlConfigService:
    """抓取任务配置 CRUD"""

    @staticmethod
    def seed_defaults() -> None:
        """启动时同步默认配置：
        - 缺失的任务 → 新增
        - 已存在的任务 → 把 defaults 里的关键字段（trading_only/cron_type/time_of_day/...）回填
          （不覆盖用户已改过的 enabled/自定义时间）
        """
        db = SessionLocal()
        try:
            existing = {r.job_key: r for r in db.query(CrawlConfig).all()}
            added = 0
            updated = 0
            for d in DEFAULTS:
                key = d["job_key"]
                if key not in existing:
                    db.add(CrawlConfig(**d))
                    added += 1
                else:
                    # 把 defaults 的关键字段同步到已存在行（处理历史 DB 升级）
                    row = existing[key]
                    for k in ("trading_only", "cron_type", "time_of_day",
                              "interval_minutes", "window_start", "window_end",
                              "display_name", "description"):
                        if k in d and getattr(row, k) != d[k]:
                            setattr(row, k, d[k])
                            updated += 1
            if added or updated:
                db.commit()
                logger.info("同步抓取配置：新增 %d 条，更新 %d 个字段", added, updated)
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
