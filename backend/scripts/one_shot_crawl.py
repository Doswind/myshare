"""一次性抓取脚本（手动）"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.fund_service import FundService
from app.services.stock_service import StockService


async def main():
    print("=== 抓取基金 + 持仓 ===")
    result = await FundService.refresh_all_funds()
    print("结果:", result)

    print("\n=== 抓取行业 + 成分股 ===")
    result2 = await StockService.refresh_sectors_and_industries()
    print("结果:", result2)

    print("\n=== 抓取持仓股票行情 ===")
    from app.database import SessionLocal
    from app.models.holding import FundHolding
    db = SessionLocal()
    try:
        codes = [c for (c,) in db.query(FundHolding.stock_code).distinct().all() if c]
    finally:
        db.close()
    print(f"持仓涉及 {len(codes)} 只股票")
    result3 = await StockService.refresh_quotes(codes)
    print("结果:", result3)


if __name__ == "__main__":
    asyncio.run(main())
