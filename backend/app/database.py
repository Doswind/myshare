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


def get_db():
    """FastAPI 依赖注入：获取 DB session"""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
