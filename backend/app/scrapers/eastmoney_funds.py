"""东方财富基金排行抓取器"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class EastmoneyFundsScraper(BaseScraper):
    """基金排行数据（含规模/收益）"""
    BASE_URL = "https://fund.eastmoney.com/data/rankhandler.aspx"

    @staticmethod
    def _one_year_ago() -> str:
        d = datetime.now() - timedelta(days=365)
        return d.strftime("%Y-%m-%d")

    @staticmethod
    def _today() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    async def fetch_page(self, fund_type: str, page: int, page_size: int = 50) -> dict:
        """
        fund_type: 'gp' 股票型 / 'hh' 混合型 / 'zs' 指数型
        返回 {datas: [...], allRecords, allPages}
        """
        params = {
            "op": "ph",
            "dt": "kf",
            "ft": fund_type,
            "rs": "",
            "gs": "0",
            "sc": "1nzf",  # 近1年收益排序
            "st": "desc",
            "sd": self._one_year_ago(),
            "ed": self._today(),
            "qdii": "",
            "tabSubtype": ",,,,,",
            "pi": page,
            "pn": page_size,
            "dx": "1",
        }
        text = await self.get(
            self.BASE_URL,
            params=params,
            headers=self.eastmoney_headers("https://fund.eastmoney.com/data/fundranking.html"),
        )
        return self.parse_js_literal(text)

    async def fetch_all(self, fund_type: str, max_pages: int = 30) -> List[Dict[str, Any]]:
        """
        翻页拉取所有
        数据格式: "000001,华夏成长,HXCZ,2024-12-31,1.2345,2.3456,..."
        列索引参考（可能变化，按需调整）:
          0: code, 1: name, 2: abbr, 3: nav_date,
          4: nav, 5: acc_nav, 6: 涨跌幅(估算?) ...
        实际解析以东财最新返回为准，做了防御性 try
        """
        first = await self.fetch_page(fund_type, 1, page_size=50)
        all_pages = int(first.get("allPages", 1))
        all_pages = min(all_pages, max_pages)
        results: List[Dict[str, Any]] = []
        for p in range(1, all_pages + 1):
            data = await self.fetch_page(fund_type, p, page_size=50)
            for row in data.get("datas", []):
                parts = row.split(",")
                if len(parts) < 10:
                    continue
                try:
                    item = {
                        "code": parts[0].strip(),
                        "name": parts[1].strip(),
                        "abbr": parts[2].strip() if len(parts) > 2 else None,
                        "nav_date": parts[3].strip() if len(parts) > 3 else None,
                        "nav": self._f(parts, 4),
                        "acc_nav": self._f(parts, 5),
                        "ret_1m": self._f(parts, 8),
                        "ret_3m": self._f(parts, 9),
                        "ret_6m": self._f(parts, 10),
                        "ret_1y": self._f(parts, 11),
                        "ret_2y": self._f(parts, 12),
                        "ret_this_year": self._f(parts, 13),
                        "ret_3y": self._f(parts, 14),
                        "ret_5y": self._f(parts, 15),
                        "scale_yi": self._f(parts, 18),
                        "inception_date": parts[16].strip() if len(parts) > 16 else None,
                    }
                    results.append(item)
                except (ValueError, IndexError) as e:
                    logger.debug("跳过解析失败的行: %s err=%s", row[:80], e)
                    continue
            logger.info("[%s] 第 %d/%d 页，累计 %d 条", fund_type, p, all_pages, len(results))
        return results

    async def fetch_all_streaming(
        self,
        fund_type: str,
        max_pages: int = 30,
        on_batch=None,
        concurrency: int = 6,
    ):
        """
        流式抓取：每页解析完就调用 on_batch(items) 回调，便于分批入库

        - 第一页：取 allPages（必须同步，因为依赖第一页的结果决定后续页数）
        - 后续页：并发抓取（concurrency 控制并发数）
        """
        first = await self.fetch_page(fund_type, 1, page_size=50)
        all_pages = int(first.get("allPages", 1))
        all_pages = min(all_pages, max_pages)

        # 解析第一页（也算一页结果）
        all_items: List[Dict[str, Any]] = []
        first_items = self._parse_page_items(first, fund_type)
        all_items.extend(first_items)
        if on_batch and first_items:
            result = on_batch(first_items)
            if asyncio.iscoroutine(result):
                await result
        logger.info("[%s] 流式 第 1/%d 页，本页 %d 条，累计 %d", fund_type, all_pages, len(first_items), len(all_items))

        if all_pages <= 1:
            return all_items

        # 剩余页并发抓取
        sem = asyncio.Semaphore(concurrency)

        async def _fetch_one(p: int) -> List[Dict[str, Any]]:
            async with sem:
                try:
                    data = await self.fetch_page(fund_type, p, page_size=50)
                    return self._parse_page_items(data, fund_type)
                except Exception as e:
                    logger.warning("[%s] 第 %d 页抓取失败: %s", fund_type, p, e)
                    return []

        # 分批：concurrency 个并发，结果按页码顺序回写（便于日志输出 + 流式入库）
        for batch_start in range(2, all_pages + 1, concurrency * 4):
            batch_end = min(batch_start + concurrency * 4, all_pages + 1)
            page_nums = list(range(batch_start, batch_end))
            results = await asyncio.gather(*[_fetch_one(p) for p in page_nums])
            for p, items in zip(page_nums, results):
                all_items.extend(items)
                if on_batch and items:
                    result = on_batch(items)
                    if asyncio.iscoroutine(result):
                        await result
                logger.info("[%s] 流式 第 %d/%d 页，本页 %d 条，累计 %d", fund_type, p, all_pages, len(items), len(all_items))
        return all_items

    def _parse_page_items(self, data: Dict[str, Any], fund_type: str) -> List[Dict[str, Any]]:
        """解析单页数据为 items 列表（抽出共用于 streaming 和 batch）"""
        items = []
        for row in data.get("datas", []):
            parts = row.split(",")
            if len(parts) < 10:
                continue
            try:
                items.append({
                    "code": parts[0].strip(),
                    "name": parts[1].strip(),
                    "abbr": parts[2].strip() if len(parts) > 2 else None,
                    "nav_date": parts[3].strip() if len(parts) > 3 else None,
                    "nav": self._f(parts, 4),
                    "acc_nav": self._f(parts, 5),
                    "ret_1m": self._f(parts, 9),
                    "ret_3m": self._f(parts, 10),
                    "ret_6m": self._f(parts, 11),
                    "ret_1y": self._f(parts, 12),
                    "ret_3y": self._f(parts, 14),
                    "ret_5y": self._f(parts, 15),
                    "ret_this_year": self._f(parts, 8),
                    "scale_yi": self._f(parts, 18),
                    "inception_date": parts[16].strip() if len(parts) > 16 else None,
                    "fund_type": fund_type,  # gp/hh/zs 来自抓取参数
                })
            except (ValueError, IndexError):
                continue
        return items

    @staticmethod
    def _f(parts: list, idx: int) -> float:
        if idx >= len(parts):
            return 0.0
        try:
            v = parts[idx]
            if not v or v == "--" or v == "":
                return 0.0
            return float(v)
        except (ValueError, TypeError):
            return 0.0
