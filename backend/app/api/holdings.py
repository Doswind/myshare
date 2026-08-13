"""持仓聚合 API（核心）"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.deps import get_db
from app.services.aggregation import AggregationService, BOARD_PREFIXES

router = APIRouter()

VALID_BOARDS = sorted(BOARD_PREFIXES.keys())


@router.get("/by-sector")
async def holdings_by_sector(
    min_scale: float = Query(5.0, ge=0),
    min_ret_1y: float = Query(5.0, ge=-100),
    industry_name: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    boards: Optional[List[str]] = Query(
        None,
        description="板块过滤（多选）：沪主板 / 科创板 / 深主板 / 创业板 / 北交所",
    ),
    sort_by: str = Query("fund_count", regex="^(fund_count|change_pct|total_market_value)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """
    核心接口：按行业分组的、来自主力基金重仓的股票列表
    支持股票价格区间 / 行业筛选 / 板块筛选 / 排序
    """
    # 校验 board 参数
    if boards:
        invalid = [b for b in boards if b not in VALID_BOARDS]
        if invalid:
            from fastapi import HTTPException
            raise HTTPException(
                400,
                f"未知板块: {invalid}，可选: {VALID_BOARDS}",
            )
    return AggregationService.get_stocks_by_sector(
        db,
        min_scale=min_scale,
        min_ret_1y=min_ret_1y,
        industry_name=industry_name,
        price_min=price_min,
        price_max=price_max,
        boards=boards,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
    )


@router.get("/boards")
async def list_boards():
    """返回可选的板块列表 + 各板块代码前缀"""
    return {
        "boards": [
            {"name": "沪主板", "prefixes": BOARD_PREFIXES["沪主板"]},
            {"name": "科创板", "prefixes": BOARD_PREFIXES["科创板"]},
            {"name": "深主板", "prefixes": BOARD_PREFIXES["深主板"]},
            {"name": "创业板", "prefixes": BOARD_PREFIXES["创业板"]},
            {"name": "北交所", "prefixes": BOARD_PREFIXES["北交所"]},
        ]
    }
