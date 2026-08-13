"""FastAPI 依赖注入 - 向后兼容层（新代码请用 app.core.deps）"""
from app.core.deps import get_db, get_current_user, require_admin, require_permission
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token

__all__ = [
    "get_db", "get_current_user", "require_admin", "require_permission",
    "hash_password", "verify_password", "create_access_token", "create_refresh_token", "decode_token",
]
