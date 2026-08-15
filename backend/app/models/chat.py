"""AI 对话会话与消息模型（按用户隔离）

- ChatSession：一个用户的一次对话会话；主键 id 直接用 uuid（同时作为 OpenClaw
  user 字段的会话标识：user = "{用户名}-{session.id}"）；title 取首条用户消息摘要；
  last_response_id 用于 OpenClaw 多轮上下文续接。
- ChatMessage：会话内的消息；session_id 指向 chat_session.id（uuid 字符串）。
  assistant 消息有 status（running/done/error），支持"后台生成、断线续接"。
  attachments 仅存元信息（文件名/类型），不存 base64 原文。
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Index

from app.database import Base


class ChatSession(Base):
    """用户对话会话（主键为 uuid）"""
    __tablename__ = "chat_session"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()),
                comment="会话 uuid（主键，同时用于拼 OpenClaw user 字段）")
    user_id = Column(Integer, nullable=False, index=True, comment="所属用户 id")
    title = Column(String(80), nullable=False, default="新会话", comment="会话标题（取首条用户消息摘要）")
    last_response_id = Column(String(120), nullable=True, comment="OpenClaw 多轮上下文 response_id")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_chat_session_user_updated", "user_id", "updated_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title or "新会话",
            "last_response_id": self.last_response_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ChatMessage(Base):
    """会话内的单条消息"""
    __tablename__ = "chat_message"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False, index=True, comment="所属会话 id（chat_session.id / uuid）")
    role = Column(String(16), nullable=False, comment="user / assistant")
    content = Column(Text, nullable=False, default="", comment="消息内容（assistant 生成中会持续更新）")
    status = Column(String(16), nullable=False, default="done", comment="done / running / error（user 恒 done）")
    error = Column(String(400), nullable=True, comment="status=error 时的错误文案")
    attachments = Column(JSON, nullable=True, comment="附件元信息 [{name, media_type, kind}]（不含 data）")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_chat_message_session", "session_id", "id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content or "",
            "status": self.status or "done",
            "error": self.error,
            "attachments": self.attachments or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
