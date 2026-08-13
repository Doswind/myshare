"""基金持仓模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Index, UniqueConstraint

from app.database import Base


class FundHolding(Base):
    """基金某报告期的持仓"""
    __tablename__ = "fund_holding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(8), nullable=False)
    report_date = Column(String(10), nullable=False, comment="YYYY-MM-DD")
    stock_code = Column(String(8), nullable=False)
    stock_name = Column(String(60))
    shares = Column(Float, comment="持股数(万股)")
    market_value = Column(Float, comment="持仓市值(万元)")
    ratio_net = Column(Float, comment="占净值比%")
    rank = Column(Integer, comment="第几大重仓 1-10")
    source = Column(String(20), default="archive", comment="archive/soft")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("fund_code", "report_date", "stock_code", name="uq_holding"),
        Index("idx_holding_fund", "fund_code"),
        Index("idx_holding_stock", "stock_code"),
        Index("idx_holding_report", "report_date"),
    )

    def to_dict(self) -> dict:
        return {
            "fund_code": self.fund_code,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "report_date": self.report_date,
            "shares": self.shares,
            "market_value": self.market_value,
            "ratio_net": self.ratio_net,
            "rank": self.rank,
            "source": self.source,
        }
