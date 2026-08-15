"""选股 demo mock 数据

20 只 mock 候选，覆盖 10 个行业，故意混合 4 种典型形态：
- 低位高分（候选）：pct_rank_1y 低（< 30%）+ 主力资金行为积极 → total_score 高
- 高位低分（陷阱）：pct_rank_1y 高（> 80%）+ 主力减仓 → total_score 低
- 低位低分（观望）：位置低但资本不动作 → total_score 中
- 中位高分（追强）：位置中位但趋势强势 + 主力加仓 → total_score 高

数据形态仅用于演示，**不反映真实行情**，请勿当作真实依据。
"""
from __future__ import annotations

from typing import Optional


# ---------- 数据定义 ----------

# 20 只 mock 候选
_CANDIDATES: list[dict] = [
    # ===== 白酒（低位高分 候选）=====
    {
        "code": "600519", "name": "贵州茅台", "industry": "白酒",
        "total_score": 78,
        "score_position": 85, "score_trend": 60, "score_capital": 92,
        "factors": {
            "pct_rank_1y": 12.3, "pct_rank_3y": 34.5,
            "drawdown_1y": -28.4, "vs_ma60_z": -1.42,
            "rsi_14": 28.6, "boll_pos": 8.2,
            "consecutive_down": 5, "volume_ratio_20d": 0.62,
        },
        "capital": {
            "fund_count": 12, "total_mv_yi": 86.4,
            "mv_change_pct_qoq": 8.3,
            "avg_fund_ret_1y": 18.4, "smart_money_index": 0.83,
        },
        "valuation": {"pe_ttm": 25.8, "pe_pct_rank_3y": 67, "pb": 8.4},
        "latest_price": 1456.30,
        "market_cap_wan_yi": 1.83,
        "holders": [
            {"fund_code": "161725", "fund_name": "招商中证白酒", "scale_yi": 685, "ret_1y": 12.3, "ratio_net": 9.8, "market_value_wan": 671230},
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 7.2, "market_value_wan": 329760},
            {"fund_code": "163406", "fund_name": "兴全合润分级", "scale_yi": 215, "ret_1y": 22.1, "ratio_net": 6.5, "market_value_wan": 139750},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 8.1, "market_value_wan": 313470},
            {"fund_code": "007119", "fund_name": "睿远成长价值", "scale_yi": 198, "ret_1y": 17.5, "ratio_net": 5.9, "market_value_wan": 116820},
            {"fund_code": "110011", "fund_name": "易方达中小盘", "scale_yi": 156, "ret_1y": 14.2, "ratio_net": 4.8, "market_value_wan": 74880},
            {"fund_code": "519694", "fund_name": "交银蓝筹", "scale_yi": 89, "ret_1y": 21.3, "ratio_net": 5.2, "market_value_wan": 46280},
            {"fund_code": "000083", "fund_name": "汇添富消费行业", "scale_yi": 142, "ret_1y": 16.8, "ratio_net": 4.5, "market_value_wan": 63900},
        ],
        "trend": {
            "ma20_dir": "下跌", "ma60_dir": "下跌", "ma250_dir": "平",
            "ret_20d": -7.2, "ret_60d": -12.1,
        },
        "data_as_of": "2026-08-15",
    },
    {
        "code": "000858", "name": "五粮液", "industry": "白酒",
        "total_score": 71,
        "score_position": 78, "score_trend": 55, "score_capital": 82,
        "factors": {
            "pct_rank_1y": 22.1, "pct_rank_3y": 28.9,
            "drawdown_1y": -22.6, "vs_ma60_z": -1.18,
            "rsi_14": 32.4, "boll_pos": 15.3,
            "consecutive_down": 4, "volume_ratio_20d": 0.71,
        },
        "capital": {
            "fund_count": 9, "total_mv_yi": 42.1,
            "mv_change_pct_qoq": 5.6,
            "avg_fund_ret_1y": 16.2, "smart_money_index": 0.71,
        },
        "valuation": {"pe_ttm": 19.4, "pe_pct_rank_3y": 45, "pb": 4.2},
        "latest_price": 142.50,
        "market_cap_wan_yi": 0.55,
        "holders": [
            {"fund_code": "161725", "fund_name": "招商中证白酒", "scale_yi": 685, "ret_1y": 12.3, "ratio_net": 8.2, "market_value_wan": 561700},
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 6.1, "market_value_wan": 279380},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 5.8, "market_value_wan": 224460},
            {"fund_code": "000083", "fund_name": "汇添富消费行业", "scale_yi": 142, "ret_1y": 16.8, "ratio_net": 4.2, "market_value_wan": 59640},
        ],
        "trend": {
            "ma20_dir": "下跌", "ma60_dir": "下跌", "ma250_dir": "下跌",
            "ret_20d": -5.8, "ret_60d": -9.3,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 银行（高位低分 陷阱）=====
    {
        "code": "600036", "name": "招商银行", "industry": "银行",
        "total_score": 28,
        "score_position": 18, "score_trend": 35, "score_capital": 38,
        "factors": {
            "pct_rank_1y": 87.2, "pct_rank_3y": 78.4,
            "drawdown_1y": -3.2, "vs_ma60_z": 1.85,
            "rsi_14": 72.4, "boll_pos": 92.1,
            "consecutive_down": 0, "volume_ratio_20d": 1.32,
        },
        "capital": {
            "fund_count": 4, "total_mv_yi": 18.2,
            "mv_change_pct_qoq": -12.5,
            "avg_fund_ret_1y": 8.9, "smart_money_index": 0.32,
        },
        "valuation": {"pe_ttm": 7.8, "pe_pct_rank_3y": 72, "pb": 1.1},
        "latest_price": 38.92,
        "market_cap_wan_yi": 0.98,
        "holders": [
            {"fund_code": "000311", "fund_name": "景顺长城沪深300", "scale_yi": 412, "ret_1y": 7.2, "ratio_net": 1.2, "market_value_wan": 49440},
            {"fund_code": "510300", "fund_name": "华泰柏瑞沪深300", "scale_yi": 892, "ret_1y": 6.8, "ratio_net": 0.8, "market_value_wan": 71360},
            {"fund_code": "100020", "fund_name": "富国天益价值", "scale_yi": 78, "ret_1y": 12.4, "ratio_net": 3.5, "market_value_wan": 27300},
            {"fund_code": "519983", "fund_name": "长信量化先锋", "scale_yi": 65, "ret_1y": 9.2, "ratio_net": 2.1, "market_value_wan": 13650},
        ],
        "trend": {
            "ma20_dir": "上涨", "ma60_dir": "上涨", "ma250_dir": "上涨",
            "ret_20d": 5.8, "ret_60d": 11.2,
        },
        "data_as_of": "2026-08-15",
    },
    {
        "code": "601398", "name": "工商银行", "industry": "银行",
        "total_score": 35,
        "score_position": 42, "score_trend": 38, "score_capital": 28,
        "factors": {
            "pct_rank_1y": 65.4, "pct_rank_3y": 58.2,
            "drawdown_1y": -8.5, "vs_ma60_z": 0.62,
            "rsi_14": 58.2, "boll_pos": 68.4,
            "consecutive_down": 0, "volume_ratio_20d": 0.85,
        },
        "capital": {
            "fund_count": 3, "total_mv_yi": 24.5,
            "mv_change_pct_qoq": -3.2,
            "avg_fund_ret_1y": 6.5, "smart_money_index": 0.18,
        },
        "valuation": {"pe_ttm": 6.2, "pe_pct_rank_3y": 52, "pb": 0.7},
        "latest_price": 6.85,
        "market_cap_wan_yi": 2.45,
        "holders": [
            {"fund_code": "510300", "fund_name": "华泰柏瑞沪深300", "scale_yi": 892, "ret_1y": 6.8, "ratio_net": 0.4, "market_value_wan": 35680},
            {"fund_code": "510330", "fund_name": "华夏沪深300", "scale_yi": 425, "ret_1y": 6.5, "ratio_net": 0.3, "market_value_wan": 12750},
            {"fund_code": "000311", "fund_name": "景顺长城沪深300", "scale_yi": 412, "ret_1y": 7.2, "ratio_net": 0.5, "market_value_wan": 20600},
        ],
        "trend": {
            "ma20_dir": "上涨", "ma60_dir": "平", "ma250_dir": "上涨",
            "ret_20d": 2.3, "ret_60d": 5.8,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 新能源（中位高分 追强）=====
    {
        "code": "300750", "name": "宁德时代", "industry": "新能源",
        "total_score": 82,
        "score_position": 62, "score_trend": 88, "score_capital": 90,
        "factors": {
            "pct_rank_1y": 48.5, "pct_rank_3y": 32.1,
            "drawdown_1y": -15.8, "vs_ma60_z": 0.32,
            "rsi_14": 62.3, "boll_pos": 58.2,
            "consecutive_down": 1, "volume_ratio_20d": 1.18,
        },
        "capital": {
            "fund_count": 15, "total_mv_yi": 128.5,
            "mv_change_pct_qoq": 14.8,
            "avg_fund_ret_1y": 24.6, "smart_money_index": 0.92,
        },
        "valuation": {"pe_ttm": 32.5, "pe_pct_rank_3y": 28, "pb": 4.8},
        "latest_price": 268.40,
        "market_cap_wan_yi": 1.18,
        "holders": [
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 8.5, "market_value_wan": 389300},
            {"fund_code": "007119", "fund_name": "睿远成长价值", "scale_yi": 198, "ret_1y": 17.5, "ratio_net": 9.2, "market_value_wan": 182160},
            {"fund_code": "161725", "fund_name": "招商中证白酒", "scale_yi": 685, "ret_1y": 12.3, "ratio_net": 5.6, "market_value_wan": 383600},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 7.8, "market_value_wan": 301860},
            {"fund_code": "163406", "fund_name": "兴全合润分级", "scale_yi": 215, "ret_1y": 22.1, "ratio_net": 6.5, "market_value_wan": 139750},
            {"fund_code": "000083", "fund_name": "汇添富消费行业", "scale_yi": 142, "ret_1y": 16.8, "ratio_net": 4.2, "market_value_wan": 59640},
            {"fund_code": "110011", "fund_name": "易方达中小盘", "scale_yi": 156, "ret_1y": 14.2, "ratio_net": 3.8, "market_value_wan": 59280},
        ],
        "trend": {
            "ma20_dir": "上涨", "ma60_dir": "上涨", "ma250_dir": "平",
            "ret_20d": 8.5, "ret_60d": 15.3,
        },
        "data_as_of": "2026-08-15",
    },
    {
        "code": "002594", "name": "比亚迪", "industry": "新能源",
        "total_score": 75,
        "score_position": 58, "score_trend": 82, "score_capital": 78,
        "factors": {
            "pct_rank_1y": 38.2, "pct_rank_3y": 52.4,
            "drawdown_1y": -18.6, "vs_ma60_z": -0.42,
            "rsi_14": 54.2, "boll_pos": 48.5,
            "consecutive_down": 2, "volume_ratio_20d": 1.05,
        },
        "capital": {
            "fund_count": 11, "total_mv_yi": 78.2,
            "mv_change_pct_qoq": 9.5,
            "avg_fund_ret_1y": 20.5, "smart_money_index": 0.78,
        },
        "valuation": {"pe_ttm": 28.4, "pe_pct_rank_3y": 38, "pb": 5.2},
        "latest_price": 268.50,
        "market_cap_wan_yi": 0.78,
        "holders": [
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 6.8, "market_value_wan": 311440},
            {"fund_code": "007119", "fund_name": "睿远成长价值", "scale_yi": 198, "ret_1y": 17.5, "ratio_net": 8.2, "market_value_wan": 162360},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 7.1, "market_value_wan": 274770},
            {"fund_code": "163406", "fund_name": "兴全合润分级", "scale_yi": 215, "ret_1y": 22.1, "ratio_net": 5.8, "market_value_wan": 124700},
            {"fund_code": "519694", "fund_name": "交银蓝筹", "scale_yi": 89, "ret_1y": 21.3, "ratio_net": 4.5, "market_value_wan": 40050},
        ],
        "trend": {
            "ma20_dir": "上涨", "ma60_dir": "平", "ma250_dir": "上涨",
            "ret_20d": 4.2, "ret_60d": 8.5,
        },
        "data_as_of": "2026-08-15",
    },
    {
        "code": "601012", "name": "隆基绿能", "industry": "新能源",
        "total_score": 65,
        "score_position": 75, "score_trend": 50, "score_capital": 72,
        "factors": {
            "pct_rank_1y": 25.6, "pct_rank_3y": 18.2,
            "drawdown_1y": -32.4, "vs_ma60_z": -1.62,
            "rsi_14": 32.4, "boll_pos": 18.5,
            "consecutive_down": 6, "volume_ratio_20d": 0.68,
        },
        "capital": {
            "fund_count": 7, "total_mv_yi": 18.5,
            "mv_change_pct_qoq": 6.8,
            "avg_fund_ret_1y": 17.2, "smart_money_index": 0.62,
        },
        "valuation": {"pe_ttm": 22.4, "pe_pct_rank_3y": 42, "pb": 2.8},
        "latest_price": 18.45,
        "market_cap_wan_yi": 0.14,
        "holders": [
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 2.5, "market_value_wan": 114500},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 2.8, "market_value_wan": 108360},
            {"fund_code": "007119", "fund_name": "睿远成长价值", "scale_yi": 198, "ret_1y": 17.5, "ratio_net": 3.2, "market_value_wan": 63360},
            {"fund_code": "519694", "fund_name": "交银蓝筹", "scale_yi": 89, "ret_1y": 21.3, "ratio_net": 2.5, "market_value_wan": 22250},
        ],
        "trend": {
            "ma20_dir": "下跌", "ma60_dir": "下跌", "ma250_dir": "下跌",
            "ret_20d": -8.5, "ret_60d": -15.2,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 医药（低位低分 观望）=====
    {
        "code": "600276", "name": "恒瑞医药", "industry": "医药",
        "total_score": 52,
        "score_position": 68, "score_trend": 45, "score_capital": 48,
        "factors": {
            "pct_rank_1y": 28.5, "pct_rank_3y": 22.1,
            "drawdown_1y": -25.2, "vs_ma60_z": -1.25,
            "rsi_14": 35.8, "boll_pos": 18.6,
            "consecutive_down": 4, "volume_ratio_20d": 0.78,
        },
        "capital": {
            "fund_count": 6, "total_mv_yi": 22.5,
            "mv_change_pct_qoq": -2.5,
            "avg_fund_ret_1y": 11.2, "smart_money_index": 0.42,
        },
        "valuation": {"pe_ttm": 48.5, "pe_pct_rank_3y": 38, "pb": 6.2},
        "latest_price": 48.62,
        "market_cap_wan_yi": 0.31,
        "holders": [
            {"fund_code": "000083", "fund_name": "汇添富消费行业", "scale_yi": 142, "ret_1y": 16.8, "ratio_net": 5.2, "market_value_wan": 73840},
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 4.8, "market_value_wan": 219840},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 4.2, "market_value_wan": 162540},
            {"fund_code": "519694", "fund_name": "交银蓝筹", "scale_yi": 89, "ret_1y": 21.3, "ratio_net": 3.8, "market_value_wan": 33820},
        ],
        "trend": {
            "ma20_dir": "下跌", "ma60_dir": "下跌", "ma250_dir": "平",
            "ret_20d": -3.5, "ret_60d": -8.2,
        },
        "data_as_of": "2026-08-15",
    },
    {
        "code": "000538", "name": "云南白药", "industry": "医药",
        "total_score": 48,
        "score_position": 62, "score_trend": 42, "score_capital": 45,
        "factors": {
            "pct_rank_1y": 32.5, "pct_rank_3y": 38.4,
            "drawdown_1y": -18.4, "vs_ma60_z": -0.85,
            "rsi_14": 42.3, "boll_pos": 28.5,
            "consecutive_down": 3, "volume_ratio_20d": 0.85,
        },
        "capital": {
            "fund_count": 5, "total_mv_yi": 14.8,
            "mv_change_pct_qoq": -1.8,
            "avg_fund_ret_1y": 9.8, "smart_money_index": 0.38,
        },
        "valuation": {"pe_ttm": 25.4, "pe_pct_rank_3y": 48, "pb": 2.4},
        "latest_price": 56.78,
        "market_cap_wan_yi": 0.10,
        "holders": [
            {"fund_code": "000083", "fund_name": "汇添富消费行业", "scale_yi": 142, "ret_1y": 16.8, "ratio_net": 3.5, "market_value_wan": 49700},
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 2.8, "market_value_wan": 128240},
            {"fund_code": "163406", "fund_name": "兴全合润分级", "scale_yi": 215, "ret_1y": 22.1, "ratio_net": 2.5, "market_value_wan": 53750},
        ],
        "trend": {
            "ma20_dir": "下跌", "ma60_dir": "平", "ma250_dir": "平",
            "ret_20d": -2.5, "ret_60d": -5.8,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 科技（低位高分 候选）=====
    {
        "code": "002415", "name": "海康威视", "industry": "科技",
        "total_score": 73,
        "score_position": 80, "score_trend": 62, "score_capital": 78,
        "factors": {
            "pct_rank_1y": 18.4, "pct_rank_3y": 28.5,
            "drawdown_1y": -26.5, "vs_ma60_z": -1.52,
            "rsi_14": 30.5, "boll_pos": 12.5,
            "consecutive_down": 5, "volume_ratio_20d": 0.65,
        },
        "capital": {
            "fund_count": 10, "total_mv_yi": 52.4,
            "mv_change_pct_qoq": 7.2,
            "avg_fund_ret_1y": 19.5, "smart_money_index": 0.75,
        },
        "valuation": {"pe_ttm": 22.5, "pe_pct_rank_3y": 35, "pb": 3.8},
        "latest_price": 32.45,
        "market_cap_wan_yi": 0.30,
        "holders": [
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 5.8, "market_value_wan": 265640},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 5.2, "market_value_wan": 201240},
            {"fund_code": "007119", "fund_name": "睿远成长价值", "scale_yi": 198, "ret_1y": 17.5, "ratio_net": 6.5, "market_value_wan": 128700},
            {"fund_code": "163406", "fund_name": "兴全合润分级", "scale_yi": 215, "ret_1y": 22.1, "ratio_net": 4.8, "market_value_wan": 103200},
            {"fund_code": "519694", "fund_name": "交银蓝筹", "scale_yi": 89, "ret_1y": 21.3, "ratio_net": 3.8, "market_value_wan": 33820},
        ],
        "trend": {
            "ma20_dir": "下跌", "ma60_dir": "下跌", "ma250_dir": "平",
            "ret_20d": -6.5, "ret_60d": -11.8,
        },
        "data_as_of": "2026-08-15",
    },
    {
        "code": "300059", "name": "东方财富", "industry": "科技",
        "total_score": 68,
        "score_position": 72, "score_trend": 58, "score_capital": 75,
        "factors": {
            "pct_rank_1y": 22.8, "pct_rank_3y": 35.4,
            "drawdown_1y": -22.4, "vs_ma60_z": -1.18,
            "rsi_14": 35.4, "boll_pos": 18.5,
            "consecutive_down": 3, "volume_ratio_20d": 0.82,
        },
        "capital": {
            "fund_count": 8, "total_mv_yi": 38.6,
            "mv_change_pct_qoq": 5.8,
            "avg_fund_ret_1y": 17.8, "smart_money_index": 0.68,
        },
        "valuation": {"pe_ttm": 35.2, "pe_pct_rank_3y": 32, "pb": 4.5},
        "latest_price": 22.15,
        "market_cap_wan_yi": 0.35,
        "holders": [
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 4.8, "market_value_wan": 185760},
            {"fund_code": "007119", "fund_name": "睿远成长价值", "scale_yi": 198, "ret_1y": 17.5, "ratio_net": 5.2, "market_value_wan": 102960},
            {"fund_code": "163406", "fund_name": "兴全合润分级", "scale_yi": 215, "ret_1y": 22.1, "ratio_net": 4.5, "market_value_wan": 96750},
        ],
        "trend": {
            "ma20_dir": "下跌", "ma60_dir": "下跌", "ma250_dir": "平",
            "ret_20d": -4.8, "ret_60d": -9.5,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 消费（中位高分）=====
    {
        "code": "600887", "name": "伊利股份", "industry": "消费",
        "total_score": 62,
        "score_position": 55, "score_trend": 68, "score_capital": 65,
        "factors": {
            "pct_rank_1y": 45.2, "pct_rank_3y": 48.5,
            "drawdown_1y": -12.4, "vs_ma60_z": -0.12,
            "rsi_14": 52.3, "boll_pos": 45.8,
            "consecutive_down": 1, "volume_ratio_20d": 0.95,
        },
        "capital": {
            "fund_count": 7, "total_mv_yi": 28.5,
            "mv_change_pct_qoq": 4.5,
            "avg_fund_ret_1y": 15.2, "smart_money_index": 0.58,
        },
        "valuation": {"pe_ttm": 18.5, "pe_pct_rank_3y": 42, "pb": 3.2},
        "latest_price": 26.78,
        "market_cap_wan_yi": 0.17,
        "holders": [
            {"fund_code": "000083", "fund_name": "汇添富消费行业", "scale_yi": 142, "ret_1y": 16.8, "ratio_net": 6.5, "market_value_wan": 92300},
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 4.8, "market_value_wan": 219840},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 3.8, "market_value_wan": 147060},
        ],
        "trend": {
            "ma20_dir": "上涨", "ma60_dir": "平", "ma250_dir": "平",
            "ret_20d": 2.8, "ret_60d": 5.4,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 周期/金融（高位高分 追强但风险高）=====
    {
        "code": "601318", "name": "中国平安", "industry": "金融",
        "total_score": 58,
        "score_position": 48, "score_trend": 72, "score_capital": 55,
        "factors": {
            "pct_rank_1y": 72.4, "pct_rank_3y": 45.8,
            "drawdown_1y": -8.5, "vs_ma60_z": 1.12,
            "rsi_14": 65.4, "boll_pos": 78.4,
            "consecutive_down": 0, "volume_ratio_20d": 1.15,
        },
        "capital": {
            "fund_count": 5, "total_mv_yi": 32.5,
            "mv_change_pct_qoq": 3.8,
            "avg_fund_ret_1y": 13.5, "smart_money_index": 0.55,
        },
        "valuation": {"pe_ttm": 9.5, "pe_pct_rank_3y": 62, "pb": 1.0},
        "latest_price": 52.30,
        "market_cap_wan_yi": 0.95,
        "holders": [
            {"fund_code": "510300", "fund_name": "华泰柏瑞沪深300", "scale_yi": 892, "ret_1y": 6.8, "ratio_net": 1.5, "market_value_wan": 133800},
            {"fund_code": "100020", "fund_name": "富国天益价值", "scale_yi": 78, "ret_1y": 12.4, "ratio_net": 4.2, "market_value_wan": 32760},
            {"fund_code": "519983", "fund_name": "长信量化先锋", "scale_yi": 65, "ret_1y": 9.2, "ratio_net": 2.8, "market_value_wan": 18200},
        ],
        "trend": {
            "ma20_dir": "上涨", "ma60_dir": "上涨", "ma250_dir": "平",
            "ret_20d": 4.5, "ret_60d": 8.2,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 军工（低位高分 候选）=====
    {
        "code": "600760", "name": "中航沈飞", "industry": "军工",
        "total_score": 70,
        "score_position": 72, "score_trend": 65, "score_capital": 75,
        "factors": {
            "pct_rank_1y": 28.5, "pct_rank_3y": 35.4,
            "drawdown_1y": -22.8, "vs_ma60_z": -1.08,
            "rsi_14": 38.5, "boll_pos": 22.4,
            "consecutive_down": 3, "volume_ratio_20d": 0.75,
        },
        "capital": {
            "fund_count": 8, "total_mv_yi": 35.6,
            "mv_change_pct_qoq": 6.5,
            "avg_fund_ret_1y": 16.5, "smart_money_index": 0.72,
        },
        "valuation": {"pe_ttm": 35.8, "pe_pct_rank_3y": 45, "pb": 4.5},
        "latest_price": 42.85,
        "market_cap_wan_yi": 0.13,
        "holders": [
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 3.5, "market_value_wan": 160300},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 4.2, "market_value_wan": 162540},
            {"fund_code": "007119", "fund_name": "睿远成长价值", "scale_yi": 198, "ret_1y": 17.5, "ratio_net": 4.8, "market_value_wan": 95040},
        ],
        "trend": {
            "ma20_dir": "下跌", "ma60_dir": "平", "ma250_dir": "上涨",
            "ret_20d": -3.2, "ret_60d": -5.8,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 有色（中位高分）=====
    {
        "code": "601899", "name": "紫金矿业", "industry": "有色",
        "total_score": 66,
        "score_position": 58, "score_trend": 72, "score_capital": 68,
        "factors": {
            "pct_rank_1y": 52.4, "pct_rank_3y": 48.5,
            "drawdown_1y": -14.2, "vs_ma60_z": 0.18,
            "rsi_14": 55.8, "boll_pos": 52.4,
            "consecutive_down": 1, "volume_ratio_20d": 1.05,
        },
        "capital": {
            "fund_count": 9, "total_mv_yi": 42.5,
            "mv_change_pct_qoq": 8.5,
            "avg_fund_ret_1y": 17.2, "smart_money_index": 0.65,
        },
        "valuation": {"pe_ttm": 14.5, "pe_pct_rank_3y": 28, "pb": 2.8},
        "latest_price": 18.25,
        "market_cap_wan_yi": 0.48,
        "holders": [
            {"fund_code": "163406", "fund_name": "兴全合润分级", "scale_yi": 215, "ret_1y": 22.1, "ratio_net": 5.2, "market_value_wan": 111800},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 4.5, "market_value_wan": 174150},
            {"fund_code": "519694", "fund_name": "交银蓝筹", "scale_yi": 89, "ret_1y": 21.3, "ratio_net": 3.8, "market_value_wan": 33820},
        ],
        "trend": {
            "ma20_dir": "上涨", "ma60_dir": "上涨", "ma250_dir": "上涨",
            "ret_20d": 5.2, "ret_60d": 9.5,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 化工（低位低分 观望）=====
    {
        "code": "600309", "name": "万华化学", "industry": "化工",
        "total_score": 45,
        "score_position": 58, "score_trend": 38, "score_capital": 42,
        "factors": {
            "pct_rank_1y": 25.4, "pct_rank_3y": 28.5,
            "drawdown_1y": -28.5, "vs_ma60_z": -1.32,
            "rsi_14": 32.5, "boll_pos": 15.8,
            "consecutive_down": 5, "volume_ratio_20d": 0.68,
        },
        "capital": {
            "fund_count": 4, "total_mv_yi": 12.5,
            "mv_change_pct_qoq": -5.8,
            "avg_fund_ret_1y": 10.5, "smart_money_index": 0.32,
        },
        "valuation": {"pe_ttm": 16.5, "pe_pct_rank_3y": 35, "pb": 2.2},
        "latest_price": 78.50,
        "market_cap_wan_yi": 0.25,
        "holders": [
            {"fund_code": "163406", "fund_name": "兴全合润分级", "scale_yi": 215, "ret_1y": 22.1, "ratio_net": 3.5, "market_value_wan": 75250},
            {"fund_code": "100020", "fund_name": "富国天益价值", "scale_yi": 78, "ret_1y": 12.4, "ratio_net": 2.8, "market_value_wan": 21840},
        ],
        "trend": {
            "ma20_dir": "下跌", "ma60_dir": "下跌", "ma250_dir": "下跌",
            "ret_20d": -7.5, "ret_60d": -14.2,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 科技/AI（中位高分 追强）=====
    {
        "code": "688981", "name": "中芯国际", "industry": "科技",
        "total_score": 78,
        "score_position": 65, "score_trend": 82, "score_capital": 85,
        "factors": {
            "pct_rank_1y": 42.5, "pct_rank_3y": 38.5,
            "drawdown_1y": -16.8, "vs_ma60_z": 0.45,
            "rsi_14": 62.5, "boll_pos": 58.5,
            "consecutive_down": 0, "volume_ratio_20d": 1.25,
        },
        "capital": {
            "fund_count": 12, "total_mv_yi": 65.8,
            "mv_change_pct_qoq": 11.5,
            "avg_fund_ret_1y": 21.8, "smart_money_index": 0.85,
        },
        "valuation": {"pe_ttm": 85.5, "pe_pct_rank_3y": 52, "pb": 5.2},
        "latest_price": 82.45,
        "market_cap_wan_yi": 0.65,
        "holders": [
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 4.5, "market_value_wan": 206100},
            {"fund_code": "007119", "fund_name": "睿远成长价值", "scale_yi": 198, "ret_1y": 17.5, "ratio_net": 5.8, "market_value_wan": 114840},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 4.8, "market_value_wan": 185760},
            {"fund_code": "163406", "fund_name": "兴全合润分级", "scale_yi": 215, "ret_1y": 22.1, "ratio_net": 4.2, "market_value_wan": 90300},
            {"fund_code": "519694", "fund_name": "交银蓝筹", "scale_yi": 89, "ret_1y": 21.3, "ratio_net": 3.2, "market_value_wan": 28480},
        ],
        "trend": {
            "ma20_dir": "上涨", "ma60_dir": "上涨", "ma250_dir": "平",
            "ret_20d": 6.8, "ret_60d": 12.5,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 消费/食品（高位低分 陷阱）=====
    {
        "code": "603288", "name": "海天味业", "industry": "消费",
        "total_score": 32,
        "score_position": 22, "score_trend": 38, "score_capital": 42,
        "factors": {
            "pct_rank_1y": 78.5, "pct_rank_3y": 65.4,
            "drawdown_1y": -5.8, "vs_ma60_z": 1.45,
            "rsi_14": 68.5, "boll_pos": 82.4,
            "consecutive_down": 0, "volume_ratio_20d": 1.18,
        },
        "capital": {
            "fund_count": 5, "total_mv_yi": 15.8,
            "mv_change_pct_qoq": -8.5,
            "avg_fund_ret_1y": 9.5, "smart_money_index": 0.28,
        },
        "valuation": {"pe_ttm": 38.5, "pe_pct_rank_3y": 58, "pb": 7.2},
        "latest_price": 42.85,
        "market_cap_wan_yi": 0.21,
        "holders": [
            {"fund_code": "000083", "fund_name": "汇添富消费行业", "scale_yi": 142, "ret_1y": 16.8, "ratio_net": 4.5, "market_value_wan": 63900},
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 2.8, "market_value_wan": 128240},
        ],
        "trend": {
            "ma20_dir": "上涨", "ma60_dir": "平", "ma250_dir": "平",
            "ret_20d": 3.5, "ret_60d": 6.8,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 医药/CRO（低位高分 候选）=====
    {
        "code": "300347", "name": "泰格医药", "industry": "医药",
        "total_score": 72,
        "score_position": 78, "score_trend": 62, "score_capital": 76,
        "factors": {
            "pct_rank_1y": 18.5, "pct_rank_3y": 22.4,
            "drawdown_1y": -32.5, "vs_ma60_z": -1.68,
            "rsi_14": 28.4, "boll_pos": 8.5,
            "consecutive_down": 6, "volume_ratio_20d": 0.58,
        },
        "capital": {
            "fund_count": 6, "total_mv_yi": 18.5,
            "mv_change_pct_qoq": 8.5,
            "avg_fund_ret_1y": 18.5, "smart_money_index": 0.78,
        },
        "valuation": {"pe_ttm": 28.5, "pe_pct_rank_3y": 25, "pb": 3.2},
        "latest_price": 58.42,
        "market_cap_wan_yi": 0.10,
        "holders": [
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 4.8, "market_value_wan": 219840},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 4.2, "market_value_wan": 162540},
            {"fund_code": "007119", "fund_name": "睿远成长价值", "scale_yi": 198, "ret_1y": 17.5, "ratio_net": 3.8, "market_value_wan": 75240},
        ],
        "trend": {
            "ma20_dir": "下跌", "ma60_dir": "下跌", "ma250_dir": "平",
            "ret_20d": -8.5, "ret_60d": -16.5,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 科技/互联网（高位低分 陷阱）=====
    {
        "code": "600585", "name": "海螺水泥", "industry": "周期",
        "total_score": 38,
        "score_position": 32, "score_trend": 45, "score_capital": 42,
        "factors": {
            "pct_rank_1y": 72.5, "pct_rank_3y": 58.4,
            "drawdown_1y": -8.5, "vs_ma60_z": 1.25,
            "rsi_14": 62.5, "boll_pos": 75.4,
            "consecutive_down": 0, "volume_ratio_20d": 1.08,
        },
        "capital": {
            "fund_count": 3, "total_mv_yi": 8.5,
            "mv_change_pct_qoq": -6.5,
            "avg_fund_ret_1y": 8.5, "smart_money_index": 0.25,
        },
        "valuation": {"pe_ttm": 8.5, "pe_pct_rank_3y": 45, "pb": 0.9},
        "latest_price": 26.45,
        "market_cap_wan_yi": 0.14,
        "holders": [
            {"fund_code": "510300", "fund_name": "华泰柏瑞沪深300", "scale_yi": 892, "ret_1y": 6.8, "ratio_net": 0.5, "market_value_wan": 44600},
            {"fund_code": "100020", "fund_name": "富国天益价值", "scale_yi": 78, "ret_1y": 12.4, "ratio_net": 1.8, "market_value_wan": 14040},
        ],
        "trend": {
            "ma20_dir": "上涨", "ma60_dir": "上涨", "ma250_dir": "平",
            "ret_20d": 2.5, "ret_60d": 5.4,
        },
        "data_as_of": "2026-08-15",
    },
    # ===== 补充到 20 只 =====
    {
        "code": "601888", "name": "中国中免", "industry": "消费",
        "total_score": 64,
        "score_position": 60, "score_trend": 68, "score_capital": 65,
        "factors": {
            "pct_rank_1y": 38.5, "pct_rank_3y": 28.4,
            "drawdown_1y": -18.5, "vs_ma60_z": -0.42,
            "rsi_14": 48.5, "boll_pos": 42.5,
            "consecutive_down": 2, "volume_ratio_20d": 0.95,
        },
        "capital": {
            "fund_count": 8, "total_mv_yi": 35.8,
            "mv_change_pct_qoq": 5.5,
            "avg_fund_ret_1y": 16.5, "smart_money_index": 0.62,
        },
        "valuation": {"pe_ttm": 22.5, "pe_pct_rank_3y": 38, "pb": 3.5},
        "latest_price": 68.42,
        "market_cap_wan_yi": 0.13,
        "holders": [
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 4.8, "market_value_wan": 219840},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 5.2, "market_value_wan": 201240},
            {"fund_code": "000083", "fund_name": "汇添富消费行业", "scale_yi": 142, "ret_1y": 16.8, "ratio_net": 6.5, "market_value_wan": 92300},
        ],
        "trend": {
            "ma20_dir": "上涨", "ma60_dir": "平", "ma250_dir": "上涨",
            "ret_20d": 3.2, "ret_60d": 6.5,
        },
        "data_as_of": "2026-08-15",
    },
    {
        "code": "000333", "name": "美的集团", "industry": "消费",
        "total_score": 71,
        "score_position": 65, "score_trend": 72, "score_capital": 76,
        "factors": {
            "pct_rank_1y": 42.5, "pct_rank_3y": 52.4,
            "drawdown_1y": -12.5, "vs_ma60_z": -0.18,
            "rsi_14": 55.8, "boll_pos": 48.5,
            "consecutive_down": 1, "volume_ratio_20d": 1.02,
        },
        "capital": {
            "fund_count": 11, "total_mv_yi": 58.5,
            "mv_change_pct_qoq": 7.5,
            "avg_fund_ret_1y": 18.5, "smart_money_index": 0.74,
        },
        "valuation": {"pe_ttm": 14.5, "pe_pct_rank_3y": 42, "pb": 2.8},
        "latest_price": 68.25,
        "market_cap_wan_yi": 0.48,
        "holders": [
            {"fund_code": "005827", "fund_name": "易方达蓝筹精选", "scale_yi": 458, "ret_1y": 15.6, "ratio_net": 6.5, "market_value_wan": 297700},
            {"fund_code": "260108", "fund_name": "景顺长城新兴成长", "scale_yi": 387, "ret_1y": 19.8, "ratio_net": 5.8, "market_value_wan": 224460},
            {"fund_code": "163406", "fund_name": "兴全合润分级", "scale_yi": 215, "ret_1y": 22.1, "ratio_net": 4.5, "market_value_wan": 96750},
            {"fund_code": "007119", "fund_name": "睿远成长价值", "scale_yi": 198, "ret_1y": 17.5, "ratio_net": 5.2, "market_value_wan": 102960},
        ],
        "trend": {
            "ma20_dir": "上涨", "ma60_dir": "上涨", "ma250_dir": "上涨",
            "ret_20d": 4.5, "ret_60d": 8.5,
        },
        "data_as_of": "2026-08-15",
    },
]


# ---------- 查询函数 ----------

def _index() -> dict[str, dict]:
    """按 code 索引（首次调用时构建）"""
    if not hasattr(_index, "_cache"):
        _index._cache = {c["code"]: c for c in _CANDIDATES}
    return _index._cache


def get_candidates(
    industry: Optional[str] = None,
    min_score: Optional[float] = None,
) -> list[dict]:
    """获取候选列表（可按行业 / 最低分过滤），按 total_score 倒序"""
    items = list(_CANDIDATES)
    if industry:
        items = [c for c in items if c.get("industry") == industry]
    if min_score is not None:
        items = [c for c in items if c.get("total_score", 0) >= min_score]
    items.sort(key=lambda c: c.get("total_score", 0), reverse=True)
    return items


def get_factors(code: str) -> Optional[dict]:
    """获取单只股票的因子详情（不含 holders）。找不到返回 None"""
    c = _index().get(code)
    if not c:
        return None
    return {
        "code": c["code"],
        "name": c["name"],
        "industry": c["industry"],
        "latest_price": c.get("latest_price"),
        "market_cap_wan_yi": c.get("market_cap_wan_yi"),
        "total_score": c["total_score"],
        "score_position": c["score_position"],
        "score_trend": c["score_trend"],
        "score_capital": c["score_capital"],
        "factors": c["factors"],
        "capital": c["capital"],
        "valuation": c["valuation"],
        "trend": c["trend"],
        "data_as_of": c["data_as_of"],
    }


def get_holders(code: str) -> Optional[list[dict]]:
    """获取单只股票的重仓基金列表。找不到返回 None"""
    c = _index().get(code)
    if not c:
        return None
    return c.get("holders", [])


def get_industries() -> list[str]:
    """所有候选行业（去重，按出现顺序）"""
    seen: list[str] = []
    for c in _CANDIDATES:
        ind = c.get("industry")
        if ind and ind not in seen:
            seen.append(ind)
    return seen