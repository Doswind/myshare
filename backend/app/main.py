"""FastAPI 应用入口"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    funds, holdings, stocks, sectors, filters, jobs, watchlist,
    crawl_config, rbac, filter_preferences, screener, openclaw, kline,
)
from app.config import settings
from app.database import init_db
from app.scheduler.scheduler import scheduler, register_jobs
from app.services.rbac_seed import seed_rbac

logging.basicConfig(
    level=logging.INFO if not settings.app_debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动 / 关闭钩子"""
    init_db()
    seed_rbac()
    register_jobs()
    # 收敛上次运行残留的 running 会话消息（进程重启后无法续接）
    try:
        from app.services.openclaw_session_service import reset_stale_running
        reset_stale_running()
    except Exception as e:
        logger.warning("收敛残留会话消息失败: %s", e)
    # OpenClaw token 缺失提示（不影响启动，/api/openclaw/chat 会按需返回 503）
    if not settings.openclaw_token:
        logger.warning(
            "OPENCLAW_TOKEN 未配置，/api/openclaw/chat 将返回 503。"
            "如需启用 AI 析股，请在 .env 中设置 OPENCLAW_TOKEN。"
        )
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
app.include_router(
    filter_preferences.router,
    prefix="/api/filter-preferences",
    tags=["filter-preferences"],
)
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(crawl_config.router, prefix="/api/crawl-config", tags=["crawl-config"])
app.include_router(screener.router, prefix="/api/screener", tags=["screener"])
app.include_router(openclaw.router, prefix="/api/openclaw", tags=["openclaw"])

# K 线路由：合并到 /api/stocks/{code}/kline，避免新增顶级前缀
from app.deps import get_current_user as _gcu
from fastapi import Depends as _Depends
kline_protected = APIRouter(dependencies=[_Depends(_gcu)])
from app.api.kline import router as _kline_router
kline_protected.include_router(_kline_router)
app.include_router(kline_protected, prefix="/api/stocks", tags=["kline"])
for r in rbac.routers:
    app.include_router(r)


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
