"""选股分析 demo API（mock 数据，不接真实抓取）

GET /api/screener/candidates         — 候选列表（可按 industry / min_score 过滤）
GET /api/screener/factors/{code}      — 单只因子详情
GET /api/screener/holders/{code}      — 单只重仓基金列表
GET /api/screener/industries          — 候选行业列表（用于筛选下拉）
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_current_user
from app.services import screener_mock

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/candidates")
async def list_candidates(
    industry: Optional[str] = Query(None, description="行业筛选"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="最低总分"),
):
    """候选列表（按 total_score 倒序）"""
    items = screener_mock.get_candidates(industry=industry, min_score=min_score)
    return {
        "total": len(items),
        "items": [
            {
                # 列表精简字段（避免 holders 大数组）
                "code": c["code"],
                "name": c["name"],
                "industry": c["industry"],
                "total_score": c["total_score"],
                "score_position": c["score_position"],
                "score_trend": c["score_trend"],
                "score_capital": c["score_capital"],
                "latest_price": c.get("latest_price"),
                "market_cap_wan_yi": c.get("market_cap_wan_yi"),
                "fund_count": c["capital"]["fund_count"],
                "pct_rank_1y": c["factors"]["pct_rank_1y"],
            }
            for c in items
        ],
    }


@router.get("/factors/{code}")
async def get_factors(code: str):
    """单只因子详情（含位置/趋势/主力资金/估值四组）"""
    data = screener_mock.get_factors(code)
    if not data:
        raise HTTPException(404, f"未找到 {code} 的因子数据")
    return data


@router.get("/holders/{code}")
async def get_holders(code: str):
    """单只重仓基金列表"""
    items = screener_mock.get_holders(code)
    if items is None:
        raise HTTPException(404, f"未找到 {code} 的持仓数据")
    return {
        "code": code,
        "items": items,
    }


@router.get("/industries")
async def list_industries():
    """候选行业列表（按出现顺序）"""
    return {"items": screener_mock.get_industries()}