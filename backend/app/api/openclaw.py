"""OpenClaw Gateway 代理 API

GET  /api/openclaw/health       — 探测 Gateway 可达性（用于前端顶部横幅）
POST /api/openclaw/chat         — 流式调用 /v1/responses（SSE 透传）
POST /api/openclaw/chat/sync    — 同步调用（demo 期只打日志）
POST /api/openclaw/feedback     — 用户反馈（demo 期只打日志）

所有路由需要登录（沿用现有 auth 中间件）。
"""
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.deps import get_current_user
from app.services import screener_mock
from app.services import openclaw_client

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(get_current_user)])


# ---------- 请求/响应模型 ----------

class ChatRequest(BaseModel):
    message: str
    code: Optional[str] = None
    previous_response_id: Optional[str] = None
    user: Optional[str] = None


class FeedbackRequest(BaseModel):
    code: Optional[str] = None
    previous_response_id: Optional[str] = None
    rating: str  # 'up' | 'down'
    comment: Optional[str] = None


# ---------- 内部辅助 ----------

def _build_enriched_message(code: Optional[str], raw_message: str) -> str:
    """如果有 code，把该股的因子 + 持仓拼到消息末尾（结构化 prompt 注入）

    格式见 doc.md §5.5 模板。
    """
    if not code:
        return raw_message

    factors = screener_mock.get_factors(code)
    if not factors:
        return raw_message + (
            f"\n\n---\n系统注：未找到股票 {code} 的因子数据，"
            f"请基于通用 A 股知识给出建议。"
        )

    holders = screener_mock.get_holders(code) or []
    holders_text = "\n".join(
        f"  - {h['fund_name']}({h['fund_code']}) 规模{h['scale_yi']}亿 近1年{h['ret_1y']}% 占比{h['ratio_net']}% 市值{h['market_value_wan']}万"
        for h in holders
    ) or "  （无持仓数据）"

    f = factors["factors"]
    cap = factors["capital"]
    val = factors["valuation"]
    tr = factors["trend"]

    return raw_message + f"""

---
【系统注入数据 — 股票 {code}】

【股票基本信息】
代码：{code}
名称：{factors['name']}
行业：{factors['industry']}
最新价：{factors.get('latest_price')}
总市值：{factors.get('market_cap_wan_yi')} 万亿

【位置因子（事实标注，非预测）】
近 1 年价格百分位：{f['pct_rank_1y']:.1f}%
近 3 年价格百分位：{f['pct_rank_3y']:.1f}%
距近 1 年高点回撤：{f['drawdown_1y']:.1f}%
相对 MA60 的 z-score：{f['vs_ma60_z']:.2f}
RSI(14)：{f['rsi_14']:.1f}
布林带位置：{f['boll_pos']:.1f}%
连续下跌天数：{f['consecutive_down']}
20 日均量比：{f['volume_ratio_20d']:.2f}

【趋势与动量】
MA20 / MA60 / MA250：{tr['ma20_dir']} / {tr['ma60_dir']} / {tr['ma250_dir']}
近 20 日收益率：{tr['ret_20d']:.1f}%
近 60 日收益率：{tr['ret_60d']:.1f}%

【主力资金行为（本系统独占）】
持有该股的主力基金数：{cap['fund_count']}
合计持仓市值：{cap['total_mv_yi']} 亿
上季度环比加减仓：{cap['mv_change_pct_qoq']:+.1f}%
持仓基金平均近 1 年收益：{cap['avg_fund_ret_1y']:.1f}%
"聪明钱"质量分：{cap['smart_money_index']:.2f}

【估值】
PE-TTM：{val['pe_ttm']}（近 3 年百分位 {val['pe_pct_rank_3y']}%）
PB：{val['pb']}

【重仓基金明细】
{holders_text}

---
请基于以上系统提供的真实数据，给出结构化结论（Markdown 格式）：
1. **整体判断**：看好 / 中性 / 谨慎
2. **看多逻辑**：3-5 条
3. **看空/风险**：3-5 条
4. **关键催化剂**：近期需要关注的变量
5. **数据缺口**：你希望看但系统未提供的数据

请尽量结构化，便于人类快速阅读。"""


# ---------- 路由 ----------

@router.get("/health")
async def health():
    """OpenClaw Gateway 可达性（始终 200，由 reachable 字段判断）"""
    return await openclaw_client.health()


@router.post("/chat")
async def chat(req: ChatRequest):
    """流式调用 OpenClaw /v1/responses，SSE 透传回前端

    错误处理：token 缺失 → 503；401 → 401；超时 → 504；其他 5xx → 503。
    """
    if not req.message or not req.message.strip():
        raise HTTPException(400, "message 不能为空")

    enriched = _build_enriched_message(req.code, req.message)

    async def event_generator():
        try:
            async for event in openclaw_client.chat_stream(
                message=enriched,
                previous_response_id=req.previous_response_id,
                user=req.user,
            ):
                # 每个事件按 SSE 规范序列化
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except openclaw_client.OpenClawAuthError as e:
            logger.warning("OpenClaw auth failed for code=%s: %s", req.code, e)
            yield f"data: {json.dumps({'type': 'error', 'error': {'code': 'auth', 'message': str(e)}}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except openclaw_client.OpenClawTimeoutError as e:
            logger.warning("OpenClaw timeout for code=%s: %s", req.code, e)
            yield f"data: {json.dumps({'type': 'error', 'error': {'code': 'timeout', 'message': str(e)}}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except openclaw_client.OpenClawUnavailableError as e:
            logger.warning("OpenClaw unavailable for code=%s: %s", req.code, e)
            yield f"data: {json.dumps({'type': 'error', 'error': {'code': 'unavailable', 'message': str(e)}}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("Unexpected OpenClaw error")
            yield f"data: {json.dumps({'type': 'error', 'error': {'code': 'unknown', 'message': str(e)}}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
            "Connection": "keep-alive",
        },
    )


@router.post("/chat/sync")
async def chat_sync(req: ChatRequest):
    """同步调用（demo 期只打日志 + 返回响应长度）"""
    enriched = _build_enriched_message(req.code, req.message)
    start = time.time()
    try:
        resp = await openclaw_client.chat_sync(
            message=enriched,
            previous_response_id=req.previous_response_id,
            user=req.user,
        )
        elapsed = time.time() - start
        # demo 期落库只打日志
        logger.info(
            "[openclaw.chat_sync] code=%s elapsed=%.2fs response_len=%d",
            req.code, elapsed, len(json.dumps(resp, ensure_ascii=False)),
        )
        return {
            "ok": True,
            "elapsed_sec": round(elapsed, 2),
            "response_keys": list(resp.keys()) if isinstance(resp, dict) else None,
            "response_id": (resp.get("id") if isinstance(resp, dict) else None),
        }
    except openclaw_client.OpenClawError as e:
        logger.warning("[openclaw.chat_sync] failed code=%s: %s", req.code, e)
        raise HTTPException(503, f"OpenClaw 调用失败：{e}")


@router.post("/feedback")
async def feedback(req: FeedbackRequest):
    """用户反馈（demo 期只打日志）"""
    logger.info(
        "[openclaw.feedback] code=%s previous_response_id=%s rating=%s comment=%s",
        req.code, req.previous_response_id, req.rating, req.comment,
    )
    return {"ok": True}