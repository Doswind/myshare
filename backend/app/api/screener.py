"""选股分析 API（真实数据：主力资金 × 价格位置双榜）

GET /api/screener/candidates         — 两榜（进场 / 退场），各 Top 20
GET /api/screener/factors/{code}      — 单只完整因子（位置/趋势/主力资金）
GET /api/screener/holders/{code}      — 单只重仓基金列表（最新报告期）
GET /api/screener/industries          — 候选行业列表（用于筛选下拉）
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.services import screener_service

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/candidates")
async def list_candidates(db: Session = Depends(get_db)):
    """进场榜 / 退场榜（各 Top 20）。返回 {in, out, report_dates, data_as_of, note}"""
    return screener_service.get_boards(db)


@router.get("/factors/{code}")
async def get_factors(code: str, db: Session = Depends(get_db)):
    """单只因子详情（价格位置 / 趋势 / 主力资金）"""
    data = screener_service.get_factors(db, code)
    if not data:
        raise HTTPException(404, f"未找到 {code} 的数据（无持仓且无 K 线）")
    return data


@router.get("/holders/{code}")
async def get_holders(code: str, db: Session = Depends(get_db)):
    """单只重仓基金列表（最新报告期）"""
    return {"code": code, "items": screener_service.get_holders(db, code)}


@router.get("/industries")
async def list_industries(db: Session = Depends(get_db)):
    """候选行业列表"""
    return {"items": screener_service.get_industries(db)}
