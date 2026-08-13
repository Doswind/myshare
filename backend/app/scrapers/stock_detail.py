"""股票详情抓取（行业 / 所属板块）

使用 emweb.eastmoney.com 单独股票接口（push2 端点被 IP 限流时仍可用）
"""
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class StockDetailScraper(BaseScraper):
    """单只股票的行业 + 板块信息（不走 push2）"""
    DETAIL_URL = "https://emweb.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax"
    SECTORS_URL = "https://push2.eastmoney.com/api/qt/stock/get"

    async def fetch_one(self, code: str) -> Optional[Dict[str, Any]]:
        """拉一只股票的详情

        Returns:
            {
              code, name, industry_path (e.g. "金融-银行-股份制与城商行"),
              industry (一级行业, e.g. "金融"),
              market (1沪/0深)
            }
        """
        # 沪市 6/9/5，深市 0/3/1/2
        if code.startswith(("5", "6", "9")):
            secid = f"SH{code}"
            market = 1
        elif code.startswith(("4", "8")):
            secid = f"BJ{code}"
            market = 0
        else:
            secid = f"SZ{code}"
            market = 0

        client = await self._get_client()
        try:
            url = f"{self.DETAIL_URL}?code={secid}"
            resp = await client.get(
                url,
                headers={"Referer": "https://emweb.eastmoney.com/"},
            )
            if resp.status_code != 200 or not resp.text:
                return None
            data = json.loads(resp.text)
            jbzl = (data.get("jbzl") or [])
            if not jbzl:
                return None
            row = jbzl[0]
            name = row.get("SECURITY_NAME_ABBR") or row.get("STR_NAMEA")
            em_path = row.get("EM2016") or ""
            # EM2016 形如 "金融-银行-股份制与城商行"
            parts = [p for p in em_path.split("-") if p]
            industry = parts[0] if parts else None
            return {
                "code": code,
                "name": name,
                "industry": industry,
                "industry_path": em_path,
                "market": market,
                "secid": f"{market}.{code}",
            }
        except Exception as e:
            logger.debug("[detail] %s 失败: %s", code, e)
            return None

    async def fetch_batch(self, codes: List[str], concurrency: int = 8) -> List[Dict[str, Any]]:
        """并发拉一批（控制并发避免被封）"""
        sem = asyncio.Semaphore(concurrency)
        out: List[Dict[str, Any]] = []

        async def _one(code: str):
            async with sem:
                r = await self.fetch_one(code)
                if r:
                    out.append(r)
                await asyncio.sleep(0.05)

        await asyncio.gather(*[_one(c) for c in codes])
        return out
