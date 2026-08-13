"""通用 Schema"""
from typing import Optional
from pydantic import BaseModel


class JobLogOut(BaseModel):
    id: int
    job_id: str
    job_name: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: str
    items_processed: int = 0
    error_message: Optional[str] = None


class FilterDefaults(BaseModel):
    min_scale: float = 5.0
    min_ret_1y: float = 5.0
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    industry: Optional[str] = None


class TriggerResponse(BaseModel):
    job_id: str
    status: str
    message: str
