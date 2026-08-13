"""基金 API"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.deps import get_db
from app.services.fund_service import FundService

router = APIRouter()


@router.get("")
async def list_funds(
    min_scale: float = Query(5.0, ge=0),
    min_ret_1y: float = Query(5.0, ge=-100),
    fund_type: Optional[str] = None,
    sort: str = "ret_1y",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return FundService.query_main_funds(db, min_scale, min_ret_1y, fund_type, sort, page, page_size)


@router.get("/{code}")
async def get_fund(code: str, db: Session = Depends(get_db)):
    f = FundService.get_fund_detail(db, code)
    if not f:
        raise HTTPException(404, f"基金 {code} 不存在")
    return f


@router.get("/{code}/holdings")
async def get_fund_holdings(
    code: str,
    report_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return FundService.get_fund_holdings(db, code, report_date)
