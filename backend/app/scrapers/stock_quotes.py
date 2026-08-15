"""股票行情批量抓取器

主数据源：东方财富 push2（批量高效）
备数据源：腾讯 qt.gtimg.cn（push2 被 IP 封锁时回退）
"""
import asyncio
import logging
import re
from typing import List, Dict, Any, Iterable, Optional

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class StockQuotesScraper(BaseScraper):
    """东方财富 push2 行情批量接口"""
    URL = "https://push2.eastmoney.com/api/qt/clist/get"
    FIELDS = "f12,f14,f2,f3,f4,f5,f6,f9,f10,f20,f21,f23,f116,f117,f168,f44,f45,f60,f47,f48"

    # 腾讯备数据源
    TENCENT_URL = "https://qt.gtimg.cn/q="

    async def fetch_batch(self, codes: List[str]) -> List[Dict[str, Any]]:
        """
        批量拉取指定股票代码的行情
        主：东方财富 push2
        备：腾讯 qt.gtimg.cn（push2 整体失败时回退）
        """
        if not codes:
            return []
        out: List[Dict[str, Any]] = []
        for chunk in self._chunks(codes, 80):
            try:
                items = await self._fetch_batch_eastmoney(chunk)
                out.extend(items)
                returned = {item["code"] for item in items}
                missing = [code for code in chunk if code not in returned]
                if missing:
                    logger.warning("[push2] %d 只股票未返回，回退腾讯补抓", len(missing))
                    out.extend(await self._fetch_batch_tencent(missing))
            except Exception as e:
                logger.warning("[push2] 批量行情失败，回退到腾讯: %s", e)
                items = await self._fetch_batch_tencent(chunk)
                out.extend(items)
            await asyncio.sleep(0.25)
        return out

    async def _fetch_batch_eastmoney(self, chunk: List[str]) -> List[Dict[str, Any]]:
        secids = ",".join(chunk)
        params = {
            "pn": 1,
            "pz": len(chunk),
            "po": 1,
            "np": 1,
            "ut": self.EAST_MONEY_UT,
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": secids,
            "fields": self.FIELDS,
        }
        text = await self.get(self.URL, params=params)
        data = self.strip_jsonp(text)
        diff = data.get("data", {}).get("diff", []) or []
        return [self._row_to_dict(row) for row in diff if self._row_to_dict(row)]

    async def _fetch_batch_tencent(self, chunk: List[str]) -> List[Dict[str, Any]]:
        """腾讯逐只股票（批量无明显接口，只能循环单只）"""
        out: List[Dict[str, Any]] = []
        client = await self._get_client()
        for code in chunk:
            try:
                # 沪市 sh, 深市 sz, 京 bj
                if code.startswith(("5", "6", "9")):
                    sec = f"sh{code}"
                elif code.startswith(("4", "8")):
                    sec = f"bj{code}"
                else:
                    sec = f"sz{code}"
                url = f"{self.TENCENT_URL}{sec}"
                resp = await client.get(
                    url,
                    headers={"Referer": "https://gu.qq.com/"},
                )
                if resp.status_code != 200 or not resp.text:
                    continue
                item = self._parse_tencent(resp.text)
                if item:
                    out.append(item)
                # 限流
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.debug("[tencent] %s 失败: %s", code, e)
                continue
        return out

    @staticmethod
    def _parse_tencent(text: str) -> Optional[Dict[str, Any]]:
        """
        腾讯 v_sz000063 / v_sh688012 返回格式（按 ~ 切分后的索引，已验证）：
          0=市场, 1=名称, 2=代码, 3=现价(元), 4=昨收, 5=今开, 6=成交量(手),
          31=涨跌额(元), 32=涨跌幅(%), 33=最高, 34=最低,
          36=成交量(手), 37=成交额(万元), 38=换手率(%), 39=市盈率(动),
          40=空, 41=最高(冗余), 42=最低(冗余), 43=振幅,
          44=流通市值(亿), 45=总市值(亿), 46=市净率, 47=涨停价, 48=跌停价
        """
        m = re.search(r'="(.*?)"', text)
        if not m:
            return None
        parts = m.group(1).split("~")
        if len(parts) < 49:
            return None
        try:
            def _f(idx, div=1.0):
                try:
                    v = float(parts[idx])
                    if v == 0:
                        return None
                    return v / div
                except (ValueError, IndexError):
                    return None

            return {
                "code": parts[2],
                "name": parts[1],
                "price": _f(3),
                "change_amt": _f(31),
                "change_pct": _f(32),
                "volume": _f(6, 10000),          # 手 → 万手
                "turnover": _f(37, 10000),        # 万元 → 亿元
                "turnover_rate": _f(38),
                "pe": _f(39),
                "pb": _f(46),
                "circ_market_cap": _f(44),
                "market_cap": _f(45),
                "high": _f(33),
                "low": _f(34),
                "pre_close": _f(4),
            }
        except (ValueError, IndexError) as e:
            logger.debug("parse tencent err: %s", e)
            return None

    async def fetch_all_market(self, market_filter: str = "m:0+t:6,m:1+t:2,m:1+t:23") -> List[Dict[str, Any]]:
        """拉全 A 股（沪深京）"""
        out: List[Dict[str, Any]] = []
        page_size = 100
        page = 1
        while True:
            params = {
                "pn": page,
                "pz": page_size,
                "po": 1,
                "np": 1,
                "ut": self.EAST_MONEY_UT,
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": market_filter,
                "fields": self.FIELDS,
            }
            text = await self.get(self.URL, params=params)
            data = self.strip_jsonp(text)
            diff = data.get("data", {}).get("diff", []) or []
            if not diff:
                break
            for row in diff:
                item = self._row_to_dict(row)
                if item:
                    out.append(item)
            total = int(data.get("data", {}).get("total", 0))
            if page * page_size >= total:
                break
            page += 1
            await asyncio.sleep(0.3)
        return out

    @staticmethod
    def _chunks(seq: Iterable, n: int):
        seq = list(seq)
        for i in range(0, len(seq), n):
            yield seq[i:i + n]

    @staticmethod
    def _row_to_dict(row: dict) -> Dict[str, Any]:
        """东方财富 row 转 dict，处理 /100、'-' 特殊值"""
        if not row or row.get("f12") in (None, "-"):
            return None

        def _v(k, div=1):
            v = row.get(k)
            if v in (None, "-", ""):
                return None
            try:
                v = float(v)
                if div != 1:
                    v = v / div
                return v
            except (ValueError, TypeError):
                return None

        return {
            "code": str(row.get("f12")),
            "name": row.get("f14"),
            "price": _v("f2", 100),
            "change_pct": _v("f3", 100),
            "change_amt": _v("f4", 100),
            "volume": _v("f5"),
            "turnover": _v("f6"),
            "pe": _v("f9", 100),
            "pb": _v("f23", 100),
            "market_cap": _v("f20"),
            "circ_market_cap": _v("f21"),
            "turnover_rate": _v("f168", 100),
            "high": _v("f44", 100),
            "low": _v("f45", 100),
            "pre_close": _v("f60", 100),
        }
