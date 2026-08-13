"""基金 Schema"""
from typing import Optional, List
from pydantic import BaseModel


class FundOut(BaseModel):
    code: str
    name: str
    abbr: Optional[str] = None
    fund_type: Optional[str] = None
    nav: Optional[float] = None
    acc_nav: Optional[float] = None
    nav_date: Optional[str] = None
    scale_yi: Optional[float] = None
    ret_1m: Optional[float] = None
    ret_3m: Optional[float] = None
    ret_6m: Optional[float] = None
    ret_1y: Optional[float] = None
    ret_3y: Optional[float] = None
    ret_5y: Optional[float] = None
    ret_this_year: Optional[float] = None
    inception_date: Optional[str] = None
    manager: Optional[str] = None
    company: Optional[str] = None
    is_main: bool = False
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class FundListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[FundOut]
