"""抓取层"""
from app.scrapers.base import BaseScraper
from app.scrapers.eastmoney_funds import EastmoneyFundsScraper
from app.scrapers.fund_holdings import FundHoldingsScraper
from app.scrapers.fund_detail import FundDetailScraper
from app.scrapers.stock_quotes import StockQuotesScraper
from app.scrapers.sectors import SectorsScraper

__all__ = [
    "BaseScraper",
    "EastmoneyFundsScraper",
    "FundHoldingsScraper",
    "FundDetailScraper",
    "StockQuotesScraper",
    "SectorsScraper",
]
