"""调度任务日志模型"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, Index

from app.database import Base


def _aware_iso(dt: Optional[datetime]) -> Optional[str]:
    """把 datetime 序列化为带时区的 ISO 8601 字符串

    - aware datetime：原样输出（含 tzinfo）
    - naive datetime：按 UTC 处理（兼容历史数据，之前的 datetime.utcnow() 都是 naive UTC）
    - None：原样输出
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class JobLog(Base):
    """调度任务执行日志"""
    __tablename__ = "job_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(40), nullable=False, comment="调度任务ID")
    job_name = Column(String(80))
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)
    status = Column(String(20), default="running", comment="running/success/failed")
    items_processed = Column(Integer, default=0)
    error_message = Column(Text)

    __table_args__ = (
        Index("idx_joblog_started", "started_at"),
        Index("idx_joblog_job", "job_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "job_name": self.job_name,
            "started_at": _aware_iso(self.started_at),
            "finished_at": _aware_iso(self.finished_at),
            "status": self.status,
            "items_processed": self.items_processed,
            "error_message": self.error_message,
        }
