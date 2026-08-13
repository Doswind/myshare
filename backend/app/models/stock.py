"""股票模型"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Index

from app.database import Base


class Stock(Base):
    """股票基本信息"""
    __tablename__ = "stock"

    code = Column(String(8), primary_key=True, comment="股票代码")
    name = Column(String(60), nullable=False, comment="股票名称")
    market = Column(Integer, nullable=False, default=0, comment="1沪/0深")
    secid = Column(String(16), comment="1.600519 / 0.000001")
    industry_code = Column(String(16), comment="行业板块代码 BK0xxx")
    industry_name = Column(String(40), comment="行业名称")
    concept_codes = Column(String(255), comment="概念板块代码列表(逗号分隔)")
    # 拼音相关字段：用于自选股的快速搜索
    pinyin_full = Column(String(120), comment="名称全拼（小写，无音调）")
    pinyin_abbr = Column(String(20), comment="名称首字母（小写）")
    # 详情抓取时间：用于 TTL 缓存，避免对已抓过的股票重复远程请求
    details_fetched_at = Column(DateTime, comment="详情(name/industry)最近一次远程抓取时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_stock_industry", "industry_code"),
        Index("idx_stock_industry_name", "industry_name"),
        Index("idx_stock_pinyin_abbr", "pinyin_abbr"),
        Index("idx_stock_pinyin_full", "pinyin_full"),
    )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "market": self.market,
            "secid": self.secid,
            "industry_code": self.industry_code,
            "industry_name": self.industry_name,
            "concept_codes": self.concept_codes.split(",") if self.concept_codes else [],
            "pinyin_full": self.pinyin_full or "",
            "pinyin_abbr": self.pinyin_abbr or "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
