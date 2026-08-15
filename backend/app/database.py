"""SQLAlchemy 同步引擎和 Session"""
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from app.config import settings

logger = logging.getLogger(__name__)

# 启用 WAL 模式 + 外键
engine = create_engine(
    settings.db_url,
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()


def init_db():
    """初始化所有表（首次启动或新增表时调用）"""
    # 引入所有模型以注册 metadata
    from app.models import (
        Fund, FundHolding, Stock, Sector, SectorMember, StockQuote, JobLog,
        Watchlist, CrawlConfig, UserFilterPreference, ChatSession, ChatMessage,
    )
    from app.models import rbac as _rbac_models  # 注册 User 外键目标及 RBAC 表
    Base.metadata.create_all(bind=engine)
    # 列升级：create_all 不会给已有表加列，手动 ALTER
    _migrate_columns()
    # 首次启动：写入默认抓取配置
    from app.services.crawl_config_service import CrawlConfigService
    CrawlConfigService.seed_defaults()


def _migrate_columns():
    """轻量迁移：给已有表加缺失列（仅爬取配置相关，避免长停机）"""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "crawl_config" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("crawl_config")}
        with engine.begin() as conn:
            if "trading_only_locked" not in cols:
                conn.execute(text("ALTER TABLE crawl_config ADD COLUMN trading_only_locked BOOLEAN DEFAULT 0"))
                logger.info("DB 迁移: crawl_config 添加 trading_only_locked 列")
            if "day_of_week" not in cols:
                conn.execute(text("ALTER TABLE crawl_config ADD COLUMN day_of_week INTEGER DEFAULT 0"))
                logger.info("DB 迁移: crawl_config 添加 day_of_week 列")
            # 删除已合并到 fund_nav 的 fund_details 配置行
            conn.execute(text("DELETE FROM crawl_config WHERE job_key = 'fund_details'"))

    if "watchlist" in insp.get_table_names():
        _migrate_watchlist_per_user()

    if "stock" in insp.get_table_names():
        _migrate_stock_details_fetched_at()

    if "chat_session" in insp.get_table_names():
        _migrate_chat_session_to_uuid()


def _migrate_chat_session_to_uuid():
    """把 chat_session 主键从自增 int 改为 uuid（并把 chat_message.session_id 对应改为 uuid）。

    兼容两种旧状态：原始(int id, 无 uuid 列) / 中间(int id + uuid 列)。
    已是 uuid 主键则跳过。数据非破坏性迁移（复制后重建）。
    """
    from sqlalchemy import inspect, text
    from uuid import uuid4
    insp = inspect(engine)
    cols_info = insp.get_columns("chat_session")
    cols = {c["name"] for c in cols_info}
    id_col = next((c for c in cols_info if c["name"] == "id"), None)
    id_type = str(id_col["type"]).upper() if id_col else ""
    is_int_pk = "INT" in id_type
    if not is_int_pk and "uuid" not in cols:
        return  # 已是 uuid 主键

    has_msg = "chat_message" in insp.get_table_names()
    with engine.begin() as conn:
        sess_rows = [dict(r) for r in conn.execute(text("SELECT * FROM chat_session")).mappings().all()]
        msg_rows = (
            [dict(r) for r in conn.execute(text("SELECT * FROM chat_message")).mappings().all()]
            if has_msg else []
        )
        id_map = {}
        for r in sess_rows:
            id_map[r["id"]] = r.get("uuid") or str(uuid4())
        conn.execute(text("DROP TABLE IF EXISTS chat_message"))
        conn.execute(text("DROP TABLE chat_session"))

    # 用新 schema（uuid 主键）重建
    from app.models.chat import ChatSession, ChatMessage
    ChatSession.__table__.create(bind=engine, checkfirst=True)
    ChatMessage.__table__.create(bind=engine, checkfirst=True)

    with engine.begin() as conn:
        for r in sess_rows:
            conn.execute(
                text(
                    "INSERT INTO chat_session (id, user_id, title, last_response_id, created_at, updated_at) "
                    "VALUES (:id,:user_id,:title,:lrid,:ca,:ua)"
                ),
                {"id": id_map[r["id"]], "user_id": r["user_id"], "title": r.get("title") or "新会话",
                 "lrid": r.get("last_response_id"), "ca": r.get("created_at"), "ua": r.get("updated_at")},
            )
        for r in msg_rows:
            conn.execute(
                text(
                    "INSERT INTO chat_message (id, session_id, role, content, status, error, attachments, created_at) "
                    "VALUES (:id,:sid,:role,:content,:status,:error,:att,:ca)"
                ),
                {"id": r["id"], "sid": id_map.get(r["session_id"]), "role": r["role"],
                 "content": r.get("content") or "", "status": r.get("status") or "done",
                 "error": r.get("error"), "att": r.get("attachments"), "ca": r.get("created_at")},
            )
    logger.info("DB 迁移: chat_session 主键改为 uuid，重建 %d 会话 / %d 消息", len(sess_rows), len(msg_rows))


def _migrate_stock_details_fetched_at():
    """stock 表加 details_fetched_at 列：用于详情抓取的 TTL 缓存
    已有 industry_name 的视为「已抓过」并回填时间为当前，避免迁移后立即触发全量重抓
    """
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("stock")}
    if "details_fetched_at" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE stock ADD COLUMN details_fetched_at DATETIME"))
        # 已抓过详情的（行业非空）→ 回填为当前时间，避免被重新抓
        result = conn.execute(
            text(
                "UPDATE stock SET details_fetched_at = CURRENT_TIMESTAMP "
                "WHERE industry_name IS NOT NULL AND industry_name != ''"
            )
        )
        if result.rowcount:
            logger.info("DB 迁移: stock 添加 details_fetched_at 列，回填 %d 条历史记录", result.rowcount)
        else:
            logger.info("DB 迁移: stock 添加 details_fetched_at 列")


def _migrate_watchlist_per_user():
    """自选股按用户隔离 + 复合主键 (user_id, code)：
    1) 加 user_id 列（默认 0）
    2) 把历史数据全部归属给 admin（id=1）—— 升级前的 watchlist 是全局共享的
    3) 建复合唯一索引 (user_id, code)
    4) 重建主键为 (user_id, code)（SQLite 不支持换主键，需复制重建）
    """
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("watchlist")}
    indexes = {i["name"] for i in insp.get_indexes("watchlist")}
    pk = insp.get_pk_constraint("watchlist") or {}
    pk_cols = pk.get("constrained_columns") or []

    with engine.begin() as conn:
        # 1) 加 user_id 列
        if "user_id" not in cols:
            conn.execute(text("ALTER TABLE watchlist ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_watchlist_user_id ON watchlist (user_id)"))
            logger.info("DB 迁移: watchlist 添加 user_id 列")

        # 2) 把 user_id=0 的历史记录全部归属给 admin（id 最小、is_admin=1 的用户）
        if "user" in insp.get_table_names():
            admin_row = conn.execute(
                text("SELECT id FROM user WHERE is_admin = 1 ORDER BY id LIMIT 1")
            ).first()
            if admin_row:
                admin_id = admin_row[0]
                result = conn.execute(
                    text("UPDATE watchlist SET user_id = :uid WHERE user_id = 0"),
                    {"uid": admin_id},
                )
                if result.rowcount:
                    logger.info("DB 迁移: watchlist 把 %d 条历史记录归属给 admin (id=%d)", result.rowcount, admin_id)

        # 3) 复合唯一索引 (user_id, code)
        if "idx_watchlist_user_code" not in indexes:
            conn.execute(
                text(
                    """
                    DELETE FROM watchlist
                    WHERE rowid NOT IN (
                        SELECT MAX(rowid) FROM watchlist GROUP BY user_id, code
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_user_code ON watchlist (user_id, code)")
            )
            logger.info("DB 迁移: watchlist 创建复合唯一索引 (user_id, code)")

        # 4) 重建主键为 (user_id, code)
        if pk_cols != ["user_id", "code"]:
            logger.info("DB 迁移: watchlist 重建主键为 (user_id, code)（旧主键=%s）", pk_cols)
            # SQLite 不支持换主键，必须：建新表 → 拷贝 → 删旧 → 改名
            conn.execute(text("ALTER TABLE watchlist RENAME TO watchlist__old"))
            # 用期望 schema 建新表
            conn.execute(
                text(
                    """
                    CREATE TABLE watchlist (
                        code VARCHAR(8) NOT NULL,
                        user_id INTEGER NOT NULL DEFAULT 0,
                        name VARCHAR(60) NOT NULL DEFAULT '',
                        note VARCHAR(120) DEFAULT '',
                        sort_order INTEGER DEFAULT 0,
                        created_at DATETIME,
                        updated_at DATETIME,
                        CONSTRAINT pk_watchlist_user_code PRIMARY KEY (user_id, code)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_watchlist_user_id ON watchlist (user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_watchlist_user_order ON watchlist (user_id, sort_order)"))
            # 拷贝数据（去重）
            conn.execute(
                text(
                    """
                    INSERT OR IGNORE INTO watchlist (code, user_id, name, note, sort_order, created_at, updated_at)
                    SELECT code, user_id, name, note, sort_order, created_at, updated_at
                    FROM watchlist__old
                    """
                )
            )
            conn.execute(text("DROP TABLE watchlist__old"))
            # idx_watchlist_user_code 是 UNIQUE INDEX，新表重建会因主键自带唯一性而无必要，
            # 但保留以兼容仍可能在某些查询计划里被引用的情况
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_user_code ON watchlist (user_id, code)"))
            logger.info("DB 迁移: watchlist 复合主键 (user_id, code) 重建完成")

        # 5) 复合索引 (user_id, sort_order) 已包含在 4) 里，这里兜底
        if "idx_watchlist_user_order" not in indexes:
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_watchlist_user_order ON watchlist (user_id, sort_order)")
            )


def get_db():
    """FastAPI 依赖注入：获取 DB session"""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
