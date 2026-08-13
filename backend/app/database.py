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
    from app.models import Fund, FundHolding, Stock, Sector, SectorMember, StockQuote, JobLog, Watchlist, CrawlConfig
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

    if "watchlist" in insp.get_table_names():
        _migrate_watchlist_per_user()

    if "stock" in insp.get_table_names():
        _migrate_stock_details_fetched_at()


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
