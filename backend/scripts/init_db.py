"""初始化数据库（建表）"""
import sys
from pathlib import Path

# 让脚本可以独立运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine, Base
from app.models import Fund, FundHolding, Stock, Sector, SectorMember, StockQuote, JobLog  # noqa


def init():
    print(f"DB: {engine.url}")
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表已创建")


if __name__ == "__main__":
    init()
