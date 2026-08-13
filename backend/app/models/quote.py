"""股票行情快照模型"""
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, PrimaryKeyConstraint, Index

from app.database import Base


class StockQuote(Base):
    """股票行情快照（每5分钟一条）"""
    __tablename__ = "stock_quote"

    code = Column(String(8), nullable=False, primary_key=True)
    snapshot_at = Column(String(20), nullable=False, primary_key=True, comment="ISO时间")
    price = Column(Float)
    change_pct = Column(Float)
    change_amt = Column(Float)
    volume = Column(Float, comment="成交量(手)")
    turnover = Column(Float, comment="成交额")
    turnover_rate = Column(Float, comment="换手率%")
    pe = Column(Float, comment="市盈率(动)")
    pb = Column(Float, comment="市净率")
    market_cap = Column(Float, comment="总市值(亿)")
    circ_market_cap = Column(Float, comment="流通市值(亿)")
    high = Column(Float)
    low = Column(Float)
    open_ = Column("open", Float)
    pre_close = Column(Float)

    __table_args__ = (
        Index("idx_quote_at", "snapshot_at"),
    )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "snapshot_at": self.snapshot_at,
            "price": self.price,
            "change_pct": self.change_pct,
            "change_amt": self.change_amt,
            "volume": self.volume,
            "turnover": self.turnover,
            "turnover_rate": self.turnover_rate,
            "pe": self.pe,
            "pb": self.pb,
            "market_cap": self.market_cap,
            "circ_market_cap": self.circ_market_cap,
            "high": self.high,
            "low": self.low,
            "open": self.open_,
            "pre_close": self.pre_close,
        }
