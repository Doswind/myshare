"""基金业务层"""
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.fund import Fund
from app.models.holding import FundHolding
from app.models.sector import Sector
from app.models.stock import Stock
from app.scrapers.eastmoney_funds import EastmoneyFundsScraper
from app.scrapers.fund_holdings import FundHoldingsScraper
from app.config import settings

logger = logging.getLogger(__name__)


class FundService:
    """基金相关业务"""

    FUND_TYPES = ["gp", "hh", "zs"]  # 股票型/混合型/指数型

    @staticmethod
    def query_main_funds(
        db: Session,
        min_scale: float = 5.0,
        min_ret_1y: float = 5.0,
        fund_type: Optional[str] = None,
        sort: str = "ret_1y",
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """查询主力基金（按实时条件过滤）"""
        q = db.query(Fund).filter(
            Fund.scale_yi >= min_scale,
            Fund.ret_1y >= min_ret_1y,
        )
        if fund_type:
            q = q.filter(Fund.fund_type == fund_type)

        # 排序
        sort_col = getattr(Fund, sort, Fund.ret_1y)
        q = q.order_by(sort_col.desc())

        total = q.count()
        items = q.offset((page - 1) * page_size).limit(page_size).all()
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [f.to_dict() for f in items],
        }

    @staticmethod
    def get_fund_detail(db: Session, code: str) -> Optional[Dict]:
        fund = db.query(Fund).filter(Fund.code == code).first()
        if not fund:
            return None
        return fund.to_dict()

    @staticmethod
    def get_fund_holdings(db: Session, code: str, report_date: Optional[str] = None) -> List[Dict]:
        """某只基金最新一期持仓"""
        q = db.query(FundHolding).filter(FundHolding.fund_code == code)
        if report_date:
            q = q.filter(FundHolding.report_date == report_date)
        else:
            # 取最新一期
            latest = (
                db.query(FundHolding.report_date)
                .filter(FundHolding.fund_code == code)
                .order_by(FundHolding.report_date.desc())
                .first()
            )
            if latest:
                q = q.filter(FundHolding.report_date == latest[0])
        return [h.to_dict() for h in q.order_by(FundHolding.rank.asc()).all()]

    @staticmethod
    def upsert_funds(db: Session, items: List[Dict]) -> int:
        """批量 upsert 基金基础信息"""
        count = 0
        for it in items:
            code = it.get("code")
            if not code or not code.isdigit() or len(code) != 6:
                continue
            f = db.query(Fund).filter(Fund.code == code).first()
            if not f:
                f = Fund(code=code, name=it.get("name", ""))
                db.add(f)
            for k, v in it.items():
                if k == "code":
                    continue
                if hasattr(f, k):
                    setattr(f, k, v)
            count += 1
        db.commit()
        return count

    @staticmethod
    def upsert_holdings(db: Session, rows: List[Dict]) -> int:
        """批量 upsert 持仓"""
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        if not rows:
            return 0
        count = 0
        for r in rows:
            stmt = sqlite_insert(FundHolding).values(**r)
            stmt = stmt.on_conflict_do_update(
                index_elements=["fund_code", "report_date", "stock_code"],
                set_={
                    "stock_name": stmt.excluded.stock_name,
                    "shares": stmt.excluded.shares,
                    "market_value": stmt.excluded.market_value,
                    "ratio_net": stmt.excluded.ratio_net,
                    "rank": stmt.excluded.rank,
                    "source": stmt.excluded.source,
                    "updated_at": datetime.utcnow(),
                },
            )
            db.execute(stmt)
            count += 1
        db.commit()
        return count

    @staticmethod
    def recalc_main_flag(db: Session, min_scale: Optional[float] = None, min_ret_1y: Optional[float] = None, max_main: Optional[int] = None) -> int:
        """重算 is_main 标记

        规则: scale_yi >= min_scale AND ret_1y >= min_ret_1y
              按 ret_1y 降序取前 max_main 只基金标记为 is_main=1
        """
        ms = min_scale if min_scale is not None else settings.default_min_scale
        mr = min_ret_1y if min_ret_1y is not None else settings.default_min_ret_1y
        cap = max_main if max_main is not None else settings.max_main_funds
        # 重置
        db.query(Fund).update({Fund.is_main: 0})
        # 候选基金（按收益降序）
        candidates = (
            db.query(Fund.code)
            .filter(Fund.scale_yi >= ms, Fund.ret_1y >= mr)
            .order_by(Fund.ret_1y.desc())
            .limit(cap)
            .all()
        )
        codes = [c for (c,) in candidates]
        if not codes:
            db.commit()
            return 0
        affected = (
            db.query(Fund)
            .filter(Fund.code.in_(codes))
            .update({Fund.is_main: 1}, synchronize_session=False)
        )
        db.commit()
        return affected

    @staticmethod
    async def refresh_all_funds(min_scale: Optional[float] = None, min_ret_1y: Optional[float] = None) -> Dict:
        """拉所有基金 + 重算主力 + 抓持仓（流式，分批入库）"""
        from app.database import SessionLocal
        sc = EastmoneyFundsScraper()
        fh = FundHoldingsScraper()

        # 用流式抓取，每页直接入库
        db = SessionLocal()
        total_upserted = 0
        try:
            for ft in FundService.FUND_TYPES:
                def _on_batch_factory(ft_name):
                    def _cb(items):
                        nonlocal total_upserted
                        if items:
                            cnt = FundService.upsert_funds(db, items)
                            total_upserted += cnt
                    return _cb
                try:
                    items = await sc.fetch_all_streaming(ft, max_pages=60, on_batch=_on_batch_factory(ft))
                    logger.info("[%s] 流式抓取完成，共 %d 条", ft, len(items))
                except Exception as e:
                    logger.error("抓取 %s 类型基金失败: %s", ft, e)
        finally:
            db.close()
        await sc.close()

        # 重算主力
        db = SessionLocal()
        try:
            main_count = FundService.recalc_main_flag(db, min_scale, min_ret_1y)
        finally:
            db.close()

        # 抓主力基金最新季报持仓
        year, season = FundHoldingsScraper.latest_season()
        db = SessionLocal()
        try:
            main_codes = [c for (c,) in db.query(Fund.code).filter(Fund.is_main == 1).all()]
        finally:
            db.close()

        holdings_count = 0
        if main_codes:
            logger.info("开始抓 %d 只主力基金的持仓", len(main_codes))
            try:
                holdings_map = await fh.fetch_many(main_codes, year, season, concurrency=8)
                all_rows = []
                for code, rows in holdings_map.items():
                    all_rows.extend(rows)
                # 同步股票基础信息
                db = SessionLocal()
                try:
                    holdings_count = FundService.upsert_holdings(db, all_rows)
                    stock_codes = {r["stock_code"] for r in all_rows if r.get("stock_code")}
                    for sc_code in stock_codes:
                        if not sc_code or len(sc_code) != 6:
                            continue
                        s = db.query(Stock).filter(Stock.code == sc_code).first()
                        if not s:
                            market = 1 if sc_code.startswith("6") else 0
                            s = Stock(code=sc_code, name="", market=market, secid=f"{market}.{sc_code}")
                            db.add(s)
                    db.commit()
                finally:
                    db.close()
            except Exception as e:
                logger.error("并发抓取持仓失败: %s", e)
            await fh.close()

        return {
            "funds_upserted": total_upserted,
            "main_count": main_count,
            "main_funds_to_fetch": len(main_codes),
            "holdings_upserted": holdings_count,
            "year": year,
            "season": season,
        }
