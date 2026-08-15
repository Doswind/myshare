"""日 K 历史行情 Schema

字段命名沿用 AKShare stock_zh_a_hist() 返回的中文列名，便于直接透传 DataFrame。
"""
from typing import List, Optional

from pydantic import BaseModel


class KLineBar(BaseModel):
    """单根 K 线（对齐 AKShare 列名）"""
    日期: str                       # YYYY-MM-DD
    开盘: Optional[float] = None
    最高: Optional[float] = None
    最低: Optional[float] = None
    收盘: Optional[float] = None
    成交量: Optional[float] = None   # 手
    成交额: Optional[float] = None   # 元
    振幅: Optional[float] = None
    涨跌幅: Optional[float] = None
    涨跌额: Optional[float] = None
    换手率: Optional[float] = None


class KLineResponse(BaseModel):
    """K 线查询响应"""
    code: str
    adjust: str
    period: str                     # daily/weekly/monthly/yearly
    bars: List[KLineBar] = []
    data_as_of: Optional[str] = None   # 数据最后更新时间 ISO8601
    is_intraday: bool = False         # 当日是否未收盘
    source: str = "akshare"
    truncated: bool = False          # true 表示 DB 缺失最新数据


class KLineTrackingStatus(BaseModel):
    """单股抓取游标状态"""
    code: str
    last_trade_date: Optional[str] = None
    last_attempt_at: Optional[str] = None
    consecutive_failures: int = 0
    paused: bool = False
    paused_reason: Optional[str] = None
    total_bars: int = 0


class KLinePoolSummary(BaseModel):
    """全池抓取状态汇总"""
    total: int = 0                  # 总股票数
    paused: int = 0                 # 暂停数
    never_fetched: int = 0           # 从未抓取
    last_full_at: Optional[str] = None     # 最近一次全量任务完成时间
    last_incremental_at: Optional[str] = None  # 最近一次增量任务完成时间


class KLineJobRunResult(BaseModel):
    """抓取任务运行结果（用于 /jobs/kline/* 响应）"""
    status: str                     # "started"
    job_id: str
    log_id: int
    pool_size: int = 0              # 涉及的股票数
    full: bool = False              # 是否全量