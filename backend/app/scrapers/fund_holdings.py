"""基金重仓股抓取器"""
import re
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from lxml import etree

from app.scrapers.base import BaseScraper, ScrapeError

logger = logging.getLogger(__name__)


class FundHoldingsScraper(BaseScraper):
    """基金季报重仓股（前 10 大）"""
    URL = "https://fundf10.eastmoney.com/FundArchivesDatas.aspx"

    async def fetch(self, code: str, year: int, season: int) -> List[Dict[str, Any]]:
        """
        season: 1/2/3/4 -> 报告月份 3/6/9/12
        """
        month = season * 3
        params = {
            "type": "jjcc",
            "code": code,
            "topline": "10",
            "year": year,
            "month": f"{month:02d}",
        }
        text = await self.get(
            self.URL,
            params=params,
            headers={"Referer": f"https://fundf10.eastmoney.com/ccmx_{code}.html"},
        )
        return self._parse(text, code, f"{year}-{month:02d}")

    def _parse(self, text: str, fund_code: str, report_date: str) -> List[Dict[str, Any]]:
        # 提取 content:"..." 内的 HTML
        m = re.search(r'content:"(.*?)"\s*,', text, re.S)
        if not m:
            return []
        raw = m.group(1)
        if not raw.strip() or "<table" not in raw:
            return []
        # 仅当 content 里仍是字面量 \uXXXX（如 \u4e2d\u6587）时才解码；
        # 东方财富的 JSONP 返回的是真实 UTF-8 中文字符，直接用即可，
        # 否则 raw.encode("utf-8").decode("unicode_escape") 会把中文变成乱码
        if re.search(r"\\u[0-9a-fA-F]{4}", raw):
            try:
                html = raw.encode("utf-8").decode("unicode_escape")
            except UnicodeDecodeError:
                html = raw
        else:
            html = raw
        return self._parse_table(html, fund_code, report_date)

    @staticmethod
    def _parse_table(html: str, fund_code: str, report_date: str) -> List[Dict[str, Any]]:
        """
        解析基金持仓表。东方财富的实际列顺序：
        [0] 序号 [1] 股票代码 [2] 股票名称 [3] 最新价 [4] 涨跌幅
        [5] 相关资讯 [6] 占净值比例 [7] 持股数（万股） [8] 持仓市值（万元）

        同一份 JSONP 可能拼了两个季报（本季 + 上季），所以只取前 topline 条。
        """
        tree = etree.HTML(html)
        if tree is None:
            return []
        rows = tree.xpath("//table//tr[td]")
        out: List[Dict[str, Any]] = []
        rank = 0
        seen_codes: set = set()
        for tr in rows:
            if rank >= 10:
                break  # 只取前 10
            tds = tr.xpath("./td")
            if len(tds) < 9:
                continue
            first_text = "".join(tds[0].xpath(".//text()")).strip()
            if first_text in ("序号", ""):
                continue
            try:
                cells_text = ["".join(td.xpath(".//text()")).strip() for td in tds]
                stock_code = "".join(tds[1].xpath(".//a/text()") or tds[1].xpath(".//text()")).strip()
                stock_name = "".join(tds[2].xpath(".//a/text()") or tds[2].xpath(".//text()")).strip()
                if not re.match(r"^\d{6}$", stock_code):
                    m = re.search(r"\b(\d{6})\b", cells_text[1] if len(cells_text) > 1 else "")
                    if m:
                        stock_code = m.group(1)
                    else:
                        continue
                if not stock_name:
                    stock_name = cells_text[2] if len(cells_text) > 2 else stock_code
                # 关键修复：列号对应真实数据列
                ratio = FundHoldingsScraper._parse_num(cells_text, 6)   # 占净值比例 (%)
                shares = FundHoldingsScraper._parse_num(cells_text, 7)  # 持股数（万股）
                mv = FundHoldingsScraper._parse_num(cells_text, 8)      # 持仓市值（万元）
                if stock_code in seen_codes:
                    # 第二个季报的同支股票，跳过
                    continue
                seen_codes.add(stock_code)
                rank += 1
                out.append({
                    "fund_code": fund_code,
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "report_date": report_date,
                    "shares": shares,
                    "market_value": mv,
                    "ratio_net": ratio,
                    "rank": rank,
                    "source": "archive",
                })
            except Exception as e:
                logger.debug("解析行失败: %s err=%s", tds, e)
                continue
        return out

    @staticmethod
    def _parse_num(cells: list, idx: int) -> float:
        if idx >= len(cells):
            return 0.0
        txt = cells[idx].replace(",", "").replace("%", "").strip()
        if not txt or txt == "--":
            return 0.0
        try:
            return float(txt)
        except ValueError:
            return 0.0

    async def fetch_many(
        self,
        codes: List[str],
        year: int,
        season: int,
        concurrency: int = 8,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """并发抓取多只基金的持仓，保持旧接口只返回结果"""
        results, _ = await self.fetch_many_with_failures(codes, year, season, concurrency)
        return results

    async def fetch_many_with_failures(
        self,
        codes: List[str],
        year: int,
        season: int,
        concurrency: int = 8,
    ) -> tuple[Dict[str, List[Dict[str, Any]]], Dict[str, str]]:
        """并发抓取多只基金的持仓，同时保留失败基金，避免失败被当成空持仓"""
        sem = asyncio.Semaphore(concurrency)
        results: Dict[str, List[Dict[str, Any]]] = {}
        failures: Dict[str, str] = {}

        async def _one(code: str):
            async with sem:
                try:
                    data = await self.fetch(code, year, season)
                    results[code] = data
                except Exception as e:
                    logger.warning("抓取基金 %s 持仓失败: %s", code, e)
                    failures[code] = str(e)[:200]

        await asyncio.gather(*[_one(c) for c in codes])
        return results, failures

    @staticmethod
    def latest_season() -> tuple:
        """根据当前日期推断最新季报"""
        now = datetime.now()
        m = now.month
        y = now.year
        if m >= 11:
            return y, 3  # Q3 报告 10 月底披露
        if m >= 9:
            return y, 2  # Q2 报告 8 月底披露
        if m >= 5:
            return y, 1  # Q1 报告 4 月底披露
        return y - 1, 4  # 上年 Q4 报告 1 月底披露
