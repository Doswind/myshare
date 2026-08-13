"""持仓聚合 API（核心）"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.deps import get_db
from app.services.aggregation import AggregationService

router = APIRouter()


@router.get("/by-sector")
async def holdings_by_sector(
    min_scale: float = Query(5.0, ge=0),
    min_ret_1y: float = Query(5.0, ge=-100),
    industry_name: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    sort_by: str = Query("fund_count", regex="^(fund_count|change_pct|total_market_value)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """
    核心接口：按行业分组的、来自主力基金重仓的股票列表
    支持股票价格区间 / 行业筛选 / 排序
    """
    return AggregationService.get_stocks_by_sector(
        db,
        min_scale=min_scale,
        min_ret_1y=min_ret_1y,
        industry_name=industry_name,
        price_min=price_min,
        price_max=price_max,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
    )
