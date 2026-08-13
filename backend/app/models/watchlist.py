"""自选股模型（按用户隔离）
仅存储 (user_id, code) 的映射关系 + 用户个性化字段（note / sort_order）。
股票基本信息（name / industry / market 等）统一在 stock 表维护。
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Index, PrimaryKeyConstraint

from app.database import Base


class Watchlist(Base):
    """用户自选股（按用户隔离）"""
    __tablename__ = "watchlist"

    code = Column(String(8), nullable=False, comment="股票代码")
    user_id = Column(Integer, nullable=False, default=0, index=True, comment="所属用户 id")
    # 股票名称不再存这里，统一从 stock 表查（避免重复录入）
    name = Column(String(60), nullable=False, default="", comment="[已废弃] 历史冗余字段，name 统一查 stock 表")
    note = Column(String(120), default="", comment="用户备注（个性化）")
    sort_order = Column(Integer, default=0, comment="用户排序（个性化）")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # 复合主键：(user_id, code) —— 同一用户对同一股票只能有一条
        PrimaryKeyConstraint("user_id", "code", name="pk_watchlist_user_code"),
        Index("idx_watchlist_user_order", "user_id", "sort_order"),
    )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "user_id": self.user_id,
            "note": self.note or "",
            "sort_order": self.sort_order or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
