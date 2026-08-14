"""认证 / 用户 / 角色 API"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, require_admin
from app.core.security import decode_token
from app.core.email import send_email, render_reset_password_email, render_welcome_email
from app.models.rbac import User, Role, Permission, AuditLog
from app.services.rbac_service import AuthService, PasswordResetService, UserService, RoleService, write_audit
from app.config import settings

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
user_router = APIRouter(prefix="/api/users", tags=["users"])
role_router = APIRouter(prefix="/api/roles", tags=["roles"])
perm_router = APIRouter(prefix="/api/permissions", tags=["permissions"])
audit_router = APIRouter(prefix="/api/audit", tags=["audit"])


# ============== Schemas ==============

class LoginReq(BaseModel):
    username: str
    password: str

class LoginResp(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class RefreshReq(BaseModel):
    refresh_token: str

class ChangePwReq(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)

class ForgotPwReq(BaseModel):
    email: EmailStr

class ResetPwReq(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

class ProfileUpdateReq(BaseModel):
    display_name: str = ""
    phone: str = ""
    avatar: str = ""
    email: Optional[EmailStr] = None

class UserCreateReq(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    email: EmailStr
    password: str = Field(min_length=8)
    is_admin: bool = False
    role_ids: Optional[List[int]] = None

class UserUpdateReq(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    role_ids: Optional[List[int]] = None

class AdminResetPwReq(BaseModel):
    new_password: str = Field(min_length=8)

class RoleCreateReq(BaseModel):
    code: str = Field(min_length=2, max_length=30)
    name: str
    description: str = ""
    permission_ids: List[int] = []

class RoleUpdateReq(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    permission_ids: Optional[List[int]] = None


# ============== Auth ==============

def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return (fwd.split(",")[0].strip() if fwd else request.client.host if request.client else "")


@auth_router.post("/login", response_model=LoginResp)
def login(req: LoginReq, request: Request, db: Session = Depends(get_db)):
    user = AuthService.authenticate(db, req.username, req.password)
    if not user:
        write_audit(db, "login", username=req.username, ip=_client_ip(request), ok=False)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    # 更新最后登录时间
    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    db.commit()
    write_audit(db, "login", user_id=user.id, username=user.username, ip=_client_ip(request))
    tokens = AuthService.issue_tokens(user)
    return {**tokens, "user": user.to_dict()}


@auth_router.post("/refresh", response_model=LoginResp)
def refresh(req: RefreshReq, request: Request, db: Session = Depends(get_db)):
    try:
        tokens = AuthService.refresh(db, req.refresh_token)
    except HTTPException as e:
        write_audit(db, "refresh_token", detail=str(e.detail), ip=_client_ip(request), ok=False)
        raise
    # 从 token 拿到 user_id 构造 user
    payload = decode_token(req.refresh_token, expected_type="refresh")
    user = db.query(User).get(int(payload["sub"]))
    return {**tokens, "user": user.to_dict()}


@auth_router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    write_audit(db, "logout", user_id=user.id, username=user.username, ip=_client_ip(request))
    return {"ok": True}


@auth_router.post("/change-password")
def change_password(
    req: ChangePwReq,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        AuthService.change_password(db, user, req.old_password, req.new_password)
    except HTTPException as e:
        write_audit(db, "change_password", user_id=user.id, username=user.username, ip=_client_ip(request), ok=False)
        raise
    write_audit(db, "change_password", user_id=user.id, username=user.username, ip=_client_ip(request))
    return {"ok": True}


@auth_router.post("/forgot-password")
async def forgot_password(req: ForgotPwReq, request: Request, db: Session = Depends(get_db)):
    """发送重置邮件（不告诉调用方邮箱是否存在，防枚举）"""
    ip = _client_ip(request)
    token = PasswordResetService.create_token(db, req.email, ip)
    if token:
        reset_url = f"{settings.frontend_base_url}/reset-password?token={token}"
        html = render_reset_password_email(reset_url, req.email, settings.email_reset_ttl_min)
        await send_email(req.email, "重置密码 - Fund Analyzer", html)
    # 始终返回 ok（防枚举）
    return {"ok": True, "message": "如果邮箱存在，重置链接已发送到邮箱"}


@auth_router.post("/reset-password")
def reset_password(
    req: ResetPwReq,
    request: Request,
    db: Session = Depends(get_db),
):
    user = PasswordResetService.consume_token(db, req.token, req.new_password)
    write_audit(db, "reset_password", user_id=user.id, username=user.username, ip=_client_ip(request))
    return {"ok": True}


@auth_router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user.to_dict()


# ============== Users ==============

@user_router.patch("/me")
def update_me(
    req: ProfileUpdateReq,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    UserService.update_profile(db, user, req.display_name, req.phone, req.avatar, req.email)
    return user.to_dict()


@user_router.get("")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return [u.to_dict() for u in db.query(User).order_by(User.id.asc()).all()]


@user_router.post("")
def create_user(
    req: UserCreateReq,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        user = UserService.create_user(db, **req.model_dump())
    except HTTPException as e:
        write_audit(db, "create_user", username=req.username, target=req.username, detail=str(e.detail), ip=_client_ip(request), ok=False)
        raise
    write_audit(db, "create_user", user_id=user.id, username=_.username, target=user.username, ip=_client_ip(request))
    return user.to_dict()


@user_router.patch("/{user_id}")
def update_user(
    user_id: int,
    req: UserUpdateReq,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "用户不存在")
    try:
        user = UserService.update_user(db, target, acting_admin=admin, **req.model_dump(exclude_unset=True))
    except HTTPException as e:
        write_audit(db, "update_user", user_id=admin.id, username=admin.username, target=target.username, detail=str(e.detail), ip=_client_ip(request), ok=False)
        raise
    write_audit(db, "update_user", user_id=admin.id, username=admin.username, target=target.username, ip=_client_ip(request))
    return user.to_dict()


@user_router.delete("/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(400, "不能删除自己")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "用户不存在")
    UserService.delete_user(db, target)
    write_audit(db, "delete_user", user_id=admin.id, username=admin.username, target=target.username, ip=_client_ip(request))
    return {"ok": True}


@user_router.post("/{user_id}/reset-password")
def admin_reset_password(
    user_id: int,
    req: AdminResetPwReq,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "用户不存在")
    AuthService.admin_reset_password(db, target, req.new_password)
    write_audit(db, "admin_reset_password", user_id=admin.id, username=admin.username, target=target.username, ip=_client_ip(request))
    return {"ok": True, "new_password": req.new_password}  # admin 可见


# ============== Roles ==============

@role_router.get("")
def list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return [r.to_dict() for r in db.query(Role).order_by(Role.id.asc()).all()]


@role_router.post("")
def create_role(
    req: RoleCreateReq,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        role = RoleService.create_role(db, **req.model_dump())
    except HTTPException:
        raise
    return role.to_dict()


@role_router.patch("/{role_id}")
def update_role(
    role_id: int,
    req: RoleUpdateReq,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "角色不存在")
    return RoleService.update_role(db, role, **req.model_dump(exclude_unset=True)).to_dict()


@role_router.delete("/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "角色不存在")
    RoleService.delete_role(db, role)
    return {"ok": True}


# ============== Permissions ==============

@perm_router.get("")
def list_permissions(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """权限码清单（按 resource 分组）"""
    perms = db.query(Permission).order_by(Permission.resource, Permission.id).all()
    grouped = {}
    for p in perms:
        grouped.setdefault(p.resource, []).append(p.to_dict())
    return grouped


# ============== Audit Log ==============

@audit_router.get("")
def list_audit_logs(
    page: int = 1,
    page_size: int = 20,
    action: Optional[str] = None,
    status: Optional[str] = None,
    username: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """审计日志查询（分页 + 筛选，仅管理员）"""
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if status:
        q = q.filter(AuditLog.status == status)
    if username:
        q = q.filter(AuditLog.username.ilike(f"%{username}%"))

    total = q.count()
    items = (
        q.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [r.to_dict() for r in items],
    }


# 统一 router 导出
routers = [auth_router, user_router, role_router, perm_router, audit_router]
