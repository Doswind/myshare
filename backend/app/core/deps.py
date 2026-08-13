"""FastAPI 依赖注入：当前用户 + 权限校验"""
import logging
from typing import Optional, Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.rbac import User
from app.core.security import decode_token

logger = logging.getLogger(__name__)

# OAuth2PasswordBearer 会从 Authorization: Bearer <token> 解析
# tokenUrl 是用于 Swagger UI 登录的地址（不需要真实存在）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_db() -> Session:
    """请求级 DB Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_token(token: Optional[str], request: Request) -> Optional[str]:
    """优先从 Bearer header 取，缺失则尝试 cookie"""
    if token:
        return token
    return request.cookies.get("access_token")


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """解析 JWT 并返回当前用户（401 if invalid）"""
    raw = _extract_token(token, request)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或 token 缺失",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(raw, expected_type="access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"无效 token: {e}")

    user_id = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求 admin 权限（is_admin=True）"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


def require_permission(code: str) -> Callable:
    """工厂：要求某个权限码（admin 绕过）"""
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.has_permission(code):
            logger.warning("权限不足: user=%s need=%s", current_user.username, code)
            raise HTTPException(status_code=403, detail=f"缺少权限: {code}")
        return current_user
    return _check
