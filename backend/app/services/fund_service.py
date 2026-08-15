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
from app.scrapers.fund_detail import FundDetailScraper
from app.config import settings
from app.database import SessionLocal

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
    def upsert_funds(db: Session, items: List[Dict], commit: bool = True) -> int:
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
        if commit:
            db.commit()
        return count

    @staticmethod
    def upsert_holdings(db: Session, rows: List[Dict], commit: bool = True) -> int:
        """批量 upsert 持仓（单条 executemany 方式，比逐条快 10 倍）"""
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        if not rows:
            return 0
        now = datetime.utcnow()
        # 统一补 updated_at
        for r in rows:
            r.setdefault("updated_at", now)
        stmt = sqlite_insert(FundHolding).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["fund_code", "report_date", "stock_code"],
            set_={
                "stock_name": stmt.excluded.stock_name,
                "shares": stmt.excluded.shares,
                "market_value": stmt.excluded.market_value,
                "ratio_net": stmt.excluded.ratio_net,
                "rank": stmt.excluded.rank,
                "source": stmt.excluded.source,
                "updated_at": now,
            },
        )
        db.execute(stmt)
        if commit:
            db.commit()
        return len(rows)

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
        """抓取并原子替换基金+最新持仓快照。

        远程抓取全部完成且没有失败后，才会清理旧基金、旧持仓并写入新快照；
        中途失败时保留旧数据，避免半套数据覆盖线上数据。
        """
        from app.database import SessionLocal
        from app.services.filter_service import FilterService
        saved_filters = FilterService.get()
        ms = min_scale if min_scale is not None else saved_filters["min_scale"]
        mr = min_ret_1y if min_ret_1y is not None else saved_filters["min_ret_1y"]
        logger.info("基金抓取阈值: 规模>=%s亿, 近1年>=%s%%", ms, mr)

        sc = EastmoneyFundsScraper()
        all_items: List[Dict] = []
        list_failures: List[str] = []
        for ft in FundService.FUND_TYPES:
            try:
                items = await sc.fetch_all_streaming(ft, max_pages=60, on_batch=None)
                all_items.extend(items)
                logger.info("[%s] 抓取完成，%d 条", ft, len(items))
            except Exception as e:
                logger.error("抓取 %s 类型基金失败: %s", ft, e)
                list_failures.append(f"{ft}: {e}")
        await sc.close()

        if list_failures or not all_items:
            raise RuntimeError(
                f"基金列表抓取不完整，保留旧数据: {', '.join(list_failures) or '没有返回数据'}"
            )

        filtered = [
            it for it in all_items
            if (it.get("scale_yi") or 0) >= ms and (it.get("ret_1y") or 0) >= mr
        ]
        filtered_by_code = {
            it["code"]: it for it in filtered
            if it.get("code") and str(it["code"]).isdigit()
        }
        filtered_codes = set(filtered_by_code)
        logger.info("抓取 %d 只基金，阈值过滤后 %d 只", len(all_items), len(filtered))

        if not filtered_codes:
            raise RuntimeError("阈值过滤后没有基金，保留旧数据")

        fh = FundHoldingsScraper()
        year, season = FundHoldingsScraper.latest_season()
        report_date = f"{year}-{season * 3:02d}"
        logger.info("持仓抓取季节: %s Q%d (%s)", year, season, report_date)

        try:
            holdings_map, failures = await fh.fetch_many_with_failures(
                sorted(filtered_codes), year, season, concurrency=15
            )
        finally:
            await fh.close()

        if failures:
            raise RuntimeError(
                f"持仓抓取失败 {len(failures)} 只，保留旧数据: {sorted(failures)[:10]}"
            )

        funds_to_store = [
            filtered_by_code[code] for code, rows in holdings_map.items() if rows
        ]
        new_codes = {it["code"] for it in funds_to_store}
        all_rows = [row for rows in holdings_map.values() for row in rows]
        if not new_codes or not all_rows:
            raise RuntimeError("过滤后的基金没有有效股票持仓，保留旧数据")

        logger.info("准备替换快照：基金 %d 只，持仓 %d 条", len(new_codes), len(all_rows))

        db = SessionLocal()
        try:
            # 显式清理，FundHolding 没有外键级联，不能依赖删除基金自动清理持仓。
            old_holdings = db.query(FundHolding).delete(synchronize_session=False)
            old_funds = db.query(Fund).delete(synchronize_session=False)

            stock_names = {
                r["stock_code"]: r.get("stock_name") or r["stock_code"]
                for r in all_rows if r.get("stock_code")
            }
            stock_codes = set(stock_names)
            for code in stock_codes:
                if len(code) != 6:
                    continue
                stock = db.query(Stock).filter(Stock.code == code).first()
                if not stock:
                    market = 1 if code.startswith(("5", "6", "9")) else 0
                    db.add(Stock(
                        code=code,
                        name=stock_names[code],
                        market=market,
                        secid=f"{market}.{code}",
                    ))
                elif not stock.name or stock.name == stock.code:
                    stock.name = stock_names[code]

            total_upserted = FundService.upsert_funds(db, funds_to_store, commit=False)
            total_holdings = FundService.upsert_holdings(db, all_rows, commit=False)
            db.commit()
            logger.info("旧快照已清理：基金 %d 只，持仓 %d 条", old_funds, old_holdings)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        return {
            "funds_upserted": total_upserted,
            "funds_in_db": len(new_codes),
            "holdings_upserted": total_holdings,
            "report_date": report_date,
        }

    @staticmethod
    async def refresh_all_holdings(concurrency: int = 15, batch_size: int = 500) -> int:
        """基于当前保存的基金列表，抓取并替换最新持仓快照。"""
        from app.database import SessionLocal
        fh = FundHoldingsScraper()
        year, season = FundHoldingsScraper.latest_season()
        report_date = f"{year}-{season * 3:02d}"
        logger.info("持仓抓取季节: %s Q%d (%s)", year, season, report_date)

        # 取全部基金代码
        db = SessionLocal()
        try:
            all_codes = [c for (c,) in db.query(Fund.code).all()]
        finally:
            db.close()

        if not all_codes:
            logger.warning("fund 表为空，跳过持仓抓取")
            await fh.close()
            return 0

        try:
            holdings_map, failures = await fh.fetch_many_with_failures(
                sorted(all_codes), year, season, concurrency=concurrency
            )
        finally:
            await fh.close()

        if failures:
            raise RuntimeError(
                f"持仓抓取失败 {len(failures)} 只，保留旧数据: {sorted(failures)[:10]}"
            )

        all_rows = [row for rows in holdings_map.values() for row in rows]
        funds_with_holdings = {code for code, rows in holdings_map.items() if rows}
        if not all_rows or not funds_with_holdings:
            raise RuntimeError("当前保存基金没有有效股票持仓，保留旧数据")

        db = SessionLocal()
        try:
            # 空持仓基金不再保留，基金详情任务自然只会处理剩余基金。
            db.query(Fund).filter(~Fund.code.in_(funds_with_holdings)).delete(
                synchronize_session=False
            )
            db.query(FundHolding).delete(synchronize_session=False)

            stock_names = {
                r["stock_code"]: r.get("stock_name") or r["stock_code"]
                for r in all_rows if r.get("stock_code")
            }
            stock_codes = set(stock_names)
            for code in stock_codes:
                if len(code) != 6:
                    continue
                stock = db.query(Stock).filter(Stock.code == code).first()
                if not stock:
                    market = 1 if code.startswith(("5", "6", "9")) else 0
                    db.add(Stock(
                        code=code,
                        name=stock_names[code],
                        market=market,
                        secid=f"{market}.{code}",
                    ))
                elif not stock.name or stock.name == stock.code:
                    stock.name = stock_names[code]

            total = FundService.upsert_holdings(db, all_rows, commit=False)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        codes = sorted({row["stock_code"] for row in all_rows if row.get("stock_code")})
        from app.services.stock_service import StockService
        await StockService.refresh_stock_details(codes, ttl_hours=0)
        await StockService.refresh_sectors_and_industries(codes)
        await StockService.refresh_quotes(codes)

        logger.info("持仓快照已替换：基金 %d 只，持仓 %d 条", len(funds_with_holdings), total)
        return total

    @staticmethod
    def get_current_holding_stock_codes() -> List[str]:
        """返回当前保存基金最新报告期的去重持仓股票代码。"""
        db = SessionLocal()
        try:
            latest = (
                db.query(FundHolding.report_date)
                .join(Fund, Fund.code == FundHolding.fund_code)
                .order_by(FundHolding.report_date.desc())
                .first()
            )
            q = db.query(FundHolding.stock_code).join(
                Fund, Fund.code == FundHolding.fund_code
            )
            if latest:
                q = q.filter(FundHolding.report_date == latest[0])
            return sorted({code for (code,) in q.distinct().all() if code})
        finally:
            db.close()

    @staticmethod
    async def refresh_full_pipeline() -> Dict[str, Any]:
        """按基金筛选策略完成基金、持仓、股票详情、板块和行情四步刷新。"""
        result = await FundService.refresh_all_funds()
        details = await FundService.refresh_fund_details()
        codes = FundService.get_current_holding_stock_codes()
        if not codes:
            raise RuntimeError("基金持仓为空，无法继续刷新股票数据")

        from app.services.stock_service import StockService
        stock_details = await StockService.refresh_stock_details(codes, ttl_hours=0)
        sectors = await StockService.refresh_sectors_and_industries(codes)
        quotes = await StockService.refresh_quotes(codes)
        return {
            **result,
            "fund_details": details,
            "stock_details": stock_details,
            "sectors": sectors,
            "quotes": quotes,
        }

    @staticmethod
    async def refresh_fund_details(codes: Optional[List[str]] = None, concurrency: int = 6) -> Dict[str, int]:
        """
        抓取基金详情（风险等级 / 评级 / 经理 / 管理人），更新 fund 表
        - codes: 指定要刷的基金代码列表；None = 刷所有
        """
        db: Session = SessionLocal()
        try:
            if codes is None:
                codes = [c for (c,) in db.query(Fund.code).all()]
            if not codes:
                return {"updated": 0, "total": 0}
            fd = FundDetailScraper()
            data_map = await fd.fetch_many(codes, concurrency=concurrency)
            updated = 0
            for code, item in data_map.items():
                f = db.query(Fund).filter(Fund.code == code).first()
                if not f:
                    continue
                for k, v in item.items():
                    if k in ("code",) or v is None or v == "":
                        continue
                    if hasattr(f, k):
                        setattr(f, k, v)
                updated += 1
                if updated % 50 == 0:
                    db.commit()
            db.commit()
            logger.info("基金详情刷新完成：%d / %d", updated, len(codes))
            return {"updated": updated, "total": len(codes)}
        finally:
            db.close()
