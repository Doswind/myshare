"""FastAPI 应用入口"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import funds, holdings, stocks, sectors, filters, jobs, watchlist, crawl_config
from app.config import settings
from app.database import init_db
from app.scheduler.scheduler import scheduler, register_jobs

logging.basicConfig(
    level=logging.INFO if not settings.app_debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动 / 关闭钩子"""
    init_db()
    register_jobs()
    try:
        scheduler.start()
        logger.info("调度器已启动")
    except Exception as e:
        logger.warning("调度器启动失败: %s", e)
    yield
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass


app = FastAPI(
    title="主力基金持仓分析",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(funds.router, prefix="/api/funds", tags=["funds"])
app.include_router(holdings.router, prefix="/api/holdings", tags=["holdings"])
app.include_router(stocks.router, prefix="/api/stocks", tags=["stocks"])
app.include_router(sectors.router, prefix="/api/sectors", tags=["sectors"])
app.include_router(filters.router, prefix="/api/filters", tags=["filters"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(crawl_config.router, prefix="/api/crawl-config", tags=["crawl-config"])


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "version": "0.1.0",
        "scheduled_jobs": [j.id for j in scheduler.get_jobs()],
    }


@app.get("/")
async def root():
    return {
        "app": "主力基金持仓分析",
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
