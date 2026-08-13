"""基金模型"""
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Index

from app.database import Base


class Fund(Base):
    """基金基础信息 + 业绩指标"""
    __tablename__ = "fund"

    code = Column(String(8), primary_key=True, comment="6位基金代码")
    name = Column(String(120), nullable=False, comment="基金名称")
    abbr = Column(String(40), comment="拼音缩写")
    fund_type = Column(String(20), comment="gp/hh/zs/zq/qdii/lof")
    nav = Column(Float, comment="单位净值")
    acc_nav = Column(Float, comment="累计净值")
    nav_date = Column(String(10), comment="净值日期 YYYY-MM-DD")
    scale_yi = Column(Float, comment="资产规模(亿)")
    ret_1m = Column(Float, comment="近1月收益%")
    ret_3m = Column(Float, comment="近3月收益%")
    ret_6m = Column(Float, comment="近6月收益%")
    ret_1y = Column(Float, comment="近1年收益%")
    ret_3y = Column(Float, comment="近3年收益%")
    ret_5y = Column(Float, comment="近5年收益%")
    ret_this_year = Column(Float, comment="今年来收益%")
    inception_date = Column(String(10), comment="成立日期")
    manager = Column(String(40), comment="基金经理")
    company = Column(String(80), comment="基金公司")
    is_main = Column(Integer, default=0, comment="是否主力 0/1")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_fund_scale", "scale_yi"),
        Index("idx_fund_ret1y", "ret_1y"),
        Index("idx_fund_is_main", "is_main"),
        Index("idx_fund_type", "fund_type"),
    )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "abbr": self.abbr,
            "fund_type": self.fund_type,
            "nav": self.nav,
            "acc_nav": self.acc_nav,
            "nav_date": self.nav_date,
            "scale_yi": self.scale_yi,
            "ret_1m": self.ret_1m,
            "ret_3m": self.ret_3m,
            "ret_6m": self.ret_6m,
            "ret_1y": self.ret_1y,
            "ret_3y": self.ret_3y,
            "ret_5y": self.ret_5y,
            "ret_this_year": self.ret_this_year,
            "inception_date": self.inception_date,
            "manager": self.manager,
            "company": self.company,
            "is_main": bool(self.is_main),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
