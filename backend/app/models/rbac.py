"""用户 / 角色 / 权限 / 审计日志 模型（RBAC）"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


# ============== User ==============
class User(Base):
    """用户表"""
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(40), unique=True, nullable=False, comment="登录名（唯一）")
    email = Column(String(120), unique=True, nullable=False, comment="邮箱（用于重置密码）")
    password_hash = Column(String(120), nullable=False, comment="bcrypt 哈希")
    is_active = Column(Boolean, default=True, comment="是否启用")
    is_admin = Column(Boolean, default=False, comment="管理员标记（绕过 RBAC）")
    must_change_password = Column(Boolean, default=False, comment="首次登录是否强制改密")
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    profile = relationship("UserProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")
    roles = relationship("Role", secondary="user_role", back_populates="users")
    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self, include_email: bool = True) -> dict:
        d = {
            "id": self.id,
            "username": self.username,
            "is_active": bool(self.is_active),
            "is_admin": bool(self.is_admin),
            "must_change_password": bool(self.must_change_password),
            "roles": [r.to_dict() for r in self.roles] if self.roles else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
        if include_email:
            d["email"] = self.email
        if self.profile:
            d["profile"] = self.profile.to_dict()
        return d

    def has_permission(self, code: str) -> bool:
        """检查用户是否拥有某个权限码（admin 绕过）"""
        if self.is_admin:
            return True
        for r in self.roles:
            if not r.is_active:
                continue
            for p in r.permissions:
                if p.code == code:
                    return True
        return False

    def permission_codes(self) -> set:
        if self.is_admin:
            return {"*"}  # admin 通配
        codes = set()
        for r in self.roles:
            if not r.is_active:
                continue
            for p in r.permissions:
                codes.add(p.code)
        return codes


class UserProfile(Base):
    """用户基础信息（与 User 1:1，避免 User 表臃肿）"""
    __tablename__ = "user_profile"

    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    display_name = Column(String(60), comment="显示名")
    phone = Column(String(20), comment="手机号")
    avatar = Column(String(255), comment="头像 URL")
    preferences = Column(Text, default="{}", comment="用户偏好 JSON")

    user = relationship("User", back_populates="profile")

    def to_dict(self) -> dict:
        return {
            "display_name": self.display_name or "",
            "phone": self.phone or "",
            "avatar": self.avatar or "",
        }


# ============== Role & Permission ==============
class Permission(Base):
    """权限码（resource:action）"""
    __tablename__ = "permission"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(60), unique=True, nullable=False, comment="如 funds:view")
    name = Column(String(60), nullable=False, comment="中文名")
    resource = Column(String(30), nullable=False, comment="资源")
    action = Column(String(20), nullable=False, comment="动作 view/create/update/delete/export/trigger")
    description = Column(String(255), default="")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "resource": self.resource,
            "action": self.action,
            "description": self.description or "",
        }


class Role(Base):
    """角色"""
    __tablename__ = "role"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(30), unique=True, nullable=False, comment="admin/viewer/analyst/...")
    name = Column(String(60), nullable=False, comment="中文名")
    description = Column(String(255), default="")
    is_builtin = Column(Boolean, default=False, comment="内置角色不可删")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    users = relationship("User", secondary="user_role", back_populates="roles")
    permissions = relationship("Permission", secondary="role_permission")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description or "",
            "is_builtin": bool(self.is_builtin),
            "is_active": bool(self.is_active),
            "permissions": [p.to_dict() for p in self.permissions] if self.permissions else [],
        }


# 多对多关联表（直接用 Table 不带 Model）
from sqlalchemy import Table
user_role = Table(
    "user_role", Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
)

role_permission = Table(
    "role_permission", Base.metadata,
    Column("role_id", Integer, ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True),
)


# ============== Password Reset ==============
class PasswordResetToken(Base):
    """密码重置令牌（一次性，30 分钟有效）"""
    __tablename__ = "password_reset_token"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(120), nullable=False, index=True, comment="bcrypt 哈希后的 token")
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reset_tokens")


# ============== Audit Log ==============
class AuditLog(Base):
    """审计日志（关键操作记录）"""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String(40), comment="冗余存用户名，用户删除后仍可查")
    action = Column(String(60), nullable=False, index=True, comment="login/logout/change_password/create_user/...")
    target = Column(String(255), default="", comment="操作目标（资源 ID/名称）")
    detail = Column(Text, default="", comment="详细 JSON")
    ip = Column(String(45), default="", comment="客户端 IP")
    status = Column(String(20), default="success", comment="success/failed")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username or "",
            "action": self.action,
            "target": self.target or "",
            "detail": self.detail or "",
            "ip": self.ip or "",
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
