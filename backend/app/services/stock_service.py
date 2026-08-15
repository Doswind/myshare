"""股票业务层"""
import logging
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any

import httpx
from pypinyin import lazy_pinyin, Style
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.stock import Stock
from app.models.quote import StockQuote
from app.models.holding import FundHolding
from app.models.fund import Fund
from app.scrapers.stock_quotes import StockQuotesScraper
from app.scrapers.stock_detail import StockDetailScraper
from app.scrapers.sectors import SectorsScraper
from app.scrapers.base import ScrapeError

logger = logging.getLogger(__name__)

# 东方财富在线搜索接口（支持中文/拼音/代码）
EM_SEARCH_URL = "https://searchapi.eastmoney.com/api/suggest/get"
EM_TIMEOUT = 5.0


class StockService:
    """股票 + 行情业务"""

    @staticmethod
    def get_stock(db: Session, code: str) -> Optional[Dict]:
        s = db.query(Stock).filter(Stock.code == code).first()
        if not s:
            return None
        return s.to_dict()

    @staticmethod
    def search_stocks(db: Session, q: str, limit: int = 20) -> List[Dict]:
        """
        模糊搜索股票：
        - 6位数字 → 精确/前缀匹配代码
        - 纯字母 → 匹配拼音全拼或首字母（以 q 开头更优先，其次包含）
        - 其它（中文/混合）→ 匹配名称（LIKE '%q%'） + 代码前缀
        返回按相关度排序的列表
        """
        q = (q or "").strip()
        if not q:
            return []
        ql = q.lower()
        from sqlalchemy import or_, func

        # 1) 纯 6 位数字 → 走代码前缀
        if q.isdigit() and len(q) == 6:
            rows = (
                db.query(Stock)
                .filter(Stock.code.like(f"{q}%"))
                .order_by(Stock.code)
                .limit(limit)
                .all()
            )
            return [s.to_dict() for s in rows]

        # 2) 纯 ASCII 字母 → 走拼音
        # 注意：Python 的 str.isalpha() 对中文也返回 True，必须用 ascii 判定
        is_ascii_alpha = bool(ql) and all(c.isascii() and c.isalpha() for c in ql)
        if is_ascii_alpha:
            # 优先：首字母开头
            rows_pref = (
                db.query(Stock)
                .filter(Stock.pinyin_abbr.like(f"{ql}%"))
                .order_by(Stock.pinyin_abbr)
                .limit(limit)
                .all()
            )
            if len(rows_pref) >= limit:
                return [s.to_dict() for s in rows_pref]
            seen = {r.code for r in rows_pref}
            # 补充：首字母包含
            extra = (
                db.query(Stock)
                .filter(
                    Stock.pinyin_abbr.like(f"%{ql}%"),
                    ~Stock.code.in_(seen) if seen else True,
                )
                .order_by(Stock.pinyin_abbr)
                .limit(limit - len(rows_pref))
                .all()
            )
            rows_pref.extend(extra)
            seen = {r.code for r in rows_pref}
            # 补充：全拼包含
            extra2 = (
                db.query(Stock)
                .filter(
                    Stock.pinyin_full.like(f"%{ql}%"),
                    ~Stock.code.in_(seen) if seen else True,
                )
                .order_by(Stock.pinyin_full)
                .limit(limit - len(rows_pref))
                .all()
            )
            rows_pref.extend(extra2)
            return [s.to_dict() for s in rows_pref]

        # 3) 其它（中文 / 混合）→ 名称 LIKE + 代码前缀
        rows = (
            db.query(Stock)
            .filter(or_(Stock.name.like(f"%{q}%"), Stock.code.like(f"{q}%")))
            .order_by(
                # 名称以 q 开头优先
                Stock.name.like(f"{q}%").desc(),
                Stock.code,
            )
            .limit(limit)
            .all()
        )
        return [s.to_dict() for s in rows]

    @staticmethod
    async def _search_remote_em(q: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        东方财富在线搜索（支持中文/拼音/代码），不限本地表
        返回原始 item：{Code, Name, PinYin, QuoteID, ...}
        """
        try:
            async with httpx.AsyncClient(timeout=EM_TIMEOUT) as client:
                r = await client.get(
                    EM_SEARCH_URL,
                    params={"input": q, "type": 14, "count": limit},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                data = r.json()
                items = (data.get("QuotationCodeTable") or {}).get("Data") or []
                return [
                    {
                        "code": it.get("Code"),
                        "name": it.get("Name"),
                        "pinyin": (it.get("PinYin") or "").lower(),
                        "secid": it.get("QuoteID"),
                        "market_type": it.get("MarketType"),
                        "security_type": it.get("SecurityTypeName"),
                    }
                    for it in items
                    if it.get("Code") and it.get("Name")
                ]
        except Exception as e:
            logger.warning("东方财富在线搜索失败: %s", e)
            return []

    @staticmethod
    def _infer_market(code: str) -> int:
        """根据代码推断沪/深 (1=沪 / 0=深)"""
        c = (code or "").strip()
        if not c:
            return 0
        if c[0] in ("6", "9"):
            return 1
        if c[0] in ("0", "3"):
            return 0
        return 0

    @staticmethod
    def _compute_pinyin(name: str) -> tuple[str, str]:
        full = "".join(
            lazy_pinyin(name, style=Style.NORMAL, errors=lambda x: [list(x)[0]] if x else [])
        ).lower()
        abbr = "".join(
            lazy_pinyin(name, style=Style.FIRST_LETTER, errors=lambda x: list(x)[0] if x else "")
        ).lower()
        return full, abbr

    @classmethod
    def upsert_remote_stock(cls, db: Session, em_item: Dict[str, Any]) -> Optional[Stock]:
        """将东方财富的搜索结果同步到本地 stock 表（已存在则更新拼音/market）"""
        code = (em_item.get("code") or "").strip()
        name = (em_item.get("name") or "").strip()
        if not code or not name:
            return None
        s = db.query(Stock).filter(Stock.code == code).first()
        market = cls._infer_market(code)
        secid = em_item.get("secid") or f"{market}.{code}"
        full, abbr = cls._compute_pinyin(name)
        if s is None:
            s = Stock(
                code=code,
                name=name,
                market=market,
                secid=secid,
                pinyin_full=full,
                pinyin_abbr=abbr,
            )
            db.add(s)
            db.commit()
            db.refresh(s)
            logger.info("自选股同步：新增 stock %s %s", code, name)
        else:
            updated = False
            if s.pinyin_full != full:
                s.pinyin_full = full
                updated = True
            if s.pinyin_abbr != abbr:
                s.pinyin_abbr = abbr
                updated = True
            if updated:
                db.commit()
                db.refresh(s)
        return s

    @classmethod
    async def search_stocks_with_remote(
        cls, db: Session, q: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        先本地搜索；本地不足 limit 时回退到东方财富在线搜索
        同步补全本地没有的股票（写入 stock 表 + 拼音）
        """
        local = cls.search_stocks(db, q, limit=limit)
        if len(local) >= limit:
            return local
        remote_items = await cls._search_remote_em(q, limit=limit)
        if not remote_items:
            return local
        local_codes = {s["code"] for s in local}
        out: List[Dict[str, Any]] = list(local)
        for it in remote_items:
            code = it["code"]
            if code in local_codes:
                continue
            # 只取 6 位 A 股
            if not (code.isdigit() and len(code) == 6):
                continue
            s = cls.upsert_remote_stock(db, it)
            if s:
                out.append(s.to_dict())
                local_codes.add(code)
                if len(out) >= limit:
                    break
        return out

    @classmethod
    async def resolve_to_stock(cls, db: Session, q: str) -> Optional[Dict[str, Any]]:
        """
        把任意输入（代码/中文名/拼音）解析成一个 stock 字典
        - 本地有 → 返回本地
        - 本地无 → 在线搜索 + 入库
        - 都找不到 → 返回 None
        """
        q = (q or "").strip()
        if not q:
            return None
        local = cls.search_stocks(db, q, limit=1)
        if local:
            return local[0]
        remote_items = await cls._search_remote_em(q, limit=3)
        if not remote_items:
            return None
        ql = q.lower()
        for it in remote_items:
            code = it["code"]
            name = it["name"]
            py = it.get("pinyin", "")
            if q == code or ql == py or q == name:
                s = cls.upsert_remote_stock(db, it)
                return s.to_dict() if s else None
        s = cls.upsert_remote_stock(db, remote_items[0])
        return s.to_dict() if s else None

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
        """刷新当前基金持仓股票行情。

        codes=None 时只从当前保存基金的最新报告期持仓中取代码，
        不再把历史股票或其它来源的 stock 表记录混入本次抓取。
        """
        sq = StockQuotesScraper()
        try:
            if codes:
                items = await sq.fetch_batch(codes)
            else:
                # 从当前保存基金的最新报告期持仓读取代码
                from app.database import SessionLocal
                db_q = SessionLocal()
                try:
                    latest = (
                        db_q.query(FundHolding.report_date)
                        .join(Fund, Fund.code == FundHolding.fund_code)
                        .order_by(FundHolding.report_date.desc())
                        .first()
                    )
                    q = db_q.query(FundHolding.stock_code).join(
                        Fund, Fund.code == FundHolding.fund_code
                    )
                    if latest:
                        q = q.filter(FundHolding.report_date == latest[0])
                    codes = sorted({r[0] for r in q.distinct().all() if r[0]})
                finally:
                    db_q.close()
                if not codes:
                    return {"snapshots": 0}
                items = await sq.fetch_batch(codes)
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

            # 回填 stock.name（仅在本地为空时才用行情里的名称回填，避免覆写已有的更准名字）
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

        requested = set(codes or [])
        stored_codes = {row["code"] for row in quote_rows}
        return {
            "snapshots": len(quote_rows),
            "requested": len(requested),
            "missing": len(requested - stored_codes),
            "snapshot_at": snapshot_at,
        }

    @staticmethod
    def cleanup_old_quotes(db: Session, keep_days: int = 30) -> int:
        """清理 N 天前的行情"""
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d %H:%M:%S")
        affected = db.query(StockQuote).filter(StockQuote.snapshot_at < cutoff).delete(synchronize_session=False)
        db.commit()
        return affected

    @staticmethod
    async def refresh_stock_details(codes: List[str] = None, ttl_hours: int = 24) -> Dict:
        """回填当前基金持仓股票的 name / industry_name。

        codes=None 时以当前保存基金最新报告期持仓为范围；
        跳过本地已有完整信息且仍在 TTL 内的股票。
        """
        from datetime import datetime, timedelta
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            if codes is None:
                now = datetime.utcnow()
                cutoff = now - timedelta(hours=ttl_hours)
                # 已有完整信息且未过期的股票 → 跳过
                fresh = {
                    c for c, in db.query(Stock.code)
                    .filter(
                        Stock.industry_name.isnot(None),
                        Stock.industry_name != "",
                        Stock.details_fetched_at.isnot(None),
                        Stock.details_fetched_at >= cutoff,
                    )
                    .all()
                }
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
                holding_codes = {c for (c,) in q.distinct().all() if c}
                codes = sorted(holding_codes - fresh)
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
            now = datetime.utcnow()
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
                        details_fetched_at=now,
                    )
                    db.add(s)
                else:
                    if name and (not s.name or s.name == s.code):
                        s.name = name
                    if industry and not s.industry_name:
                        s.industry_name = industry
                    # 只要走了抓取就刷新时间，避免被反复选中
                    s.details_fetched_at = now
                n += 1
            db.commit()
        finally:
            db.close()
        return {"details": n}

    @staticmethod
    async def refresh_sectors_and_industries(
        codes: Optional[List[str]] = None,
        include_concepts: bool = False,
    ) -> Dict:
        """抓行业并回填指定持仓股票；概念板块默认保持现状。

        默认只维护当前保存基金最新报告期持仓股票的板块关系，
        避免把全市场成分股混入当前持仓数据。
        """
        sc = SectorsScraper()
        from app.database import SessionLocal
        from app.models.sector import Sector, SectorMember
        db = SessionLocal()
        try:
            if codes is None:
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
                codes = sorted({c for (c,) in q.distinct().all() if c})
            if not codes:
                return {"sectors": 0, "stock_mappings": 0}
            total_stocks = 0
            total_sectors = 0
            target_codes = set(codes)
            concept_map: Dict[str, set] = {}
            if target_codes:
                industry_sector_codes = {
                    code for (code,) in db.query(Sector.code).filter(
                        Sector.kind == "industry"
                    ).all()
                }
                db.query(SectorMember).filter(
                    SectorMember.stock_code.in_(target_codes),
                    SectorMember.sector_code.in_(industry_sector_codes),
                ).delete(synchronize_session=False)
            kinds = ("industry", "concept") if include_concepts else ("industry",)
            fetch_errors: Dict[str, str] = {}
            for kind in kinds:
                try:
                    sectors = await sc.fetch_all_with_members(kind)
                except Exception as e:
                    logger.error("抓 %s 板块失败: %s", kind, e)
                    fetch_errors[kind] = str(e)
                    continue
                for s in sectors:
                    code = s.get("code")
                    name = s.get("name")
                    if not code or not name:
                        continue
                    # upsert sector
                    row = db.query(Sector).filter(Sector.code == code).first()
                    if not row:
                        row = Sector(code=code, name=name, kind=kind, change_pct=s.get("change_pct"), lead_stock=s.get("lead_stock"))
                        db.add(row)
                    else:
                        row.name = name
                        row.kind = kind
                        row.change_pct = s.get("change_pct")
                        row.lead_stock = s.get("lead_stock")

                    # 全量模式重建板块成员；当前持仓模式只替换 target_codes，
                    # 不影响其它股票的板块关系。
                    if not target_codes:
                        db.query(SectorMember).filter(
                            SectorMember.sector_code == code
                        ).delete()

                    members = s.get("members", [])
                    member_codes = s.get("member_codes", [])
                    if target_codes:
                        members = [m for m in members if m.get("code") in target_codes]
                        member_codes = [m["code"] for m in members]
                    for mc in member_codes:
                        if not mc or len(mc) != 6:
                            continue
                        db.add(SectorMember(sector_code=code, stock_code=mc))

                    # 反向填充当前持仓股票的基础信息和主行业
                    if kind == "industry":
                        for member in members:
                            mc = member.get("code")
                            if not mc or len(mc) != 6:
                                continue
                            st = db.query(Stock).filter(Stock.code == mc).first()
                            if not st:
                                market = 1 if mc.startswith("6") else 0
                                st = Stock(
                                    code=mc,
                                    name=member.get("name") or mc,
                                    market=market,
                                    secid=f"{market}.{mc}",
                                )
                                db.add(st)
                            elif member.get("name") and (not st.name or st.name == st.code):
                                st.name = member["name"]
                            st.industry_code = code
                            st.industry_name = name
                    elif kind == "concept":
                        for mc in member_codes:
                            concept_map.setdefault(mc, set()).add(code)
                    total_sectors += 1
                    total_stocks += len(member_codes)
            if target_codes and include_concepts:
                for code in target_codes:
                    st = db.query(Stock).filter(Stock.code == code).first()
                    if st:
                        st.concept_codes = ",".join(sorted(concept_map.get(code, set())))
            # industry 是必需类型：抓取失败或一个板块都没拿到时如实报错
            # （在 commit 之前抛出，事务回滚，不会误删既有板块成员）
            if "industry" in kinds and (("industry" in fetch_errors) or total_sectors == 0):
                reason = fetch_errors.get("industry") or "未获取到任何行业板块数据"
                raise ScrapeError(f"行业板块抓取失败：{reason}")
            db.commit()
            return {"sectors": total_sectors, "stock_mappings": total_stocks}
        finally:
            db.close()
            await sc.close()
