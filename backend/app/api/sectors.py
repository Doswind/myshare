"""行业 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.deps import get_db, get_current_user
from app.models.sector import Sector, SectorMember
from app.models.stock import Stock

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("")
async def list_sectors(db: Session = Depends(get_db)):
    rows = db.query(Sector).order_by(Sector.kind, Sector.code).all()
    return [s.to_dict() for s in rows]


@router.get("/by-industry")
async def list_industry_names(db: Session = Depends(get_db)):
    """从 stock 表去重行业名（更准确）"""
    rows = (
        db.query(Stock.industry_name)
        .filter(Stock.industry_name.isnot(None), Stock.industry_name != "")
        .distinct()
        .all()
    )
    return [{"name": r[0]} for r in rows if r[0]]


@router.get("/{code}/members")
async def sector_members(code: str, db: Session = Depends(get_db)):
    rows = (
        db.query(SectorMember, Stock)
        .outerjoin(Stock, Stock.code == SectorMember.stock_code)
        .filter(SectorMember.sector_code == code)
        .all()
    )
    return [
        {
            "code": m.stock_code,
            "name": s.name if s else None,
            "industry_code": s.industry_code if s else None,
        }
        for m, s in rows
    ]
