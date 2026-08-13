"""RBAC 默认数据：权限码 + 角色 + admin 账号"""
import logging
from typing import List, Dict, Any

from app.database import SessionLocal
from app.models.rbac import User, Role, Permission
from app.core.security import hash_password

logger = logging.getLogger(__name__)


# ============== 权限码定义 ==============
PERMISSIONS: List[Dict[str, Any]] = [
    # dashboard
    {"code": "dashboard:view", "name": "查看看板", "resource": "dashboard", "action": "view"},
    # funds
    {"code": "funds:view", "name": "查看基金", "resource": "funds", "action": "view"},
    {"code": "funds:export", "name": "导出基金", "resource": "funds", "action": "export"},
    # stocks
    {"code": "stocks:view", "name": "查看股票", "resource": "stocks", "action": "view"},
    {"code": "stocks:export", "name": "导出股票", "resource": "stocks", "action": "export"},
    # holdings
    {"code": "holdings:view", "name": "查看持仓", "resource": "holdings", "action": "view"},
    # sectors
    {"code": "sectors:view", "name": "查看板块", "resource": "sectors", "action": "view"},
    # watchlist
    {"code": "watchlist:view", "name": "查看自选股", "resource": "watchlist", "action": "view"},
    {"code": "watchlist:edit", "name": "编辑自选股", "resource": "watchlist", "action": "edit"},
    # filters
    {"code": "filters:view", "name": "查看筛选", "resource": "filters", "action": "view"},
    {"code": "filters:edit", "name": "编辑筛选", "resource": "filters", "action": "edit"},
    # settings
    {"code": "settings:view", "name": "查看设置", "resource": "settings", "action": "view"},
    {"code": "settings:edit", "name": "编辑设置", "resource": "settings", "action": "edit"},
    # jobs
    {"code": "jobs:view", "name": "查看抓取任务", "resource": "jobs", "action": "view"},
    {"code": "jobs:trigger", "name": "手动触发抓取", "resource": "jobs", "action": "trigger"},
    # users
    {"code": "users:view", "name": "查看用户", "resource": "users", "action": "view"},
    {"code": "users:create", "name": "创建用户", "resource": "users", "action": "create"},
    {"code": "users:update", "name": "修改用户", "resource": "users", "action": "update"},
    {"code": "users:delete", "name": "删除用户", "resource": "users", "action": "delete"},
    # roles
    {"code": "roles:view", "name": "查看角色", "resource": "roles", "action": "view"},
    {"code": "roles:edit", "name": "编辑角色", "resource": "roles", "action": "edit"},
    # audit
    {"code": "audit:view", "name": "查看审计日志", "resource": "audit", "action": "view"},
]


# ============== 内置角色 ==============
BUILTIN_ROLES: List[Dict[str, Any]] = [
    {
        "code": "admin",
        "name": "管理员",
        "description": "拥有所有权限（绕过 RBAC）",
        "is_builtin": True,
        "permissions": [p["code"] for p in PERMISSIONS],  # 全部
    },
    {
        "code": "viewer",
        "name": "普通用户",
        "description": "查看看板、基金、股票、持仓、板块，自选股编辑",
        "is_builtin": True,
        "permissions": [
            "dashboard:view",
            "funds:view",
            "stocks:view",
            "holdings:view",
            "sectors:view",
            "watchlist:view", "watchlist:edit",
            "filters:view",
        ],
    },
    {
        "code": "analyst",
        "name": "分析师",
        "description": "普通用户 + 导出/编辑筛选",
        "is_builtin": True,
        "permissions": [
            "dashboard:view",
            "funds:view", "funds:export",
            "stocks:view", "stocks:export",
            "holdings:view",
            "sectors:view",
            "watchlist:view", "watchlist:edit",
            "filters:view", "filters:edit",
        ],
    },
]


def seed_rbac() -> None:
    """首次启动 seed：权限 + 角色 + admin 账号"""
    db = SessionLocal()
    try:
        # 1) 权限码 upsert
        existing = {p.code: p for p in db.query(Permission).all()}
        added_p = 0
        for d in PERMISSIONS:
            if d["code"] not in existing:
                db.add(Permission(**d))
                added_p += 1
        if added_p:
            db.commit()
            logger.info("RBAC seed: 新增 %d 个权限码", added_p)

        # 2) 角色 upsert
        existing_r = {r.code: r for r in db.query(Role).all()}
        added_r = 0
        for d in BUILTIN_ROLES:
            if d["code"] not in existing_r:
                role = Role(
                    code=d["code"], name=d["name"],
                    description=d["description"], is_builtin=d["is_builtin"],
                )
                # 配权限
                perms = db.query(Permission).filter(Permission.code.in_(d["permissions"])).all()
                role.permissions = perms
                db.add(role)
                added_r += 1
            else:
                # 同步权限（处理新增权限码后老角色没同步的情况）
                role = existing_r[d["code"]]
                target_perms = db.query(Permission).filter(Permission.code.in_(d["permissions"])).all()
                target_codes = {p.code for p in target_perms}
                current_codes = {p.code for p in role.permissions}
                if target_codes != current_codes:
                    role.permissions = target_perms
                    logger.info("RBAC seed: 同步角色 %s 的权限（%d -> %d）",
                                d["code"], len(current_codes), len(target_codes))
        if added_r:
            db.commit()
            logger.info("RBAC seed: 新增 %d 个角色", added_r)
        else:
            db.commit()

        # 3) admin 账号
        admin_role = db.query(Role).filter(Role.code == "admin").first()
        if not admin_role:
            logger.error("admin 角色不存在，无法创建默认账号")
            return
        if not db.query(User).filter(User.username == "admin").first():
            user = User(
                username="admin",
                email="admin@local",
                password_hash=hash_password("admin123"),
                is_admin=True,
                must_change_password=True,
            )
            user.roles = [admin_role]
            from app.models.rbac import UserProfile
            user.profile = UserProfile(display_name="管理员")
            db.add(user)
            db.commit()
            logger.info("RBAC seed: 创建默认 admin 账号（首次登录强制改密）")
        else:
            # 已有 admin，确保 is_admin=True 且有 admin 角色
            user = db.query(User).filter(User.username == "admin").first()
            if not user.is_admin:
                user.is_admin = True
            if admin_role not in user.roles:
                user.roles = list(user.roles) + [admin_role]
            db.commit()
    finally:
        db.close()
