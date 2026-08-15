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
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.chat import ChatSession, ChatMessage
from app.models.rbac import User
from app.services import screener_service
from app.services import openclaw_client
from app.services import openclaw_session_service

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(get_current_user)])


# ---------- 请求/响应模型 ----------

class ChatAttachment(BaseModel):
    name: str
    media_type: str
    kind: str  # 'image' | 'file'
    data: str  # base64（不含 data: 前缀）


class ChatRequest(BaseModel):
    message: str
    code: Optional[str] = None
    previous_response_id: Optional[str] = None
    user: Optional[str] = None
    attachments: Optional[List[ChatAttachment]] = None


class FeedbackRequest(BaseModel):
    code: Optional[str] = None
    previous_response_id: Optional[str] = None
    rating: str  # 'up' | 'down'
    comment: Optional[str] = None


class SessionMessageRequest(BaseModel):
    message: str
    code: Optional[str] = None
    attachments: Optional[List[ChatAttachment]] = None


def _own_session_or_404(db: Session, sid: int, user: User) -> ChatSession:
    sess = db.query(ChatSession).filter(
        ChatSession.id == sid, ChatSession.user_id == user.id
    ).first()
    if not sess:
        raise HTTPException(404, "会话不存在")
    return sess


# ---------- 内部辅助 ----------

def _build_enriched_message(code: Optional[str], raw_message: str) -> str:
    """如果有 code，把该股的真实因子 + 持仓拼到消息末尾（结构化 prompt 注入）"""
    if not code:
        return raw_message

    factors = screener_service.get_factors(None, code)
    if not factors:
        return raw_message + (
            f"\n\n---\n系统注：未找到股票 {code} 的因子数据，"
            f"请基于通用 A 股知识给出建议。"
        )

    holders = screener_service.get_holders(None, code) or []
    holders_text = "\n".join(
        f"  - {h['fund_name']}({h['fund_code']}) 规模{h['scale_yi']:.0f}亿 近1年{h['ret_1y']:.1f}% 占比{h['ratio_net']:.1f}% 市值{h['market_value_wan']:.0f}万"
        for h in holders
    ) or "  （无持仓数据）"

    f = factors["factors"]
    cap = factors["capital"]
    tr = factors["trend"]
    direction = factors.get("direction")
    dir_text = {"in": "主力进场（加仓/新进）", "out": "主力退场（减仓/退出）"}.get(direction, "方向不明显")
    mv = cap["mv_change_pct_qoq"]
    mv_text = "新进建仓（无上期基数）" if mv is None else f"{mv:+.1f}%"

    return raw_message + f"""

---
【系统注入数据 — 股票 {code}】

【股票基本信息】
代码：{code}
名称：{factors['name']}
行业：{factors['industry']}
最新价：{factors.get('latest_price')}
主力方向：{dir_text}

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

【主力资金行为（本系统独占，季度环比）】
持有该股的主力基金数：{cap['fund_count']}
合计持仓市值：{cap['total_mv_yi']} 亿
上季度环比加减仓：{mv_text}
加仓 {cap['funds_add']} 只 / 减仓 {cap['funds_cut']} 只 / 新进 {cap['funds_new']} 只 / 退出 {cap['funds_exit']} 只
持仓基金近 1 年收益中位数：{cap['avg_fund_ret_1y']:.1f}%
持仓基金近 1 年跑赢比例：{cap['smart_money_index']:.2f}

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
    attachments = [a.model_dump() for a in req.attachments] if req.attachments else None

    async def event_generator():
        try:
            async for event in openclaw_client.chat_stream(
                message=enriched,
                previous_response_id=req.previous_response_id,
                user=req.user,
                attachments=attachments,
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


# ---------- 会话（按用户隔离 + 后台续跑） ----------

@router.post("/sessions")
async def create_session(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """新建空会话"""
    sess = ChatSession(user_id=user.id, title="新会话")
    db.add(sess)
    db.commit()
    return sess.to_dict()


@router.get("/sessions")
async def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """当前用户会话列表（按 updated_at desc）"""
    rows = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return [s.to_dict() for s in rows]


@router.get("/sessions/{sid}")
async def get_session(sid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """会话详情 + 全部消息"""
    sess = _own_session_or_404(db, sid, user)
    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == sid)
        .order_by(ChatMessage.id.asc())
        .all()
    )
    return {**sess.to_dict(), "messages": [m.to_dict() for m in msgs]}


@router.delete("/sessions/{sid}")
async def delete_session(sid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """删除会话及其消息"""
    sess = _own_session_or_404(db, sid, user)
    db.query(ChatMessage).filter(ChatMessage.session_id == sid).delete()
    db.delete(sess)
    db.commit()
    return {"ok": True}


@router.post("/sessions/{sid}/messages")
async def send_session_message(
    sid: int,
    req: SessionMessageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """发送消息：落库 user 消息 + 建 assistant(running) + 起后台生成任务"""
    if not req.message or not req.message.strip():
        raise HTTPException(400, "message 不能为空")
    sess = _own_session_or_404(db, sid, user)

    # 同一会话同时只允许一个进行中的生成
    running = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == sid, ChatMessage.status == "running")
        .first()
    )
    if running:
        raise HTTPException(409, "该会话有正在生成的回复，请稍候")

    att_meta = (
        [{"name": a.name, "media_type": a.media_type, "kind": a.kind} for a in req.attachments]
        if req.attachments else None
    )
    user_msg = ChatMessage(
        session_id=sid, role="user", content=req.message.strip(),
        status="done", attachments=att_meta,
    )
    db.add(user_msg)
    assistant_msg = ChatMessage(session_id=sid, role="assistant", content="", status="running")
    db.add(assistant_msg)
    db.commit()

    enriched = _build_enriched_message(req.code, req.message.strip())
    attachments = [a.model_dump() for a in req.attachments] if req.attachments else None
    openclaw_session_service.start_generation(
        assistant_msg_id=assistant_msg.id,
        session_id=sid,
        message=enriched,
        previous_response_id=sess.last_response_id,
        attachments=attachments,
    )
    return {"user_message_id": user_msg.id, "assistant_message_id": assistant_msg.id}


@router.get("/sessions/{sid}/stream")
async def stream_session_message(
    sid: int,
    message_id: int = Query(..., description="assistant 消息 id"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """SSE 订阅某条 assistant 消息的生成（backlog + 实时；首发/续接通用）"""
    _own_session_or_404(db, sid, user)
    msg = db.query(ChatMessage).filter(
        ChatMessage.id == message_id, ChatMessage.session_id == sid
    ).first()
    if not msg:
        raise HTTPException(404, "消息不存在")

    async def event_generator():
        async for item in openclaw_session_service.subscribe(message_id):
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )