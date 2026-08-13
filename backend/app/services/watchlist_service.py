"""自选股业务层"""
import asyncio
import logging
from datetime import datetime, timedelta
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

# 详情抓取 TTL：24h 内认为本地详情有效，不再远程抓
DETAILS_TTL = timedelta(hours=24)
# 单只股票的远程抓取超时（防被卡住）
FETCH_TIMEOUT = 8.0


class WatchlistService:
    """自选股管理 + 行情 + 基金关注度"""

    # 按 code 维度分配锁，避免同一只股票被多用户/多次并发抓取
    _code_locks: Dict[str, asyncio.Lock] = {}
    _locks_guard = asyncio.Lock()

    @classmethod
    async def _get_code_lock(cls, code: str) -> asyncio.Lock:
        """惰性分配 per-code 锁，并定期清理空闲锁防止内存膨胀"""
        async with cls._locks_guard:
            lock = cls._code_locks.get(code)
            if lock is None:
                lock = asyncio.Lock()
                cls._code_locks[code] = lock
            # 清理：当字典过大时（>500），清理空闲锁
            if len(cls._code_locks) > 500:
                for k, v in list(cls._code_locks.items()):
                    if not v.locked():
                        cls._code_locks.pop(k, None)
            return lock

    @staticmethod
    def _enrich(db: Session, w: Watchlist) -> Dict[str, Any]:
        """把 watchlist 行扩展为带行情、股票基本信息、基金关注度的 dict
        名称 / 行业 / market 全部从 stock 表查（单一来源）"""
        code = w.code
        out = w.to_dict()

        # 股票基本信息（name / industry / market / secid）从 stock 表查
        s = db.query(Stock).filter(Stock.code == code).first()
        out["name"] = s.name if s else w.name  # 兜底用旧的 w.name（迁移期兼容）
        out["industry_name"] = s.industry_name if s else None
        out["market"] = s.market if s else (1 if code.startswith(("5", "6", "9")) else 0)
        out["secid"] = s.secid if s else f"{1 if code.startswith(('5','6','9')) else 0}.{code}"

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

        # 1) 确保 stock 行存在（共享表，跨用户复用）
        s = db.query(Stock).filter(Stock.code == code).first()
        if s is None:
            s = Stock(code=code, name=name or "", market=market, secid=secid)
            db.add(s)
            db.flush()
        elif name and (not s.name or s.name == code):
            s.name = name

        # 2) watchlist 行（只存映射 + 个性化字段，不存股票数据）
        w = (
            db.query(Watchlist)
            .filter(Watchlist.user_id == user_id, Watchlist.code == code)
            .first()
        )
        if not w:
            w = Watchlist(user_id=user_id, code=code, note=note)
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

    @classmethod
    async def resolve_name(cls, db: Session, code: str) -> Optional[str]:
        """异步：取股票名称
        1) 本地有 name 且非空 → 直接返回
        2) 本地无 / 失效 → 加 per-code 锁后远程抓
        """
        s = db.query(Stock).filter(Stock.code == code).first()
        if s and s.name and s.name != code:
            return s.name

        lock = await cls._get_code_lock(code)
        async with lock:
            # 双重检查：拿到锁后再查一次
            s = db.query(Stock).filter(Stock.code == code).first()
            if s and s.name and s.name != code:
                return s.name

            sc = StockDetailScraper()
            try:
                item = await asyncio.wait_for(sc.fetch_one(code), timeout=FETCH_TIMEOUT)
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("抓 %s 名称失败: %s", code, e)
                return None
            finally:
                await sc.close()

            if not item or not item.get("name"):
                return None

            name = item["name"]
            now = datetime.utcnow()
            if s is None:
                s = Stock(
                    code=code,
                    name=name,
                    market=item.get("market") or (1 if code.startswith(("5", "6", "9")) else 0),
                    secid=item.get("secid") or f"{1 if code.startswith(('5','6','9')) else 0}.{code}",
                    details_fetched_at=now,
                )
                db.add(s)
            else:
                s.name = name
                s.details_fetched_at = now
            db.commit()
            return name

    @classmethod
    async def resolve_detail(cls, db: Session, code: str) -> Optional[Dict[str, Any]]:
        """异步：取股票详情（name + industry + market + secid）
        1) 本地有完整信息（name 非空 + industry_name 非空）且未过 TTL → 直接返回
        2) 否则 → 加 per-code 锁后远程抓
        """
        s = db.query(Stock).filter(Stock.code == code).first()
        now = datetime.utcnow()
        if s and s.name and s.industry_name:
            fresh = s.details_fetched_at and (now - s.details_fetched_at) < DETAILS_TTL
            if fresh:
                return {
                    "name": s.name,
                    "industry": s.industry_name,
                    "industry_path": None,
                    "market": s.market,
                    "secid": s.secid,
                }

        lock = await cls._get_code_lock(code)
        async with lock:
            # 双重检查
            s = db.query(Stock).filter(Stock.code == code).first()
            if s and s.name and s.industry_name:
                fresh = s.details_fetched_at and (now - s.details_fetched_at) < DETAILS_TTL
                if fresh:
                    return {
                        "name": s.name,
                        "industry": s.industry_name,
                        "industry_path": None,
                        "market": s.market,
                        "secid": s.secid,
                    }

            sc = StockDetailScraper()
            try:
                item = await asyncio.wait_for(sc.fetch_one(code), timeout=FETCH_TIMEOUT)
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("抓 %s 详情失败: %s", code, e)
                return None
            finally:
                await sc.close()

            if not item:
                return None

            name = item.get("name")
            industry = item.get("industry")
            market = item.get("market")
            secid = item.get("secid")
            fetched_at = datetime.utcnow()
            if s is None:
                s = Stock(
                    code=code,
                    name=name or code,
                    market=market if market is not None else (1 if code.startswith(("5", "6", "9")) else 0),
                    secid=secid or f"{1 if code.startswith(('5','6','9')) else 0}.{code}",
                    industry_name=industry,
                    details_fetched_at=fetched_at,
                )
                db.add(s)
            else:
                if name and (not s.name or s.name == s.code):
                    s.name = name
                if industry and not s.industry_name:
                    s.industry_name = industry
                if market is not None:
                    s.market = market
                if secid:
                    s.secid = secid
                s.details_fetched_at = fetched_at
            db.commit()
            return {
                "name": s.name,
                "industry": s.industry_name,
                "industry_path": item.get("industry_path"),
                "market": s.market,
                "secid": s.secid,
            }
