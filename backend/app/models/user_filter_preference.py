"""用户筛选偏好模型"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint

from app.database import Base


class UserFilterPreference(Base):
    """按用户、页面保存筛选条件。"""
    __tablename__ = "user_filter_preference"
    __table_args__ = (
        UniqueConstraint("user_id", "scope", name="uq_user_filter_preference_scope"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    scope = Column(String(40), nullable=False)
    filters_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
