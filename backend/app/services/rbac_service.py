"""认证 / 用户 / 角色 业务层"""
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.rbac import User, UserProfile, Role, Permission, PasswordResetToken, AuditLog
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.config import settings

logger = logging.getLogger(__name__)


# ============== AuditLog 工具 ==============

def write_audit(
    db: Session,
    action: str,
    user_id: Optional[int] = None,
    username: str = "",
    target: str = "",
    detail: str = "",
    ip: str = "",
    ok: bool = True,
) -> None:
    """记录审计日志"""
    log = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        target=target,
        detail=detail,
        ip=ip,
        status="success" if ok else "failed",
    )
    db.add(log)
    db.commit()


# ============== 用户登录 / 注册 ==============

class AuthService:

    @staticmethod
    def authenticate(db: Session, username: str, password: str) -> Optional[User]:
        """校验用户名/密码，返回 User 或 None"""
        u = db.query(User).filter(User.username == username).first()
        if not u:
            return None
        if not u.is_active:
            return None
        if not verify_password(password, u.password_hash):
            return None
        return u

    @staticmethod
    def issue_tokens(user: User) -> Dict[str, str]:
        """签发 access + refresh token"""
        return {
            "access_token": create_access_token(user.id),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
        }

    @staticmethod
    def refresh(db: Session, refresh_token: str) -> Dict[str, str]:
        """用 refresh token 换新 access token"""
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="refresh token 已过期，请重新登录")
        except jwt.PyJWTError as e:
            raise HTTPException(status_code=401, detail=f"无效 refresh token: {e}")
        user_id = int(payload.get("sub", 0))
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在或已禁用")
        return AuthService.issue_tokens(user)

    @staticmethod
    def change_password(db: Session, user: User, old_pw: str, new_pw: str) -> None:
        """用户自己改密码"""
        if not verify_password(old_pw, user.password_hash):
            raise HTTPException(status_code=400, detail="旧密码错误")
        if len(new_pw) < 8:
            raise HTTPException(status_code=400, detail="新密码至少 8 位")
        user.password_hash = hash_password(new_pw)
        user.must_change_password = False
        db.commit()

    @staticmethod
    def admin_reset_password(db: Session, target_user: User, new_pw: str) -> None:
        """管理员重置别人密码"""
        if len(new_pw) < 8:
            raise HTTPException(status_code=400, detail="新密码至少 8 位")
        target_user.password_hash = hash_password(new_pw)
        target_user.must_change_password = True  # 强制改密
        db.commit()


# ============== 密码重置（忘记密码） ==============

class PasswordResetService:

    @staticmethod
    def create_token(db: Session, email: str, ip: str = "") -> Optional[str]:
        """根据邮箱创建重置 token，返回明文 token（仅此一次返回）或 None（邮箱不存在）"""
        user = db.query(User).filter(User.email == email, User.is_active == True).first()
        if not user:
            return None  # 安全：不告诉调用方邮箱是否存在
        # 生成随机 token（32 字节 = 64 字符）
        plain = secrets.token_urlsafe(32)
        token_hash = hash_password(plain)
        # 清理该用户的历史未用 token
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at == None,
        ).delete()
        rec = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=settings.email_reset_ttl_min),
        )
        db.add(rec)
        db.commit()
        write_audit(db, "request_password_reset", user_id=user.id, username=user.username, ip=ip)
        return plain

    @staticmethod
    def consume_token(db: Session, plain_token: str, new_password: str) -> User:
        """用 token + 新密码重置"""
        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="新密码至少 8 位")
        # 找到所有未过期未使用的 token（要遍历 verify，bcrypt 不能直接 hash 查询）
        candidates = db.query(PasswordResetToken).filter(
            PasswordResetToken.used_at == None,
            PasswordResetToken.expires_at > datetime.utcnow(),
        ).order_by(PasswordResetToken.created_at.desc()).all()

        matched: Optional[PasswordResetToken] = None
        for t in candidates:
            if verify_password(plain_token, t.token_hash):
                matched = t
                break

        if not matched:
            raise HTTPException(status_code=400, detail="token 无效或已过期")
        user = db.query(User).filter(User.id == matched.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=400, detail="用户不存在或已禁用")
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        matched.used_at = datetime.utcnow()
        db.commit()
        return user


# ============== 用户管理 ==============

class UserService:

    @staticmethod
    def create_user(
        db: Session,
        username: str,
        email: str,
        password: str,
        is_admin: bool = False,
        role_ids: Optional[List[int]] = None,
    ) -> User:
        """创建用户（管理员）"""
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="密码至少 8 位")
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail=f"用户名 {username} 已存在")
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=400, detail=f"邮箱 {email} 已存在")

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            is_admin=is_admin,
            must_change_password=True,
        )
        db.add(user)
        db.flush()  # 拿 user.id
        # 配 profile
        user.profile = UserProfile(display_name=username)
        # 配角色
        if role_ids:
            roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
            user.roles = roles
        elif not is_admin:
            # 普通用户默认给 viewer 角色
            viewer = db.query(Role).filter(Role.code == "viewer").first()
            if viewer:
                user.roles = [viewer]
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_user(
        db: Session,
        user: User,
        email: Optional[str] = None,
        is_active: Optional[bool] = None,
        role_ids: Optional[List[int]] = None,
    ) -> User:
        """管理员更新用户"""
        if email and email != user.email:
            if db.query(User).filter(User.email == email, User.id != user.id).first():
                raise HTTPException(status_code=400, detail="邮箱已被其他用户使用")
            user.email = email
        if is_active is not None:
            user.is_active = is_active
        if role_ids is not None:
            roles = db.query(Role).filter(Role.id.in_(role_ids)).all() if role_ids else []
            user.roles = roles
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_profile(
        db: Session,
        user: User,
        display_name: str,
        phone: str,
        avatar: str,
        email: Optional[str] = None,
    ) -> User:
        """用户自己更新基础信息（含邮箱）"""
        if not user.profile:
            user.profile = UserProfile()
        user.profile.display_name = display_name
        user.profile.phone = phone
        user.profile.avatar = avatar
        if email and email != user.email:
            # 检查邮箱是否被其他用户占用
            if db.query(User).filter(User.email == email, User.id != user.id).first():
                raise HTTPException(status_code=400, detail="邮箱已被其他用户使用")
            user.email = email
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_user(db: Session, user: User) -> None:
        """删除用户（不能删自己）"""
        db.delete(user)
        db.commit()


# ============== 角色 / 权限 ==============

class RoleService:

    @staticmethod
    def create_role(db: Session, code: str, name: str, description: str, permission_ids: List[int]) -> Role:
        if db.query(Role).filter(Role.code == code).first():
            raise HTTPException(status_code=400, detail=f"角色 {code} 已存在")
        role = Role(code=code, name=name, description=description)
        if permission_ids:
            perms = db.query(Permission).filter(Permission.id.in_(permission_ids)).all()
            role.permissions = perms
        db.add(role)
        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def update_role(
        db: Session,
        role: Role,
        name: Optional[str] = None,
        description: Optional[str] = None,
        permission_ids: Optional[List[int]] = None,
        is_active: Optional[bool] = None,
    ) -> Role:
        if name is not None:
            role.name = name
        if description is not None:
            role.description = description
        if is_active is not None:
            role.is_active = is_active
        if permission_ids is not None:
            perms = db.query(Permission).filter(Permission.id.in_(permission_ids)).all() if permission_ids else []
            role.permissions = perms
        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def delete_role(db: Session, role: Role) -> None:
        if role.is_builtin:
            raise HTTPException(status_code=400, detail="内置角色不可删除")
        if role.users:
            raise HTTPException(status_code=400, detail=f"角色正在被 {len(role.users)} 个用户使用")
        db.delete(role)
        db.commit()
