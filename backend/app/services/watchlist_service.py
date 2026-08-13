"""自选股业务层"""
import asyncio
import logging
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.watchlist import Watchlist
from app.models.stock import Stock
from app.models.quote import StockQuote
from app.models.holding import FundHolding
from app.models.fund import Fund
from app.scrapers.stock_detail import StockDetailScraper

logger = logging.getLogger(__name__)


class WatchlistService:
    """自选股管理 + 行情 + 基金关注度"""

    @staticmethod
    def _enrich(db: Session, w: Watchlist) -> Dict[str, Any]:
        """把 watchlist 行扩展为带行情和基金关注度的 dict"""
        code = w.code
        out = w.to_dict()

        # 行情
        q = (
            db.query(StockQuote)
            .filter(StockQuote.code == code)
            .order_by(StockQuote.snapshot_at.desc())
            .first()
        )
        if q:
            out["price"] = q.price
            out["change_pct"] = q.change_pct
            out["change_amt"] = q.change_amt
            out["pe"] = q.pe
            out["pb"] = q.pb
            out["market_cap"] = q.market_cap
            out["quote_at"] = q.snapshot_at
        else:
            out["price"] = None
            out["change_pct"] = None

        # 行业
        s = db.query(Stock).filter(Stock.code == code).first()
        out["industry_name"] = s.industry_name if s else None
        out["market"] = s.market if s else (1 if code.startswith(("5", "6", "9")) else 0)

        # 基金关注度：哪些主力基金重仓了
        latest = (
            db.query(FundHolding.report_date)
            .filter(FundHolding.stock_code == code)
            .order_by(FundHolding.report_date.desc())
            .first()
        )
        if latest:
            rd = latest[0]
            fund_count = (
                db.query(func.count(FundHolding.fund_code))
                .join(Fund, Fund.code == FundHolding.fund_code)
                .filter(
                    FundHolding.stock_code == code,
                    FundHolding.report_date == rd,
                    Fund.is_main == 1,
                )
                .scalar()
            ) or 0
            out["fund_count"] = int(fund_count)
            out["report_date"] = rd
        else:
            out["fund_count"] = 0
            out["report_date"] = None
        return out

    @staticmethod
    def list_watchlist(db: Session, user_id: int) -> List[Dict]:
        rows = (
            db.query(Watchlist)
            .filter(Watchlist.user_id == user_id)
            .order_by(Watchlist.sort_order.desc(), Watchlist.created_at.desc())
            .all()
        )
        return [WatchlistService._enrich(db, w) for w in rows]

    @staticmethod
    def add_watchlist(db: Session, user_id: int, code: str, name: Optional[str] = None, note: str = "") -> Dict:
        code = code.strip()
        if not code.isdigit() or len(code) != 6:
            raise ValueError("股票代码必须是 6 位数字")

        market = 1 if code.startswith(("5", "6", "9")) else 0
        secid = f"{market}.{code}"

        # 确保 stock 行存在
        s = db.query(Stock).filter(Stock.code == code).first()
        if not s:
            s = Stock(code=code, name=name or "", market=market, secid=secid)
            db.add(s)
            db.flush()
        elif name and (not s.name or s.name == code):
            s.name = name

        # watchlist 行（按 (user_id, code) 唯一）
        w = (
            db.query(Watchlist)
            .filter(Watchlist.user_id == user_id, Watchlist.code == code)
            .first()
        )
        if not w:
            w = Watchlist(user_id=user_id, code=code, name=s.name or name or "", note=note)
            db.add(w)
        else:
            if note:
                w.note = note
        db.commit()
        return WatchlistService._enrich(db, w)

    @staticmethod
    def update_watchlist(
        db: Session,
        user_id: int,
        code: str,
        note: Optional[str] = None,
        sort_order: Optional[int] = None,
    ) -> Dict:
        w = (
            db.query(Watchlist)
            .filter(Watchlist.user_id == user_id, Watchlist.code == code)
            .first()
        )
        if not w:
            raise ValueError(f"自选股 {code} 不存在")
        if note is not None:
            w.note = note
        if sort_order is not None:
            w.sort_order = sort_order
        db.commit()
        return WatchlistService._enrich(db, w)

    @staticmethod
    def remove_watchlist(db: Session, user_id: int, code: str) -> bool:
        w = (
            db.query(Watchlist)
            .filter(Watchlist.user_id == user_id, Watchlist.code == code)
            .first()
        )
        if not w:
            return False
        db.delete(w)
        db.commit()
        return True

    @staticmethod
    async def resolve_name(code: str) -> Optional[str]:
        """异步：从东财抓 name（添加时如果 stock 表没有就用这个补）"""
        sc = StockDetailScraper()
        try:
            item = await sc.fetch_one(code)
            if item and item.get("name"):
                return item["name"]
        except Exception as e:
            logger.warning("抓 %s 名称失败: %s", code, e)
        finally:
            await sc.close()
        return None

    @staticmethod
    async def resolve_detail(code: str) -> Optional[Dict[str, Any]]:
        """异步：从东财抓 name + industry（一次性）"""
        sc = StockDetailScraper()
        try:
            item = await sc.fetch_one(code)
            if item:
                return {
                    "name": item.get("name"),
                    "industry": item.get("industry"),
                    "industry_path": item.get("industry_path"),
                    "market": item.get("market"),
                    "secid": item.get("secid"),
                }
        except Exception as e:
            logger.warning("抓 %s 详情失败: %s", code, e)
        finally:
            await sc.close()
        return None
