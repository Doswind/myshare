"""SQLAlchemy 同步引擎和 Session"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from app.config import settings

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
    # 首次启动：写入默认抓取配置
    from app.services.crawl_config_service import CrawlConfigService
    CrawlConfigService.seed_defaults()


def get_db():
    """FastAPI 依赖注入：获取 DB session"""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
