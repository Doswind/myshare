"""基金和股票数据公共模块。

数据源为 AkShare。基金持仓属于定期披露数据，不代表实时持仓。
"""

from __future__ import annotations

import json
import os
import re
from typing import Iterable

import akshare as ak
import pandas as pd
import requests


DEFAULT_FUND_TYPES = ("股票型", "指数型", "混合型")


def _code(value: object) -> str:
    """将基金/股票代码标准化为六位字符串。"""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6)


def _kv_frame_to_dict(df: pd.DataFrame) -> dict:
    """把 item/value 或 字段/值 形式的详情表转换为字典。"""
    if df is None or df.empty or len(df.columns) < 2:
        return {}
    key_col, value_col = df.columns[:2]
    return dict(zip(df[key_col].astype(str), df[value_col]))


def _number(value: object) -> float | None:
    """将行情文本安全转换为数值。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class MarketDataClient:
    """AkShare 基金和股票数据访问客户端。"""

    def __init__(self, cache_dir: str = "./output"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_fund_list(
        self,
        types: Iterable[str] | None = None,
        min_scale: float | None = None,
        exclude_c: bool = True,
        exclude_backend: bool = True,
        cache_path: str | None = None,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """获取最新基金列表并进行本地筛选。

        参数:
            types: 基金类型前缀，例如 ``("股票型", "指数型", "混合型")``。
            min_scale: 最小规模（亿元）。需要列表缓存或数据源提供基金规模字段。
            exclude_c: 是否排除简称以 C/C类 结尾的份额。
            exclude_backend: 是否排除后端收费份额。
            cache_path: 过滤后列表缓存路径；默认使用 cache_dir/filter_fund_list.csv。
            refresh: 是否忽略缓存并重新获取基金列表。
        """
        cache_path = cache_path or os.path.join(
            self.cache_dir, "filter_fund_list.csv"
        )
        wanted_types = tuple(types or DEFAULT_FUND_TYPES)
        cache_meta_path = f"{cache_path}.meta.json"
        cache_meta = {
            "types": sorted(wanted_types),
            "exclude_c": exclude_c,
            "exclude_backend": exclude_backend,
        }

        cache_matches = False
        if os.path.exists(cache_meta_path):
            try:
                with open(cache_meta_path, encoding="utf-8") as file:
                    cache_matches = json.load(file) == cache_meta
            except (OSError, json.JSONDecodeError):
                cache_matches = False

        if os.path.exists(cache_path) and cache_matches and not refresh:
            result = pd.read_csv(cache_path, dtype={"基金代码": str})
            if min_scale and (
                "基金规模" not in result.columns
                or pd.to_numeric(
                    result["基金规模"], errors="coerce"
                ).isna().all()
            ):
                result = self._load_fund_scales(result)
                result.to_csv(cache_path, index=False, encoding="utf-8-sig")
            return self._filter_fund_scale(result, min_scale)

        all_funds = ak.fund_name_em()
        all_funds["基金代码"] = all_funds["基金代码"].map(_code)
        result = all_funds[
            all_funds["基金类型"].fillna("").map(
                lambda value: any(
                    str(value).startswith(target) for target in wanted_types
                )
            )
        ].copy()

        names = result["基金简称"].fillna("").astype(str)
        if exclude_c:
            result = result[~names.str.endswith(("C", "C类"), na=False)]
            names = result["基金简称"].fillna("").astype(str)
        if exclude_backend:
            result = result[~names.str.contains("后端", na=False)]

        result.reset_index(drop=True, inplace=True)
        if min_scale:
            result = self._load_fund_scales(result)
        result.to_csv(cache_path, index=False, encoding="utf-8-sig")
        with open(cache_meta_path, "w", encoding="utf-8") as file:
            json.dump(cache_meta, file, ensure_ascii=False, indent=2)
        return self._filter_fund_scale(result, min_scale)

    @staticmethod
    def _filter_fund_scale(
        funds: pd.DataFrame, min_scale: float | None
    ) -> pd.DataFrame:
        if min_scale is None or min_scale <= 0:
            return funds.copy()
        if "基金规模" not in funds.columns:
            raise ValueError("当前基金列表没有“基金规模”字段，无法进行规模筛选")
        scale = pd.to_numeric(funds["基金规模"], errors="coerce")
        return funds[scale >= min_scale].copy()

    @staticmethod
    def _parse_scale(value: object) -> float | None:
        """从基金规模文本中提取亿元数值。"""
        match = re.search(r"([\d.]+)\s*亿", str(value))
        return float(match.group(1)) if match else None

    def _load_fund_scales(self, funds: pd.DataFrame) -> pd.DataFrame:
        """逐只补充基金规模；仅在调用方明确要求规模筛选时使用。"""
        result = funds.copy()
        scales = []
        for code in result["基金代码"]:
            try:
                overview = ak.fund_overview_em(symbol=_code(code))
                scale_value = None
                if overview is not None and not overview.empty:
                    row = overview.iloc[0]
                    for key in overview.columns:
                        if "净资产规模" in str(key) or "基金规模" in str(key):
                            scale_value = self._parse_scale(row[key])
                            if scale_value is not None:
                                break
                scales.append(scale_value)
            except Exception:
                scales.append(None)
        result["基金规模"] = scales
        return result

    def get_fund_detail(
        self,
        fund_code: str,
        nav_period: str = "1年",
    ) -> dict:
        """获取单只基金详情、最新净值和阶段收益。"""
        code = _code(fund_code)
        try:
            detail = _kv_frame_to_dict(
                ak.fund_individual_basic_info_xq(code)
            )
        except Exception:
            overview = ak.fund_overview_em(symbol=code)
            detail = (
                overview.iloc[0].dropna().to_dict()
                if overview is not None and not overview.empty
                else {}
            )

        # 统一几个常用字段名称，保留原始字段以便调用方继续使用。
        aliases = {
            "基金规模": ("最新规模", "基金规模"),
            "管理人": ("基金公司", "基金管理人", "管理人"),
            "成立日期": ("成立时间", "成立日期"),
            "类型": ("基金类型", "类型"),
        }
        for standard, candidates in aliases.items():
            detail[standard] = next(
                (detail[key] for key in candidates if key in detail), None
            )

        try:
            nav = ak.fund_open_fund_info_em(
                symbol=code,
                indicator="单位净值走势",
                period=nav_period,
            )
            if nav is not None and not nav.empty:
                latest = nav.iloc[-1]
                detail.update(
                    {
                        "最新净值": latest.get("单位净值"),
                        "最新净值日期": latest.get("净值日期"),
                        "日增长率": latest.get("日增长率"),
                    }
                )
        except Exception:
            pass

        try:
            returns = ak.fund_open_fund_info_em(
                symbol=code,
                indicator="累计收益率走势",
                period=nav_period,
            )
            if returns is not None and not returns.empty:
                detail[f"{nav_period}累计收益率"] = returns.iloc[-1].get(
                    "累计收益率"
                )
        except Exception:
            pass

        return detail

    def get_fund_holdings(
        self,
        fund_code: str,
        top_n: int = 10,
    ) -> pd.DataFrame:
        """获取单只基金最新披露季度的股票持仓。"""
        code = _code(fund_code)
        holdings = ak.fund_portfolio_hold_em(symbol=code, date="")
        if holdings is None or holdings.empty:
            return pd.DataFrame(
                columns=[
                    "基金代码",
                    "股票代码",
                    "股票名称",
                    "占净值比例",
                    "持股数",
                    "持仓市值",
                    "季度",
                ]
            )

        latest_quarter = holdings["季度"].dropna().iloc[-1]
        holdings = holdings[holdings["季度"] == latest_quarter].copy()
        holdings = holdings.sort_values("序号").head(top_n)
        holdings.insert(0, "基金代码", code)
        return holdings.reset_index(drop=True)

    def get_stock_detail(self, stock_code: str) -> dict:
        """获取单只 A 股的基本详情。"""
        code = _code(stock_code)
        try:
            detail = ak.stock_profile_cninfo(symbol=code)
            if detail is not None and not detail.empty:
                return detail.iloc[0].dropna().to_dict()
        except Exception:
            pass

        # 巨潮接口不可用时，仅请求单只股票的雪球资料，绝不回退到全市场行情。
        market = "SH" if code.startswith(("600", "601", "603", "605", "688")) else "SZ"
        try:
            detail = ak.stock_individual_basic_info_xq(
                symbol=f"{market}{code}"
            )
            return _kv_frame_to_dict(detail)
        except Exception:
            return {}

    def get_stock_quote(self, stock_code: str | None = None) -> pd.DataFrame:
        """获取 A 股实时行情；传代码时返回对应股票。"""
        if stock_code is not None:
            return self._get_single_stock_quote(stock_code)

        try:
            quotes = ak.stock_zh_a_spot_em()
        except Exception:
            quotes = ak.stock_zh_a_spot_tx()
        return quotes

    def get_stock_returns(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> dict:
        """根据历史收盘价计算区间收益和最大回撤。"""
        history = self.get_stock_history(
            stock_code, start_date, end_date, adjust=adjust
        )
        if history.empty:
            return {}
        close = pd.to_numeric(history["收盘"], errors="coerce").dropna()
        if close.empty:
            return {}
        drawdown = close / close.cummax() - 1
        return {
            "stock_code": _code(stock_code),
            "start_date": str(history["日期"].iloc[0]),
            "end_date": str(history["日期"].iloc[-1]),
            "start_close": float(close.iloc[0]),
            "end_close": float(close.iloc[-1]),
            "return_pct": float((close.iloc[-1] / close.iloc[0] - 1) * 100),
            "max_drawdown_pct": float(drawdown.min() * 100),
        }

    def get_technical_indicators(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """基于历史行情计算均线、MACD、RSI 和布林带。"""
        df = self.get_stock_history(
            stock_code, start_date, end_date, adjust=adjust
        ).copy()
        if df.empty:
            return df
        close = pd.to_numeric(df["收盘"], errors="coerce")
        df["MA5"] = close.rolling(5).mean()
        df["MA10"] = close.rolling(10).mean()
        df["MA20"] = close.rolling(20).mean()
        df["MA60"] = close.rolling(60).mean()
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df["DIF"] = ema12 - ema26
        df["DEA"] = df["DIF"].ewm(span=9, adjust=False).mean()
        df["MACD"] = (df["DIF"] - df["DEA"]) * 2
        change = close.diff()
        gain = change.clip(lower=0).rolling(14).mean()
        loss = (-change.clip(upper=0)).rolling(14).mean()
        df["RSI14"] = 100 - 100 / (1 + gain / loss.replace(0, pd.NA))
        middle = close.rolling(20).mean()
        std = close.rolling(20).std()
        df["BOLL_MIDDLE"] = middle
        df["BOLL_UPPER"] = middle + 2 * std
        df["BOLL_LOWER"] = middle - 2 * std
        return df

    def get_financial_summary(self, stock_code: str) -> pd.DataFrame:
        """获取单只股票主要财务指标。"""
        return ak.stock_financial_abstract_new_ths(
            symbol=_code(stock_code),
            indicator="按报告期",
        )

    def get_stock_valuation(self, stock_code: str) -> dict:
        """获取单只股票实时估值字段。"""
        quote = self.get_stock_quote(stock_code)
        return quote.iloc[0].dropna().to_dict() if not quote.empty else {}

    def get_stock_fund_flow(self, stock_code: str) -> pd.DataFrame:
        """获取单只股票历史资金流向。"""
        code = _code(stock_code)
        market = "sh" if code.startswith(("5", "6", "9")) else "sz"
        return ak.stock_individual_fund_flow(stock=code, market=market)

    def get_major_shareholders(
        self,
        stock_code: str,
        report_date: str,
        free_float: bool = False,
    ) -> pd.DataFrame:
        """获取指定报告期前十大股东或前十大流通股东。"""
        code = _code(stock_code)
        prefix = "sh" if code.startswith(("5", "6", "9")) else "sz"
        function = (
            ak.stock_gdfx_free_top_10_em
            if free_float
            else ak.stock_gdfx_top_10_em
        )
        return function(symbol=f"{prefix}{code}", date=report_date)

    def get_stock_dividends(self, stock_code: str) -> pd.DataFrame:
        """获取单只股票历史分红送配记录。"""
        return ak.stock_dividend_cninfo(symbol=_code(stock_code))

    def get_stock_news(self, stock_code: str) -> pd.DataFrame:
        """获取单只股票新闻。"""
        return ak.stock_news_em(symbol=_code(stock_code))

    def get_stock_announcements(
        self,
        stock_code: str,
        begin_date: str | None = None,
        end_date: str | None = None,
        category: str = "全部",
    ) -> pd.DataFrame:
        """获取单只股票公告。"""
        return ak.stock_individual_notice_report(
            security=_code(stock_code),
            symbol=category,
            begin_date=begin_date,
            end_date=end_date,
        )

    def get_industry_fund_flow(
        self,
        indicator: str = "今日",
    ) -> pd.DataFrame:
        """获取行业板块资金流向排名。"""
        return ak.stock_sector_fund_flow_rank(
            indicator=indicator,
            sector_type="行业资金流",
        )

    @staticmethod
    def _get_single_stock_quote(stock_code: str) -> pd.DataFrame:
        """通过腾讯单代码接口获取行情，不下载全市场数据。"""
        code = _code(stock_code)
        if code.startswith(("4", "8", "92")):
            market = "bj"
        elif code.startswith(("5", "6", "9")):
            market = "sh"
        else:
            market = "sz"

        response = requests.get(
            f"https://qt.gtimg.cn/q={market}{code}",
            timeout=10,
        )
        response.raise_for_status()
        response.encoding = "gbk"
        text = response.text
        if '="' not in text:
            return pd.DataFrame()
        values = text.split('="', 1)[1].rsplit('"', 1)[0].split("~")
        if len(values) < 50 or not values[2]:
            return pd.DataFrame()

        return pd.DataFrame(
            [
                {
                    "代码": values[2],
                    "名称": values[1],
                    "最新价": _number(values[3]),
                    "昨收": _number(values[4]),
                    "今开": _number(values[5]),
                    "涨跌额": _number(values[31]),
                    "涨跌幅": _number(values[32]),
                    "最高": _number(values[33]),
                    "最低": _number(values[34]),
                    "成交量": _number(values[36]),
                    "成交额": _number(values[37]),
                    "换手率": _number(values[38]),
                    "市盈率-动态": _number(values[39]),
                    "振幅": _number(values[43]),
                    "流通市值": _number(values[44]),
                    "总市值": _number(values[45]),
                    "涨停价": _number(values[47]),
                    "跌停价": _number(values[48]),
                    "量比": _number(values[49]),
                    "行情时间": values[30],
                }
            ]
        )

    def get_industry_board_mapping(
        self,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """建立并缓存股票代码到一级行业板块的反向映射。"""
        cache_path = os.path.join(
            self.cache_dir,
            "stock_industry_board_mapping.csv",
        )
        if os.path.exists(cache_path) and not refresh:
            return pd.read_csv(cache_path, dtype={"股票代码": str})

        try:
            board_list = ak.stock_board_industry_name_em()
        except Exception as error:
            raise RuntimeError("获取东方财富行业板块列表失败") from error

        name_column = next(
            (
                column
                for column in board_list.columns
                if "名称" in str(column)
                or str(column).lower() == "name"
            ),
            board_list.columns[0],
        )
        records = []
        for board_name in board_list[name_column].dropna().astype(str):
            try:
                constituents = ak.stock_board_industry_cons_em(
                    symbol=board_name
                )
                code_column = next(
                    (
                        column
                        for column in constituents.columns
                        if "代码" in str(column)
                        or str(column).lower() in {"code", "symbol"}
                    ),
                    None,
                )
                if code_column is None:
                    continue
                records.extend(
                    {
                        "股票代码": _code(code),
                        "行业板块": board_name,
                    }
                    for code in constituents[code_column].dropna()
                )
            except Exception:
                continue

        mapping = pd.DataFrame(records).drop_duplicates()
        if mapping.empty:
            raise RuntimeError("没有获取到行业板块成分股映射")
        mapping.to_csv(cache_path, index=False, encoding="utf-8-sig")
        return mapping

    def get_stock_industry_board(
        self,
        stock_code: str,
        refresh: bool = False,
    ) -> dict:
        """获取单只股票的展示型一级行业板块。"""
        code = _code(stock_code)
        try:
            mapping = self.get_industry_board_mapping(refresh=refresh)
        except RuntimeError as error:
            # 板块映射首次构建依赖东方财富成分股接口。
            # 接口不可用时返回公司详细行业，避免页面因网络错误崩溃。
            detail = self.get_stock_detail(code)
            official_industry = detail.get("所属行业")
            fallback_board = self._infer_display_board(official_industry)
            return {
                "stock_code": code,
                "industry_board": fallback_board,
                "industry_boards": [fallback_board] if fallback_board else [],
                "official_industry": official_industry,
                "source": "本地规则映射",
            }
        boards = (
            mapping.loc[
                mapping["股票代码"].map(_code) == code,
                "行业板块",
            ]
            .drop_duplicates()
            .tolist()
        )
        return {
            "stock_code": code,
            "industry_board": boards[0] if boards else None,
            "industry_boards": boards,
            "official_industry": self.get_stock_detail(code).get("所属行业"),
            "source": "东方财富行业板块",
        }

    @staticmethod
    def _infer_display_board(official_industry: object) -> str | None:
        """网络不可用时，将正式行业名称映射为页面展示大类。"""
        text = str(official_industry or "")
        rules = (
            (("计算机", "通信", "电子设备"), "电子设备"),
            (("电气机械", "电气设备"), "电气设备"),
            (("石油", "天然气", "煤炭"), "化石能源"),
            (("食品", "饮料", "酒"), "食品饮料"),
            (("医药", "医疗"), "医药生物"),
            (("银行", "保险", "证券"), "金融"),
            (("汽车", "车辆"), "汽车"),
            (("房地产", "房地产业"), "房地产"),
            (("建筑", "工程"), "建筑装饰"),
        )
        for keywords, board in rules:
            if any(keyword in text for keyword in keywords):
                return board
        return None

    def get_board(
        self,
        board_type: str = "industry",
        board: str | None = None,
        refresh: bool = False,
        cache: bool = True,
    ) -> pd.DataFrame:
        """获取行业或概念板块。

        参数:
            board_type: ``industry`` 表示行业板块，``concept`` 表示概念板块。
            board: 不传时返回板块列表；传板块名称或代码时返回该板块成分股。
            refresh: 是否忽略本地缓存并重新请求。
            cache: 是否读写本地 CSV 缓存。
        """
        if board_type not in {"industry", "concept"}:
            raise ValueError(
                "board_type 只支持 'industry' 或 'concept'"
            )

        suffix = "list" if board is None else re.sub(
            r"[^\w\u4e00-\u9fff-]+", "_", str(board)
        )
        cache_path = os.path.join(
            self.cache_dir,
            f"board_{board_type}_{suffix}.csv",
        )
        if cache and os.path.exists(cache_path) and not refresh:
            return pd.read_csv(
                cache_path,
                dtype={"代码": str, "code": str},
            )

        try:
            if board_type == "industry":
                result = (
                    ak.stock_board_industry_name_em()
                    if board is None
                    else ak.stock_board_industry_cons_em(symbol=board)
                )
            else:
                result = (
                    ak.stock_board_concept_name_em()
                    if board is None
                    else ak.stock_board_concept_cons_em(symbol=board)
                )
        except Exception as error:
            # 东方财富板块接口不可用时，同花顺可提供板块列表。
            # 当前 AkShare 没有同花顺板块成分股接口，因此指定 board 时仍报错。
            if board is not None:
                raise RuntimeError(
                    f"获取{board_type}板块“{board}”成分股失败；"
                    "当前备用数据源只支持板块列表"
                ) from error
            try:
                result = (
                    ak.stock_board_industry_name_ths()
                    if board_type == "industry"
                    else ak.stock_board_concept_name_ths()
                )
            except Exception as fallback_error:
                raise RuntimeError(
                    f"获取{board_type}板块数据失败，请稍后重试"
                ) from fallback_error

        if result is None:
            result = pd.DataFrame()
        if cache and not result.empty:
            result.to_csv(cache_path, index=False, encoding="utf-8-sig")
        return result

    def get_board_date(
        self,
        board_type: str = "industry",
        board: str | None = None,
        refresh: bool = False,
        cache: bool = True,
    ) -> pd.DataFrame:
        """兼容旧测试代码，等同于 get_board。"""
        return self.get_board(
            board_type=board_type,
            board=board,
            refresh=refresh,
            cache=cache,
        )

    def get_stock_history(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        period: str = "daily",
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取 A 股历史行情。日期格式为 YYYYMMDD。"""
        code = _code(stock_code)
        try:
            return ak.stock_zh_a_hist(
                symbol=code,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        except Exception:
            if period != "daily":
                raise ValueError("腾讯备用接口只支持 daily 历史行情")
            market = "sh" if code.startswith(("5", "6", "9")) else "sz"
            history = ak.stock_zh_a_hist_tx(
                symbol=f"{market}{code}",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            history = history.rename(
                columns={
                    "date": "日期",
                    "open": "开盘",
                    "close": "收盘",
                    "high": "最高",
                    "low": "最低",
                    "volume": "成交量",
                    "turnover": "换手率",
                    "amount": "成交额",
                }
            )
            if "换手率" in history.columns:
                history["换手率"] = history["换手率"] * 100
            return history

    def plot_stock_kline(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        output_path: str | None = None,
        adjust: str = "qfq",
        show: bool = False,
    ) -> str:
        """获取历史行情并生成 K 线和成交量图，返回图片路径。"""
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle

        plt.rcParams["font.sans-serif"] = [
            "PingFang SC",
            "Arial Unicode MS",
            "DejaVu Sans",
        ]
        plt.rcParams["axes.unicode_minus"] = False
        code = _code(stock_code)
        history = self.get_stock_history(
            code,
            start_date,
            end_date,
            period="daily",
            adjust=adjust,
        ).copy()
        if history.empty:
            raise ValueError(f"{code} 在指定区间没有历史行情数据")

        required = {"日期", "开盘", "收盘", "最高", "最低", "成交量"}
        missing = required.difference(history.columns)
        if missing:
            raise ValueError(f"历史行情缺少绘图字段: {sorted(missing)}")

        history["日期"] = pd.to_datetime(history["日期"])
        history = history.sort_values("日期").reset_index(drop=True)
        if output_path is None:
            output_path = os.path.join(
                self.cache_dir,
                f"{code}_kline_{start_date}_{end_date}.png",
            )
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        dates = mdates.date2num(history["日期"].dt.to_pydatetime())
        fig, (price_ax, volume_ax) = plt.subplots(
            2,
            1,
            figsize=(14, 8),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},
        )
        candle_width = 0.7
        for index, row in history.iterrows():
            rising = row["收盘"] >= row["开盘"]
            color = "#d62728" if rising else "#2ca02c"
            price_ax.vlines(
                dates[index],
                row["最低"],
                row["最高"],
                color=color,
                linewidth=0.8,
            )
            body_bottom = min(row["开盘"], row["收盘"])
            body_height = abs(row["收盘"] - row["开盘"])
            if body_height == 0:
                body_height = max(abs(row["收盘"]) * 0.0001, 0.0001)
            price_ax.add_patch(
                Rectangle(
                    (dates[index] - candle_width / 2, body_bottom),
                    candle_width,
                    body_height,
                    facecolor=color,
                    edgecolor=color,
                )
            )
            volume_ax.bar(
                dates[index],
                row["成交量"],
                width=candle_width,
                color=color,
                alpha=0.8,
            )

        price_ax.set_title(
            f"{code} K线图（{start_date} - {end_date}，{adjust or '不复权'}）"
        )
        price_ax.set_ylabel("价格")
        volume_ax.set_ylabel("成交量")
        volume_ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        volume_ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        price_ax.grid(alpha=0.25)
        volume_ax.grid(alpha=0.25)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        if show:
            plt.show()
        plt.close(fig)
        return output_path

if __name__ == '__main__':
    stock = MarketDataClient()
    #s = stock.get_fund_list(types=["股票型"], exclude_c=True, exclude_backend=True)
    #print(s)
    #f = stock.get_fund_detail("011369")
    #rint(f)
    #g = stock.get_fund_holdings("011369")
    #print(g)
    #d = stock.get_stock_detail("300308")
    #print(d)
    #h = stock.get_stock_quote("300308")
    #print(h)
    #a = stock.get_stock_history("300308", "20260701", "20260814")
    #print(a)
    #e = stock.plot_stock_kline("300308", "20260701", "20260814")
    #print(e)
    #i = stock.get_board()
    #print(i)
    #m = stock.get_stock_detail("300308")
    #print(m.get("所属行业"))
    n = stock.get_stock_industry_board("300308")
    print(n)
