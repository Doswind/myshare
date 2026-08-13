"""自选股模型"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Index

from app.database import Base


class Watchlist(Base):
    """用户自选股（按用户隔离）"""
    __tablename__ = "watchlist"

    code = Column(String(8), primary_key=True, comment="股票代码")
    user_id = Column(Integer, nullable=False, default=0, index=True, comment="所属用户 id（0=历史遗留/未迁移）")
    name = Column(String(60), nullable=False, default="", comment="股票名称（首次添加时自动填）")
    note = Column(String(120), default="", comment="备注")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_watchlist_user_order", "user_id", "sort_order"),
        # 同一用户对同一股票只能有一条
        Index("idx_watchlist_user_code", "user_id", "code", unique=True),
    )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "user_id": self.user_id,
            "name": self.name,
            "note": self.note or "",
            "sort_order": self.sort_order or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
