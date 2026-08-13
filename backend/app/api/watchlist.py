"""自选股 API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.deps import get_db
from app.services.watchlist_service import WatchlistService

router = APIRouter()


class AddBody(BaseModel):
    code: str
    name: Optional[str] = None
    note: str = ""


class UpdateBody(BaseModel):
    note: Optional[str] = None
    sort_order: Optional[int] = None


@router.get("")
async def list_watchlist(db: Session = Depends(get_db)):
    return WatchlistService.list_watchlist(db)


@router.post("")
async def add_watchlist(body: AddBody, db: Session = Depends(get_db)):
    try:
        item = WatchlistService.add_watchlist(db, body.code, body.name, body.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # 异步补 name + industry（如果还没有）
    from app.models.stock import Stock
    from app.models.watchlist import Watchlist
    s = db.query(Stock).filter(Stock.code == body.code).first()
    need_fetch = (not item.get("name") or item["name"] == body.code) or (s and not s.industry_name)
    if need_fetch:
        detail = await WatchlistService.resolve_detail(body.code)
        if detail:
            if detail.get("name"):
                item["name"] = detail["name"]
            if detail.get("industry"):
                item["industry_name"] = detail["industry"]
            if s:
                if detail.get("name"):
                    s.name = detail["name"]
                if detail.get("industry"):
                    s.industry_name = detail["industry"]
                if detail.get("market") is not None:
                    s.market = detail["market"]
                if detail.get("secid"):
                    s.secid = detail["secid"]
            w = db.query(Watchlist).filter(Watchlist.code == body.code).first()
            if w and detail.get("name"):
                w.name = detail["name"]
            db.commit()
    return item


@router.patch("/{code}")
async def update_watchlist(code: str, body: UpdateBody, db: Session = Depends(get_db)):
    try:
        return WatchlistService.update_watchlist(db, code, body.note, body.sort_order)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{code}")
async def remove_watchlist(code: str, db: Session = Depends(get_db)):
    ok = WatchlistService.remove_watchlist(db, code)
    if not ok:
        raise HTTPException(404, f"自选股 {code} 不存在")
    return {"ok": True}
