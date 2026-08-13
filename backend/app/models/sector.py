"""行业板块模型"""
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, PrimaryKeyConstraint, Index

from app.database import Base


class Sector(Base):
    """行业/概念/地域板块"""
    __tablename__ = "sector"

    code = Column(String(12), primary_key=True, comment="BK0xxx")
    name = Column(String(40), nullable=False)
    kind = Column(String(20), default="industry", comment="industry/concept/region")
    change_pct = Column(Float, comment="板块涨跌幅%")
    lead_stock = Column(String(60), comment="领涨股名")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "kind": self.kind,
            "change_pct": self.change_pct,
            "lead_stock": self.lead_stock,
        }


class SectorMember(Base):
    """板块成分股"""
    __tablename__ = "sector_member"

    sector_code = Column(String(12), nullable=False, primary_key=True)
    stock_code = Column(String(8), nullable=False, primary_key=True)

    __table_args__ = (
        Index("idx_sector_member_stock", "stock_code"),
    )
