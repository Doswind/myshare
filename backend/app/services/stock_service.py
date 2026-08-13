"""股票业务层"""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.stock import Stock
from app.models.quote import StockQuote
from app.models.holding import FundHolding
from app.models.fund import Fund
from app.scrapers.stock_quotes import StockQuotesScraper
from app.scrapers.stock_detail import StockDetailScraper
from app.scrapers.sectors import SectorsScraper

logger = logging.getLogger(__name__)


class StockService:
    """股票 + 行情业务"""

    @staticmethod
    def get_stock(db: Session, code: str) -> Optional[Dict]:
        s = db.query(Stock).filter(Stock.code == code).first()
        if not s:
            return None
        return s.to_dict()

    @staticmethod
    def get_latest_quote(db: Session, code: str) -> Optional[Dict]:
        q = (
            db.query(StockQuote)
            .filter(StockQuote.code == code)
            .order_by(StockQuote.snapshot_at.desc())
            .first()
        )
        if not q:
            return None
        return q.to_dict()

    @staticmethod
    def get_batch_latest_quotes(db: Session, codes: List[str]) -> Dict[str, Dict]:
        """批量获取最新行情"""
        if not codes:
            return {}
        # SQLite 子查询 + IN
        from sqlalchemy import func
        subq = (
            db.query(
                StockQuote.code,
                func.max(StockQuote.snapshot_at).label("max_at"),
            )
            .filter(StockQuote.code.in_(codes))
            .group_by(StockQuote.code)
            .subquery()
        )
        rows = (
            db.query(StockQuote)
            .join(subq, (StockQuote.code == subq.c.code) & (StockQuote.snapshot_at == subq.c.max_at))
            .all()
        )
        return {r.code: r.to_dict() for r in rows}

    @staticmethod
    def get_funds_holding_stock(db: Session, code: str) -> List[Dict]:
        """反向：哪些主力基金重仓了这只股票"""
        # 找最新一期
        latest = (
            db.query(FundHolding.report_date)
            .filter(FundHolding.stock_code == code)
            .order_by(FundHolding.report_date.desc())
            .first()
        )
        if not latest:
            return []
        report_date = latest[0]
        rows = (
            db.query(FundHolding, Fund)
            .join(Fund, Fund.code == FundHolding.fund_code)
            .filter(
                FundHolding.stock_code == code,
                FundHolding.report_date == report_date,
                Fund.is_main == 1,
            )
            .order_by(FundHolding.ratio_net.desc())
            .all()
        )
        out = []
        for h, f in rows:
            d = h.to_dict()
            d["fund_name"] = f.name
            d["fund_scale_yi"] = f.scale_yi
            d["fund_ret_1y"] = f.ret_1y
            out.append(d)
        return out

    @staticmethod
    async def refresh_quotes(codes: Optional[List[str]] = None) -> Dict:
        """刷新行情。codes=None 表示全 A 股

        同时回填 stock.name（行情里带的名称）
        """
        sq = StockQuotesScraper()
        try:
            if codes:
                items = await sq.fetch_batch(codes)
            else:
                items = await sq.fetch_all_market()
        finally:
            await sq.close()

        if not items:
            return {"snapshots": 0}

        from app.database import SessionLocal
        snapshot_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db = SessionLocal()
        try:
            quote_rows = []
            stock_updates = []  # [(code, name)]
            for it in items:
                if not it.get("code") or not it.get("price"):
                    continue
                # 异常值过滤
                price = it["price"]
                if price < 0.01 or price > 10000:
                    continue
                quote_rows.append({
                    "code": it["code"],
                    "snapshot_at": snapshot_at,
                    "price": it.get("price"),
                    "change_pct": it.get("change_pct"),
                    "change_amt": it.get("change_amt"),
                    "volume": it.get("volume"),
                    "turnover": it.get("turnover"),
                    "turnover_rate": it.get("turnover_rate"),
                    "pe": it.get("pe"),
                    "pb": it.get("pb"),
                    "market_cap": it.get("market_cap"),
                    "circ_market_cap": it.get("circ_market_cap"),
                    "high": it.get("high"),
                    "low": it.get("low"),
                    "pre_close": it.get("pre_close"),
                })
                if it.get("name"):
                    stock_updates.append((it["code"], it["name"]))
            # 批量插入行情
            db.bulk_insert_mappings(StockQuote, quote_rows)

            # 回填 stock.name
            if stock_updates:
                for code, name in stock_updates:
                    s = db.query(Stock).filter(Stock.code == code).first()
                    if s is None:
                        market = 1 if code.startswith(("5", "6", "9")) else 0
                        s = Stock(code=code, name=name, market=market, secid=f"{market}.{code}")
                        db.add(s)
                    elif not s.name or s.name == code:
                        s.name = name
            db.commit()
        finally:
            db.close()

        return {"snapshots": len(items), "snapshot_at": snapshot_at}

    @staticmethod
    def cleanup_old_quotes(db: Session, keep_days: int = 30) -> int:
        """清理 N 天前的行情"""
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d %H:%M:%S")
        affected = db.query(StockQuote).filter(StockQuote.snapshot_at < cutoff).delete(synchronize_session=False)
        db.commit()
        return affected

    @staticmethod
    async def refresh_stock_details(codes: List[str] = None) -> Dict:
        """回填 stock.name / industry_name（用 emweb 单股接口，push2 限流时也能用）"""
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            if codes is None:
                # 默认：所有有 holdings 的 + 库里没有 industry_name 的
                holding_codes = [c for (c,) in db.query(FundHolding.stock_code).distinct().all() if c]
                already = {
                    c for c, in db.query(Stock.code)
                    .filter(Stock.industry_name.isnot(None), Stock.industry_name != "")
                    .all()
                }
                codes = sorted(set(holding_codes) - already)
            if not codes:
                return {"details": 0}
        finally:
            db.close()

        sc = StockDetailScraper()
        try:
            items = await sc.fetch_batch(codes, concurrency=10)
        finally:
            await sc.close()

        db = SessionLocal()
        try:
            n = 0
            for it in items:
                code = it["code"]
                name = it.get("name")
                industry = it.get("industry")
                market = it.get("market")
                s = db.query(Stock).filter(Stock.code == code).first()
                if s is None:
                    s = Stock(
                        code=code,
                        name=name or code,
                        market=market,
                        secid=f"{market}.{code}",
                        industry_name=industry,
                    )
                    db.add(s)
                else:
                    if name and (not s.name or s.name == s.code):
                        s.name = name
                    if industry and not s.industry_name:
                        s.industry_name = industry
                n += 1
            db.commit()
        finally:
            db.close()
        return {"details": n}

    @staticmethod
    async def refresh_sectors_and_industries() -> Dict:
        """抓行业 + 概念板块 + 成分股，反向填充 stock.industry_*"""
        sc = SectorsScraper()
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            total_stocks = 0
            total_sectors = 0
            for kind in ("industry", "concept"):
                try:
                    sectors = await sc.fetch_all_with_members(kind)
                except Exception as e:
                    logger.error("抓 %s 板块失败: %s", kind, e)
                    continue
                for s in sectors:
                    code = s.get("code")
                    name = s.get("name")
                    if not code or not name:
                        continue
                    # upsert sector
                    from app.models.sector import Sector, SectorMember
                    row = db.query(Sector).filter(Sector.code == code).first()
                    if not row:
                        row = Sector(code=code, name=name, kind=kind, change_pct=s.get("change_pct"), lead_stock=s.get("lead_stock"))
                        db.add(row)
                    else:
                        row.name = name
                        row.kind = kind
                        row.change_pct = s.get("change_pct")
                        row.lead_stock = s.get("lead_stock")

                    # 清空旧成分股
                    db.query(SectorMember).filter(SectorMember.sector_code == code).delete()

                    member_codes = s.get("member_codes", [])
                    for mc in member_codes:
                        if not mc or len(mc) != 6:
                            continue
                        db.add(SectorMember(sector_code=code, stock_code=mc))

                    # 反向填充 stock（仅 industry）
                    if kind == "industry":
                        for mc in member_codes:
                            if not mc or len(mc) != 6:
                                continue
                            st = db.query(Stock).filter(Stock.code == mc).first()
                            if not st:
                                market = 1 if mc.startswith("6") else 0
                                st = Stock(code=mc, name="", market=market, secid=f"{market}.{mc}")
                                db.add(st)
                            # 取第一个行业为主行业
                            if not st.industry_name:
                                st.industry_code = code
                                st.industry_name = name
                    total_sectors += 1
                    total_stocks += len(member_codes)
                db.commit()
            return {"sectors": total_sectors, "stock_mappings": total_stocks}
        finally:
            db.close()
            await sc.close()
