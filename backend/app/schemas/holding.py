"""持仓 Schema"""
from typing import Optional, List
from pydantic import BaseModel


class HoldingOut(BaseModel):
    fund_code: str
    stock_code: str
    stock_name: Optional[str] = None
    report_date: str
    shares: Optional[float] = None
    market_value: Optional[float] = None
    ratio_net: Optional[float] = None
    rank: Optional[int] = None
    source: Optional[str] = None


class HoldingWithStock(HoldingOut):
    """持仓 + 股票信息 + 行情"""
    stock_industry: Optional[str] = None
    price: Optional[float] = None
    change_pct: Optional[float] = None


class SectorStockItem(BaseModel):
    code: str
    name: str
    industry_name: Optional[str] = None
    price: Optional[float] = None
    change_pct: Optional[float] = None
    fund_count: int = 0
    total_market_value: Optional[float] = None
    total_ratio: Optional[float] = None


class SectorGroupOut(BaseModel):
    industry_name: str
    stock_count: int
    avg_change_pct: Optional[float] = None
    total_market_value: Optional[float] = None
    stocks: List[SectorStockItem]


class SectorGroupedOut(BaseModel):
    total: int
    page: int
    page_size: int
    sectors: List[SectorGroupOut]
