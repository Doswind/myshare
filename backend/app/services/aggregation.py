"""聚合服务：当前基金快照 → 行业板块 → 股票（核心）"""
import logging
from typing import Optional, Dict, Any, List
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, and_, or_

from app.models.fund import Fund
from app.models.holding import FundHolding
from app.models.stock import Stock
from app.models.quote import StockQuote

logger = logging.getLogger(__name__)


def classify_board(code: str) -> str:
    """
    A股板块识别（按代码前缀）
    - 沪主板: 600/601/603/605
    - 科创板: 688
    - 深主板: 000/001/002
    - 创业板: 300/301
    - 北交所: 8/9 开头
    """
    c = (code or "").strip()
    if not c:
        return "其它"
    if c.startswith(("600", "601", "603", "605")):
        return "沪主板"
    if c.startswith("688"):
        return "科创板"
    if c.startswith(("000", "001", "002")):
        return "深主板"
    if c.startswith(("300", "301")):
        return "创业板"
    if c.startswith(("8", "9", "43", "83", "87")):
        return "北交所"
    return "其它"


# 板块对应的代码前缀集合（用于 SQL LIKE 多选）
BOARD_PREFIXES: Dict[str, List[str]] = {
    "沪主板": ["600", "601", "603", "605"],
    "科创板": ["688"],
    "深主板": ["000", "001", "002"],
    "创业板": ["300", "301"],
    "北交所": ["8", "9", "43", "83", "87"],
}


class AggregationService:
    """核心聚合：按行业分组的、来自当前基金快照的股票列表"""

    @staticmethod
    def get_stocks_by_sector(
        db: Session,
        min_scale: float = 5.0,
        min_ret_1y: float = 5.0,
        industry_name: Optional[str] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        boards: Optional[List[str]] = None,
        page: int = 1,
        page_size: Optional[int] = None,
        sort_by: str = "fund_count",
        funded_only: bool = False,
    ) -> Dict[str, Any]:
        """
        返回结构：
        {
          total: 234, page, page_size,
          sectors: [
            { industry_name, stock_count, avg_change_pct, total_market_value,
              stocks: [{ code, name, price, change_pct, fund_count, total_market_value }] }
          ]
        }
        """
        # 1. 主力基金 code 集合
        main_subq = (
            db.query(Fund.code)
            .filter(Fund.scale_yi >= min_scale, Fund.ret_1y >= min_ret_1y)
            .subquery()
        )

        # 2. 最新一期报告日期（可能为 None：还没抓取过持仓）
        latest_date_row = (
            db.query(FundHolding.report_date)
            .filter(FundHolding.fund_code.in_(main_subq.select()))
            .order_by(FundHolding.report_date.desc())
            .first()
        )
        latest_date = latest_date_row[0] if latest_date_row else None

        # 3. 当前筛选基金最新报告期的持仓股票集合。
        #    看板必须以持仓为准，不能直接查询残留在 stock 表中的历史股票。
        holding_filters = [FundHolding.fund_code.in_(main_subq.select())]
        if latest_date:
            holding_filters.append(FundHolding.report_date == latest_date)
        holding_stocks_subq = (
            db.query(FundHolding.stock_code.label("code"))
            .filter(*holding_filters)
            .distinct()
            .subquery()
        )

        # 4. base 查询：当前持仓股票 + stock 元数据 + 最新行情。
        #    stock 元数据缺失时仍保留股票，行业统一归到“其它”。
        latest_quote_subq = (
            db.query(
                StockQuote.code,
                func.max(StockQuote.snapshot_at).label("max_at"),
            )
            .group_by(StockQuote.code)
            .subquery()
        )

        base = (
            db.query(
                holding_stocks_subq.c.code,
                Stock.name,
                Stock.industry_name,
                StockQuote.price,
                StockQuote.change_pct,
                StockQuote.market_cap,
            )
            .outerjoin(Stock, Stock.code == holding_stocks_subq.c.code)
            .outerjoin(
                latest_quote_subq,
                latest_quote_subq.c.code == holding_stocks_subq.c.code,
            )
            .outerjoin(
                StockQuote,
                and_(
                    StockQuote.code == holding_stocks_subq.c.code,
                    StockQuote.snapshot_at == latest_quote_subq.c.max_at,
                ),
            )
            .group_by(holding_stocks_subq.c.code, Stock.name, Stock.industry_name, StockQuote.price,
                      StockQuote.change_pct, StockQuote.market_cap)
        )

        if industry_name:
            if industry_name == "其它":
                base = base.filter(
                    or_(Stock.industry_name.is_(None), Stock.industry_name == "")
                )
            else:
                base = base.filter(Stock.industry_name == industry_name)
        if price_min is not None:
            base = base.filter(StockQuote.price >= price_min)
        if price_max is not None:
            base = base.filter(StockQuote.price <= price_max)
        if boards:
            # 板块过滤：按代码前缀的 LIKE 组合
            prefixes: List[str] = []
            for b in boards:
                prefixes.extend(BOARD_PREFIXES.get(b, []))
            if prefixes:
                base = base.filter(
                    or_(*[Stock.code.like(f"{p}%") for p in prefixes])
                )

        rows = base.all()
        if not rows:
            return {"total": 0, "page": page, "page_size": 0, "sectors": []}

        # 5. 内存聚合：按股票计算 fund_count / total_market_value
        stock_codes = [r.code for r in rows]
        agg_query = (
            db.query(
                FundHolding.stock_code,
                func.max(FundHolding.stock_name).label("holding_name"),
                func.count(distinct(FundHolding.fund_code)).label("fund_count"),
                func.sum(FundHolding.market_value).label("total_mv"),
                func.sum(FundHolding.ratio_net).label("total_ratio"),
            )
            .filter(
                FundHolding.fund_code.in_(main_subq.select()),
                FundHolding.stock_code.in_(stock_codes),
            )
        )
        if latest_date:
            agg_query = agg_query.filter(FundHolding.report_date == latest_date)
        agg_rows = agg_query.group_by(FundHolding.stock_code).all()
        agg_map = {
            r.stock_code: {
                "holding_name": r.holding_name,
                "fund_count": r.fund_count or 0,
                "total_market_value": r.total_mv or 0,
                "total_ratio": r.total_ratio or 0,
            }
            for r in agg_rows
        }

        # 6. 构造每只股票
        stock_list: List[Dict] = []
        for r in rows:
            agg = agg_map.get(r.code, {})
            stock_name = r.name if r.name and r.name != r.code else agg.get("holding_name")
            display_agg = {k: v for k, v in agg.items() if k != "holding_name"}
            stock_list.append({
                "code": r.code,
                "name": stock_name or r.code,
                "industry_name": r.industry_name or "其它",
                "board": classify_board(r.code),
                "price": r.price,
                "change_pct": r.change_pct,
                "market_cap": r.market_cap,
                **display_agg,
            })

        # 7. 排序
        if sort_by == "fund_count":
            stock_list.sort(key=lambda x: (-x.get("fund_count", 0), -(x.get("price") or 0)))
        elif sort_by == "change_pct":
            stock_list.sort(key=lambda x: -(x.get("change_pct") or -9999))
        elif sort_by == "total_market_value":
            stock_list.sort(key=lambda x: -(x.get("total_market_value") or 0))

        # 7.5 funded_only: 过滤掉无基金重仓的股票
        if funded_only:
            stock_list = [s for s in stock_list if (s.get("fund_count") or 0) > 0]

        # 8. 按行业分组
        grouped = defaultdict(list)
        for s in stock_list:
            grouped[s["industry_name"]].append(s)

        # 9. 排序行业
        sector_list = []
        for ind, stocks in grouped.items():
            valid_chg = [s["change_pct"] for s in stocks if s.get("change_pct") is not None]
            total_mv = sum(s.get("total_market_value") or 0 for s in stocks)
            funded = sum(1 for s in stocks if (s.get("fund_count") or 0) > 0)
            sector_list.append({
                "industry_name": ind,
                "stock_count": len(stocks),
                "funded_count": funded,
                "avg_change_pct": (sum(valid_chg) / len(valid_chg)) if valid_chg else None,
                "total_market_value": total_mv,
                "stocks": stocks,
            })
        sector_list.sort(key=lambda x: -x["total_market_value"])

        # 10. 分页（按行业级分页）
        total = len(stock_list)
        flat = [s for sect in sector_list for s in sect["stocks"]]
        if page_size is None:
            # 看板/股票列表默认返回完整结果，不依赖某个写死的上限。
            flat_paged = flat
            response_page_size = total
        else:
            start = (page - 1) * page_size
            end = start + page_size
            flat_paged = flat[start:end]
            response_page_size = page_size
        # 重新按行业聚合
        grouped2 = defaultdict(list)
        for s in flat_paged:
            grouped2[s["industry_name"]].append(s)
        paged_sectors = []
        for ind, stocks in grouped2.items():
            valid_chg = [s["change_pct"] for s in stocks if s.get("change_pct") is not None]
            total_mv = sum(s.get("total_market_value") or 0 for s in stocks)
            funded = sum(1 for s in stocks if (s.get("fund_count") or 0) > 0)
            paged_sectors.append({
                "industry_name": ind,
                "stock_count": len(stocks),
                "funded_count": funded,
                "avg_change_pct": (sum(valid_chg) / len(valid_chg)) if valid_chg else None,
                "total_market_value": total_mv,
                "stocks": stocks,
            })
        paged_sectors.sort(key=lambda x: -x["total_market_value"])

        return {
            "total": total,
            "page": page,
            "page_size": response_page_size,
            "sectors": paged_sectors,
            "report_date": latest_date,
        }
