"""抓取器基类：限流 + 重试 + JSONP 剥离"""
import asyncio
import random
import re
import logging
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

logger = logging.getLogger(__name__)


class ScrapeError(Exception):
    pass


class BaseScraper:
    """所有抓取器继承此类"""

    BASE_HEADERS = {
        "User-Agent": settings.crawl_user_agent,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    EAST_MONEY_UT = "fa5fd1943c7b386f172d6893dbfba10b"
    DEFAULT_TIMEOUT = 15.0

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy or settings.crawl_proxy or None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.DEFAULT_TIMEOUT,
                headers=self.BASE_HEADERS.copy(),
                follow_redirects=True,
                proxy=self.proxy,
                trust_env=False,  # 禁用环境代理，避免连接被代理拦截
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, ScrapeError)),
        reraise=True,
    )
    async def get(self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> str:
        client = await self._get_client()
        merged_headers = {**client.headers, **(headers or {})}
        logger.debug("GET %s params=%s", url, params)
        resp = await client.get(url, params=params, headers=merged_headers)
        if resp.status_code != 200:
            raise ScrapeError(f"GET {url} status={resp.status_code}")
        await self._rate_limit()
        return resp.text

    async def _rate_limit(self, lo: float = 0.2, hi: float = 0.5):
        await asyncio.sleep(random.uniform(lo, hi))

    @staticmethod
    def strip_jsonp(text: str) -> dict:
        """去掉 jQueryxxx(...) 包装，得到 JSON"""
        import json
        m = re.search(r"\((.*)\)\s*;?\s*$", text.strip(), re.S)
        if m:
            return json.loads(m.group(1))
        return json.loads(text)

    @staticmethod
    def parse_js_literal(text: str) -> dict:
        """
        解析无引号 key 的 JS 字面量，例如 {datas: [...], allRecords: 123}
        """
        import json
        # 取出第一个 {...} 块
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ScrapeError(f"无法解析 JS 字面量: {text[:200]}")
        body = m.group(0)
        # 给 key 加双引号
        body = re.sub(r"([,{]\s*)([A-Za-z_]\w*)(\s*:)", r'\1"\2"\3', body)
        # 去掉可能的多余逗号
        body = re.sub(r",\s*}", "}", body)
        body = re.sub(r",\s*\]", "]", body)
        return json.loads(body)

    def eastmoney_headers(self, referer: str = "https://quote.eastmoney.com/") -> dict:
        return {
            "Referer": referer,
            "User-Agent": settings.crawl_user_agent,
        }
