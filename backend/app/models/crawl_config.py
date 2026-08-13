"""抓取策略配置模型

每个抓取任务（基金列表/净值/持仓/行情/行业/基金详情/股票详情）一行
用户可在 Settings 页面调整：开关 / 频率 / 时间窗口 / 仅交易日
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from app.database import Base


class CrawlConfig(Base):
    """抓取任务配置"""
    __tablename__ = "crawl_config"

    job_key = Column(String(40), primary_key=True, comment="稳定标识，如 funds_full / fund_nav / quotes / sectors / fund_details / stock_details")
    display_name = Column(String(60), nullable=False, comment="中文名（设置页展示）")
    # 触发类型：off=关闭 / daily=每天定点 / interval=按周期
    cron_type = Column(String(10), default="daily", comment="off / daily / interval")
    # interval 时使用
    interval_minutes = Column(Integer, default=5, comment="interval 模式下的周期（分钟）")
    # daily 时使用（HH:MM）
    time_of_day = Column(String(5), default="17:00", comment="daily 模式下的触发时间")
    # interval 时的运行窗口（HH:MM-HH:MM，留空=全天）
    window_start = Column(String(5), default="", comment="interval 窗口起点 HH:MM")
    window_end = Column(String(5), default="", comment="interval 窗口终点 HH:MM")
    # 是否仅 A 股交易日执行（interval 用得多）
    trading_only = Column(Boolean, default=False, comment="interval 时是否仅交易日执行")
    enabled = Column(Boolean, default=True, comment="总开关")
    description = Column(Text, default="", comment="说明文字（设置页展示）")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "job_key": self.job_key,
            "display_name": self.display_name,
            "cron_type": self.cron_type or "daily",
            "interval_minutes": self.interval_minutes or 5,
            "time_of_day": self.time_of_day or "17:00",
            "window_start": self.window_start or "",
            "window_end": self.window_end or "",
            "trading_only": bool(self.trading_only),
            "enabled": bool(self.enabled),
            "description": self.description or "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
