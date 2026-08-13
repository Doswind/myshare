"""股票 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.deps import get_db
from app.services.stock_service import StockService

router = APIRouter()


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
