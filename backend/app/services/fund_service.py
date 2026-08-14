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
        """全量抓取基金列表 → 按阈值过滤入库 → 抓持仓

        流程：
        1. 抓取东方财富全部基金（3类型，每类最多60页）
        2. 按阈值过滤（scale_yi >= min_scale AND ret_1y >= min_ret_1y）
        3. 先抓到新数据后，清除 fund 表中不再满足阈值的旧基金
        4. 抓取 fund 表中全部基金的持仓
        """
        from app.database import SessionLocal
        ms = min_scale if min_scale is not None else settings.default_min_scale
        mr = min_ret_1y if min_ret_1y is not None else settings.default_min_ret_1y
        logger.info("基金抓取阈值: 规模>=%s亿, 近1年>=%s%%", ms, mr)

        sc = EastmoneyFundsScraper()

        # 1. 流式抓取全部基金，先存到内存
        all_items: List[Dict] = []
        for ft in FundService.FUND_TYPES:
            try:
                items = await sc.fetch_all_streaming(ft, max_pages=60, on_batch=None)
                all_items.extend(items)
                logger.info("[%s] 抓取完成，%d 条", ft, len(items))
            except Exception as e:
                logger.error("抓取 %s 类型基金失败: %s", ft, e)
        await sc.close()

        if not all_items:
            logger.error("未抓到任何基金数据，跳过入库")
            return {"funds_upserted": 0, "holdings_upserted": 0}

        # 2. 按阈值过滤
        filtered = [
            it for it in all_items
            if (it.get("scale_yi") or 0) >= ms and (it.get("ret_1y") or 0) >= mr
        ]
        new_codes = {it["code"] for it in filtered if it.get("code")}
        logger.info("抓取 %d 只基金，阈值过滤后 %d 只", len(all_items), len(filtered))

        # 3. 安全替换：先入库新数据，再删除不再满足阈值的旧基金
        db = SessionLocal()
        total_upserted = 0
        try:
            total_upserted = FundService.upsert_funds(db, filtered)

            # 删除不再满足阈值的旧基金（新数据已入库，安全清除）
            if new_codes:
                old_funds = db.query(Fund).filter(~Fund.code.in_(new_codes)).all()
                for f in old_funds:
                    db.delete(f)
                if old_funds:
                    logger.info("清除 %d 只不再满足阈值的旧基金", len(old_funds))
                    db.commit()
        finally:
            db.close()

        # 4. 抓持仓（用 fund 表中的全部基金）
        holdings_count = await FundService.refresh_all_holdings()

        return {
            "funds_upserted": total_upserted,
            "funds_in_db": len(new_codes),
            "holdings_upserted": holdings_count,
        }

    @staticmethod
    async def refresh_all_holdings(concurrency: int = 30, batch_size: int = 500) -> int:
        """单独抓全部基金最新季报持仓（分批并发，分批入库）

        优化：
        - 并发 30（原 15），东财可承受
        - 增量跳过：已有当季持仓的基金不重复抓（季报数据季度内不变）
        - 批量写入：upsert_holdings 已改为 executemany
        - 跨季度自动全量：latest_season() 返回新 year/season 时，旧数据不匹配，自然全量重抓
        """
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

        # 增量：跳过已有当季持仓的基金
        db = SessionLocal()
        try:
            existing_codes = set(
                c for (c,) in db.query(FundHolding.fund_code)
                .filter(FundHolding.report_date == report_date)
                .distinct()
                .all()
            )
        finally:
            db.close()

        to_fetch = [c for c in all_codes if c not in existing_codes]
        skipped = len(all_codes) - len(to_fetch)
        logger.info("持仓抓取: 共 %d 只基金，已抓 %d 只（跳过），需抓 %d 只",
                    len(all_codes), skipped, len(to_fetch))

        if not to_fetch:
            logger.info("全部基金当季持仓已存在，无需抓取")
            await fh.close()
            return 0

        total_holdings = 0
        total_batches = (len(to_fetch) + batch_size - 1) // batch_size
        logger.info("开始抓 %d 只基金的持仓，分 %d 批（每批 %d，并发 %d）",
                    len(to_fetch), total_batches, batch_size, concurrency)

        try:
            for i in range(0, len(to_fetch), batch_size):
                batch = to_fetch[i:i + batch_size]
                batch_num = i // batch_size + 1
                holdings_map = await fh.fetch_many(batch, year, season, concurrency=concurrency)

                all_rows = []
                for code, rows in holdings_map.items():
                    all_rows.extend(rows)

                # 入库 + 同步股票基础信息
                db = SessionLocal()
                try:
                    cnt = FundService.upsert_holdings(db, all_rows)
                    total_holdings += cnt

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

                logger.info("持仓抓取进度: %d/%d 批 (基金 %d-%d/%d)，本批 %d 条持仓",
                            batch_num, total_batches, i + 1, min(i + batch_size, len(to_fetch)),
                            len(to_fetch), len(all_rows))
        except Exception as e:
            logger.error("持仓抓取失败: %s", e)
        finally:
            await fh.close()

        logger.info("持仓抓取完成: 新增 %d 条持仓（抓取 %d 只，跳过 %d 只）",
                    total_holdings, len(to_fetch), skipped)
        return total_holdings

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
