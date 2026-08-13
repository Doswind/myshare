"""股票 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.deps import get_db
from app.services.stock_service import StockService

router = APIRouter()


@router.get("/search")
async def search_stocks(
    q: str = Query(..., min_length=1, description="代码 / 名称 / 拼音首字母"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """自选股添加时的智能联想接口：支持代码、中文名、拼音首字母
    本地 + 东方财富在线搜索（找不到时自动入库）"""
    return await StockService.search_stocks_with_remote(db, q, limit)


@router.get("/{code}")
async def get_stock(code: str, db: Session = Depends(get_db)):
    s = StockService.get_stock(db, code)
    if not s:
        raise HTTPException(404, f"股票 {code} 不存在")
    return s


@router.get("/{code}/quote")
async def get_stock_quote(code: str, db: Session = Depends(get_db)):
    q = StockService.get_latest_quote(db, code)
    if not q:
        raise HTTPException(404, f"股票 {code} 暂无行情")
    return q


@router.post("/batch-quotes")
async def get_batch_quotes(codes: List[str], db: Session = Depends(get_db)):
    return StockService.get_batch_latest_quotes(db, codes)


@router.get("/{code}/funds")
async def get_funds_holding_stock(code: str, db: Session = Depends(get_db)):
    """反向：哪些主力基金重仓了这只股票"""
    return StockService.get_funds_holding_stock(db, code)
