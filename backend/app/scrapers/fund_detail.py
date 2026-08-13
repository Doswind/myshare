"""基金详情抓取：风险等级、基金评级、基金经理、基金公司、规模

数据源：
- http://fund.eastmoney.com/{code}.html （风险等级 + 评级）
- https://fundf10.eastmoney.com/jbgk_{code}.html （经理 / 管理人 / 成立日期 / 规模）
"""
import re
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from lxml import etree

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# 注意：顺序很重要，更长的模式必须排在前面（避免 "高风险" 吞掉 "中高风险"）
RISK_LEVELS = ("中高风险", "中低风险", "中风险", "高风险", "低风险")


class FundDetailScraper(BaseScraper):
    """单只基金的详情（风险等级 / 评级 / 经理 / 管理人）"""

    MAIN_URL = "http://fund.eastmoney.com/{code}.html"
    F10_URL = "https://fundf10.eastmoney.com/jbgk_{code}.html"
    # 业绩/净值/规模（从已抓到的 F10 也能解析）

    async def fetch_one(self, code: str) -> Dict[str, Any]:
        """抓取单只基金的全部详情字段"""
        code = code.strip()
        out: Dict[str, Any] = {"code": code}

        # 1) 主页：风险等级 + 评级
        try:
            main_text = await self.get(
                self.MAIN_URL.format(code=code),
                headers={"Referer": "https://fund.eastmoney.com/"},
            )
            out.update(self._parse_main(main_text))
        except Exception as e:
            logger.warning("抓取基金主页 %s 失败: %s", code, e)

        # 2) F10：经理 / 管理人 / 成立日期 / 规模
        try:
            f10_text = await self.get(
                self.F10_URL.format(code=code),
                headers={"Referer": "https://fundf10.eastmoney.com/"},
            )
            out.update(self._parse_f10(f10_text))
        except Exception as e:
            logger.warning("抓取基金 F10 %s 失败: %s", code, e)

        return out

    @staticmethod
    def _parse_main(html: str) -> Dict[str, Any]:
        """
        从 http://fund.eastmoney.com/{code}.html 提取：
        - 风险等级（中高风险/中风险/中低风险/低风险/高风险）
        - 评级（晨星评级，最近一次）
        """
        out: Dict[str, Any] = {}
        # 风险等级：匹配 "中高风险 / 中风险 / 中低风险 / 低风险 / 高风险"
        # 在主页里出现在 "类型：X | 风险" 这一行（被 &nbsp;|&nbsp; 隔开）
        for risk in RISK_LEVELS:
            # 用包含关系匹配，并限制在 "类型" 上下文附近
            if risk in html:
                # 找到位置，确保在 "类型" 之后
                idx = html.find(risk)
                if idx < 0:
                    continue
                # 检查前后 500 字符内是否有 "类型" 字样
                ctx = html[max(0, idx - 500):idx]
                if "类型" in ctx or "stock-type" in ctx or "fundType" in ctx:
                    out["risk_level"] = risk
                    break
        # 评级：找 晨星评级行
        m = re.search(r"晨星评级</a>[^<]*</td>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>([★]+)", html)
        if m:
            out["rating"] = len(m.group(2))
        return out

    @staticmethod
    def _parse_f10(html: str) -> Dict[str, Any]:
        """
        从 jbgk_{code}.html 提取：
        - 基金经理
        - 基金管理人（基金公司）
        - 成立日期
        - 净资产规模（亿元 + 截止日期）
        """
        out: Dict[str, Any] = {}
        # 解码 unicode escape（如 \u91d1\u6893 才需要，但 jbgk 一般是真实中文）
        if re.search(r"\\u[0-9a-fA-F]{4}", html):
            try:
                html = html.encode("utf-8").decode("unicode_escape")
            except UnicodeDecodeError:
                pass
        tree = etree.HTML(html)

        def text_of(xpath_expr: str) -> str:
            for el in tree.xpath(xpath_expr):
                return "".join(el.xpath(".//text()")).strip()
            return ""

        # 经理（label 内的 a 标签文本）
        manager = ""
        for a in tree.xpath("//label[contains(., '基金经理')]/a"):
            t = "".join(a.xpath(".//text()")).strip()
            if t and "经理" not in t and "管理" not in t:
                manager = t
                break
        if manager:
            out["manager"] = manager

        # 管理人（基金公司）
        for a in tree.xpath("//label[contains(., '管理人')]/a"):
            t = "".join(a.xpath(".//text()")).strip()
            if t and "管理人" not in t and "管理" not in t and len(t) <= 30:
                # 排除 URL 形式的文本
                if not t.startswith("http"):
                    out["company"] = t
                    break

        # 成立日期
        for label in tree.xpath("//label[contains(., '成立日期')]"):
            t = "".join(label.xpath(".//text()")).strip()
            m = re.search(r"(\d{4}-\d{2}-\d{2})", t)
            if m:
                out["inception_date"] = m.group(1)
                break

        # 净资产规模 + 截止日期
        for label in tree.xpath("//label[contains(., '净资产规模')]"):
            t = "".join(label.xpath(".//text()")).strip()
            # 例: "净资产规模： 22.96亿元 （截止至：2026-06-30）"
            m = re.search(r"([\d.]+)\s*亿元", t)
            if m:
                out["scale_yi"] = float(m.group(1))
            m2 = re.search(r"(\d{4}-\d{2}-\d{2})", t)
            if m2:
                out["nav_date"] = m2.group(1)
            break

        return out

    async def fetch_many(
        self,
        codes: List[str],
        concurrency: int = 6,
    ) -> Dict[str, Dict[str, Any]]:
        """并发抓取多只基金的详情"""
        sem = asyncio.Semaphore(concurrency)
        results: Dict[str, Dict[str, Any]] = {}

        async def _one(code: str):
            async with sem:
                try:
                    results[code] = await self.fetch_one(code)
                except Exception as e:
                    logger.warning("抓取基金 %s 详情失败: %s", code, e)
                    results[code] = {"code": code}

        await asyncio.gather(*[_one(c) for c in codes])
        return results
