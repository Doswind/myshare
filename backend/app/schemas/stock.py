"""股票 Schema"""
from typing import Optional, List
from pydantic import BaseModel


class StockOut(BaseModel):
    code: str
    name: str
    market: int
    secid: Optional[str] = None
    industry_code: Optional[str] = None
    industry_name: Optional[str] = None
    concept_codes: List[str] = []
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class StockQuoteOut(BaseModel):
    code: str
    snapshot_at: str
    price: Optional[float] = None
    change_pct: Optional[float] = None
    change_amt: Optional[float] = None
    volume: Optional[float] = None
    turnover: Optional[float] = None
    turnover_rate: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    market_cap: Optional[float] = None
    circ_market_cap: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    pre_close: Optional[float] = None
