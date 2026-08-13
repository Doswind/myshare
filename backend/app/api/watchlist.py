"""自选股 API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.deps import get_db, get_current_user
from app.models.rbac import User
from app.services.watchlist_service import WatchlistService

router = APIRouter(dependencies=[Depends(get_current_user)])


class AddBody(BaseModel):
    code: str  # 也可作为 q（中文/拼音首字母），后端会自动解析
    name: Optional[str] = None
    note: str = ""


class UpdateBody(BaseModel):
    note: Optional[str] = None
    sort_order: Optional[int] = None


@router.get("")
async def list_watchlist(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return WatchlistService.list_watchlist(db, user.id)


@router.post("")
async def add_watchlist(
    body: AddBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """添加自选股：code 字段可以是 6 位代码 / 中文名 / 拼音首字母
    本地找不到时自动从东方财富在线搜索 + 入库"""
    from app.models.stock import Stock
    from app.services.stock_service import StockService

    raw = (body.code or "").strip()
    if not raw:
        raise HTTPException(400, "code 不能为空")

    # 走 resolve_to_stock：本地+在线搜索（找不到时自动入库）
    s = await StockService.resolve_to_stock(db, raw)
    if not s:
        raise HTTPException(404, f"找不到股票：{raw}")
    resolved_code = s["code"]
    resolved_name = s["name"] or body.name

    try:
        item = WatchlistService.add_watchlist(db, user.id, resolved_code, resolved_name, body.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # 异步补 industry（如果还没有）
    s_row = db.query(Stock).filter(Stock.code == resolved_code).first()
    need_fetch = (s_row and not s_row.industry_name)
    if need_fetch:
        detail = await WatchlistService.resolve_detail(resolved_code)
        if detail:
            if detail.get("industry"):
                item["industry_name"] = detail["industry"]
            if s_row and detail.get("industry"):
                s_row.industry_name = detail["industry"]
                if detail.get("market") is not None:
                    s_row.market = detail["market"]
                if detail.get("secid"):
                    s_row.secid = detail["secid"]
                db.commit()
    return item


@router.patch("/{code}")
async def update_watchlist(
    code: str,
    body: UpdateBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return WatchlistService.update_watchlist(db, user.id, code, body.note, body.sort_order)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{code}")
async def remove_watchlist(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ok = WatchlistService.remove_watchlist(db, user.id, code)
    if not ok:
        raise HTTPException(404, f"自选股 {code} 不存在")
    return {"ok": True}
