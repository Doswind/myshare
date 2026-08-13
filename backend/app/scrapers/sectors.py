"""行业/概念/地域板块 + 成分股抓取器"""
import asyncio
import logging
from typing import List, Dict

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class SectorsScraper(BaseScraper):
    """行业板块 + 成分股"""
    URL = "https://push2.eastmoney.com/api/qt/clist/get"

    async def list_sectors(self, kind: str = "industry") -> List[Dict]:
        """kind: industry/concept/region"""
        fs_map = {
            "industry": "m:90+t:2",
            "concept": "m:90+t:3",
            "region": "m:90+t:1",
        }
        fs = fs_map.get(kind, "m:90+t:2")
        params = {
            "pn": 1, "pz": 200, "po": 1, "np": 1,
            "ut": self.EAST_MONEY_UT,
            "fltt": 2, "invt": 2, "fid": "f3",
            "fs": fs,
            "fields": "f12,f14,f2,f3,f20,f128",
        }
        text = await self.get(self.URL, params=params)
        data = self.strip_jsonp(text)
        out = []
        for x in (data.get("data", {}).get("diff", []) or []):
            out.append({
                "code": x.get("f12"),
                "name": x.get("f14"),
                "change_pct": (x.get("f3") or 0) / 100 if x.get("f3") not in (None, "-") else 0,
                "lead_stock": x.get("f128"),
                "kind": kind,
            })
        return out

    async def list_members(self, sector_code: str, page_size: int = 500) -> List[Dict]:
        """板块成分股（含名称）"""
        out: List[Dict] = []
        page = 1
        while True:
            params = {
                "pn": page, "pz": page_size, "po": 1, "np": 1,
                "ut": self.EAST_MONEY_UT,
                "fltt": 2, "invt": 2, "fid": "f3",
                "fs": f"b:{sector_code}",
                "fields": "f12,f14,f2",
            }
            text = await self.get(self.URL, params=params)
            data = self.strip_jsonp(text)
            diff = data.get("data", {}).get("diff", []) or []
            if not diff:
                break
            for x in diff:
                out.append({
                    "code": str(x.get("f12")),
                    "name": x.get("f14"),
                })
            total = int(data.get("data", {}).get("total", 0))
            if page * page_size >= total or total == 0:
                break
            page += 1
            await asyncio.sleep(0.2)
        return out

    async def list_members_codes(self, sector_code: str) -> List[str]:
        """仅返回成分股代码列表"""
        rows = await self.list_members(sector_code)
        return [r["code"] for r in rows]

    async def fetch_all_with_members(self, kind: str = "industry") -> List[Dict]:
        """拉所有板块 + 成分股"""
        sectors = await self.list_sectors(kind)
        for s in sectors:
            try:
                members = await self.list_members(s["code"])
                s["member_count"] = len(members)
                s["member_codes"] = [m["code"] for m in members]
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.warning("拉 %s 成分股失败: %s", s["code"], e)
                s["member_count"] = 0
                s["member_codes"] = []
        return sectors
