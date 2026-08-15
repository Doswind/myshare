"""日 K 历史行情 ORM 模型

两张表：
1. stock_kline_daily  —— 行情主表，每只股票每天一行 OHLCV
2. stock_kline_tracking —— 抓取游标表，每只股票一行（last_trade_date + 失败计数）

列名使用中文以直接对齐 AKShare stock_zh_a_hist() 返回的 DataFrame 列名，
避免每次插入时重命名（节省一次 map）。前端取数据时再做中文→英文映射。
"""
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Index, PrimaryKeyConstraint,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import Base


class StockKlineDaily(Base):
    """日 K 线历史（每只股票每天一行，前复权）"""
    __tablename__ = "stock_kline_daily"

    code = Column("代码", String(8), nullable=False, comment="6 位股票代码")
    trade_date = Column("日期", String(10), nullable=False, comment="YYYY-MM-DD")
    adjust = Column("复权", String(8), nullable=False, default="qfq", comment="qfq/hfq/none")

    open_ = Column("开盘", Float, nullable=False)
    high = Column("最高", Float, nullable=False)
    low = Column("最低", Float, nullable=False)
    close = Column("收盘", Float, nullable=False)
    volume = Column("成交量", Float, nullable=False, comment="手")
    amount = Column("成交额", Float, nullable=False, comment="元")

    amplitude = Column("振幅", Float, comment="%")
    change_pct = Column("涨跌幅", Float, comment="%")
    change_amt = Column("涨跌额", Float, comment="元")
    turnover_rate = Column("换手率", Float, comment="%")

    source = Column("数据源", String(16), nullable=False, default="akshare")
    fetched_at = Column("抓取时间", String(32), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("代码", "日期", "复权", name="pk_kline_daily"),
        Index("idx_kline_date", "日期"),
        Index("idx_kline_code_date", "代码", "日期"),
    )

    def to_dict(self) -> dict:
        return {
            "日期": self.trade_date,
            "开盘": self.open_,
            "最高": self.high,
            "最低": self.low,
            "收盘": self.close,
            "成交量": self.volume,
            "成交额": self.amount,
            "振幅": self.amplitude,
            "涨跌幅": self.change_pct,
            "涨跌额": self.change_amt,
            "换手率": self.turnover_rate,
        }


class StockKlineTracking(Base):
    """抓取游标：每只股票一行，记录"抓到哪里 + 失败状态"
    用于支撑首次全量 / 后续增量 / 失败暂停 的状态机。
    """
    __tablename__ = "stock_kline_tracking"

    code = Column(String(8), primary_key=True, comment="6 位股票代码")

    last_trade_date = Column(String(10), comment="最后成功抓到的交易日 YYYY-MM-DD")
    last_attempt_at = Column(String(32), comment="最后一次尝试时间 ISO8601")

    consecutive_failures = Column(Integer, default=0, comment="连续失败次数（达 5 paused）")
    paused = Column(Boolean, default=False, comment="是否暂停抓取")
    paused_reason = Column(String(40), comment="max_failures / delisted / manual")

    total_bars = Column(Integer, default=0, comment="累计入库条数")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_kline_tracking_paused", "paused"),
    )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "last_trade_date": self.last_trade_date,
            "last_attempt_at": self.last_attempt_at,
            "consecutive_failures": self.consecutive_failures,
            "paused": bool(self.paused),
            "paused_reason": self.paused_reason,
            "total_bars": self.total_bars or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


__all__ = ["StockKlineDaily", "StockKlineTracking"]