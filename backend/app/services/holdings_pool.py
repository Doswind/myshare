"""持仓池定义

K 线抓取的目标股票池 = 重仓股（FundHolding.stock_code 去重）
                      ∪ 全用户自选股（Watchlist.code 去重）

与「持仓股票行情」现有任务共用同一来源，避免重复定义。
"""
from typing import List

from sqlalchemy.orm import Session

from app.models.holding import FundHolding
from app.models.watchlist import Watchlist


def get_holdings_pool(db: Session) -> List[str]:
    """返回去重后的股票代码列表（按 code 升序）

    过滤规则：
    - 非空字符串
    - 6 位数字（A 股代码格式）
    """
    holding_codes = set(
        c for (c,) in db.query(FundHolding.stock_code).distinct().all()
        if c and c.strip()
    )
    watchlist_codes = set(
        c for (c,) in db.query(Watchlist.code).distinct().all()
        if c and c.strip()
    )
    merged = holding_codes | watchlist_codes
    # 仅保留 6 位数字代码（A 股）
    valid = sorted(c for c in merged if len(c) == 6 and c.isdigit())
    return valid


def get_holdings_pool_size(db: Session) -> int:
    """返回池大小（不加载完整列表）"""
    return len(get_holdings_pool(db))