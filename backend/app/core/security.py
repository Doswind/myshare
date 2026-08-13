"""认证核心：密码哈希 + JWT"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import jwt
from passlib.context import CryptContext

from app.config import settings

logger = logging.getLogger(__name__)

# bcrypt 密码哈希
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain: str) -> str:
    """bcrypt 哈希密码"""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码"""
    try:
        return pwd_context.verify(plain, hashed)
    except Exception as e:
        logger.warning("verify_password failed: %s", e)
        return False


# ========== JWT ==========
JWT_ALGORITHM = "HS256"


def create_access_token(user_id: int, extra: Optional[Dict[str, Any]] = None) -> str:
    """生成 access token（默认 1 小时）"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_ttl_min),
        "jti": f"{user_id}-{int(now.timestamp() * 1000)}",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """生成 refresh token（默认 7 天）"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_ttl_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: Optional[str] = None) -> Dict[str, Any]:
    """解码 token，失败抛 jwt.PyJWTError"""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"token type mismatch: expected={expected_type}, got={payload.get('type')}")
    return payload
