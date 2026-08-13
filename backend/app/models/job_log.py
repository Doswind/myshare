"""调度任务日志模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Index

from app.database import Base


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
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "status": self.status,
            "items_processed": self.items_processed,
            "error_message": self.error_message,
        }
