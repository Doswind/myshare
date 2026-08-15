"""OpenClaw 会话后台生成 + 订阅（断线续跑核心）

设计：把"生成"与"客户端连接"解耦。
- 发送消息时创建 assistant 消息行(status=running)，并起一个进程内 asyncio 后台任务 _run。
- _run 消费 openclaw_client.chat_stream，把增量累积到 GenState.text，广播给所有订阅队列，
  并节流写库（生成中内容持续落库）。结束时写 done/error、更新会话 last_response_id/title。
- 客户端通过 subscribe() 订阅：先拿到已累积的 backlog，再续接实时增量。
- 客户端断开只移除自己的订阅队列，不影响后台任务 —— 因此切页/关窗后生成继续。
- 生成已结束（不在 ACTIVE）时，subscribe 直接读库返回完整内容。

限制：单进程内存 pub/sub（当前单 worker uvicorn async 足够）。进程重启后 ACTIVE 丢失，
残留 running 由 reset_stale_running() 在启动时收敛为 done/error。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.database import SessionLocal
from app.models.chat import ChatSession, ChatMessage
from app.services import openclaw_client

logger = logging.getLogger(__name__)

# 结束哨兵
_DONE = {"type": "done"}

# 节流写库参数
_FLUSH_CHARS = 40
_FLUSH_INTERVAL = 0.8


@dataclass
class GenState:
    text: str = ""
    done: bool = False
    error: Optional[str] = None
    response_id: Optional[str] = None
    subscribers: set = field(default_factory=set)


# assistant_msg_id -> GenState
ACTIVE: dict[int, GenState] = {}


def _extract_delta(event: dict) -> str:
    if not isinstance(event, dict):
        return ""
    t = event.get("type") or ""
    if isinstance(t, str) and t.endswith(".delta") and isinstance(event.get("delta"), str):
        return event["delta"]
    return ""


def _extract_response_id(event: dict) -> Optional[str]:
    if not isinstance(event, dict):
        return None
    if event.get("type") == "response.completed":
        resp = event.get("response") or {}
        if isinstance(resp, dict) and resp.get("id"):
            return resp["id"]
    return None


def is_active(assistant_msg_id: int) -> bool:
    return assistant_msg_id in ACTIVE


def _broadcast(state: GenState, item: dict) -> None:
    for q in list(state.subscribers):
        try:
            q.put_nowait(item)
        except Exception:
            pass


def _persist_content(assistant_msg_id: int, content: str,
                     status: str, error: Optional[str] = None) -> None:
    """更新 assistant 消息内容/状态（独立 session，短事务）"""
    db = SessionLocal()
    try:
        msg = db.query(ChatMessage).filter(ChatMessage.id == assistant_msg_id).first()
        if not msg:
            return
        msg.content = content
        msg.status = status
        msg.error = error
        db.commit()
    finally:
        db.close()


def _finalize_session(session_id: int, response_id: Optional[str]) -> None:
    """结束时更新会话 last_response_id + updated_at + title（若仍是默认）"""
    db = SessionLocal()
    try:
        sess = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not sess:
            return
        if response_id:
            sess.last_response_id = response_id
        sess.updated_at = datetime.utcnow()
        # title：若仍是默认，取该会话首条 user 消息摘要
        if not sess.title or sess.title == "新会话":
            first_user = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id, ChatMessage.role == "user")
                .order_by(ChatMessage.id.asc())
                .first()
            )
            if first_user and first_user.content:
                sess.title = first_user.content.strip().replace("\n", " ")[:30] or "新会话"
        db.commit()
    finally:
        db.close()


async def _run(assistant_msg_id: int, session_id: int, message: str,
               previous_response_id: Optional[str], attachments: Optional[list],
               user: Optional[str] = None) -> None:
    """后台生成任务：消费 SSE，累积 + 广播 + 节流落库，结束落定。"""
    state = ACTIVE[assistant_msg_id]
    loop = asyncio.get_event_loop()
    last_flush_t = loop.time()
    last_flush_len = 0
    try:
        async for event in openclaw_client.chat_stream(
            message=message,
            previous_response_id=previous_response_id,
            attachments=attachments,
            user=user,
        ):
            # 上游错误事件
            if isinstance(event, dict) and event.get("type") == "error":
                err = (event.get("error") or {}).get("message") or "生成失败"
                raise RuntimeError(err)
            delta = _extract_delta(event)
            rid = _extract_response_id(event)
            if rid:
                state.response_id = rid
            if not delta:
                continue
            state.text += delta
            _broadcast(state, {"type": "delta", "delta": delta})
            now = loop.time()
            if (len(state.text) - last_flush_len >= _FLUSH_CHARS
                    or now - last_flush_t >= _FLUSH_INTERVAL):
                _persist_content(assistant_msg_id, state.text, "running")
                last_flush_t = now
                last_flush_len = len(state.text)

        # 正常结束
        state.done = True
        _persist_content(assistant_msg_id, state.text, "done")
        _finalize_session(session_id, state.response_id)
        _broadcast(state, _DONE)
    except Exception as e:  # noqa: BLE001
        logger.warning("[chat] 生成失败 msg=%s: %s", assistant_msg_id, e)
        state.done = True
        state.error = str(e)
        _persist_content(assistant_msg_id, state.text, "error", str(e))
        _finalize_session(session_id, state.response_id)
        _broadcast(state, {"type": "error", "error": str(e)})
    finally:
        # 让当前订阅者收完哨兵后清理；新订阅者会走 DB
        ACTIVE.pop(assistant_msg_id, None)


def start_generation(assistant_msg_id: int, session_id: int, message: str,
                     previous_response_id: Optional[str] = None,
                     attachments: Optional[list] = None,
                     user: Optional[str] = None) -> None:
    """注册 GenState 并起后台任务。要求 assistant 消息行已建好(status=running)。"""
    ACTIVE[assistant_msg_id] = GenState()
    asyncio.create_task(
        _run(assistant_msg_id, session_id, message, previous_response_id, attachments, user)
    )


async def subscribe(assistant_msg_id: int):
    """订阅某条 assistant 消息的生成：先 backlog，再实时 delta，至 done/error。

    - 在 ACTIVE：快照已累积文本作为 backlog（与注册队列间无 await，无丢失），续接实时。
    - 不在 ACTIVE（已结束/进程重启后）：读库返回完整内容 + 终态。
    """
    state = ACTIVE.get(assistant_msg_id)
    if state is None:
        # 已结束：读库
        db = SessionLocal()
        try:
            msg = db.query(ChatMessage).filter(ChatMessage.id == assistant_msg_id).first()
        finally:
            db.close()
        if not msg:
            yield {"type": "error", "error": "消息不存在"}
            return
        yield {"type": "backlog", "text": msg.content or ""}
        if msg.status == "error":
            yield {"type": "error", "error": msg.error or "生成失败"}
        else:
            yield _DONE
        return

    # 进行中：快照 + 注册（同步，无 await，避免丢增量）
    q: asyncio.Queue = asyncio.Queue()
    backlog = state.text
    already_done = state.done
    state.subscribers.add(q)
    try:
        yield {"type": "backlog", "text": backlog}
        if already_done:
            if state.error:
                yield {"type": "error", "error": state.error}
            else:
                yield _DONE
            return
        while True:
            item = await q.get()
            if item.get("type") in ("done", "error"):
                yield item
                return
            yield item
    finally:
        state.subscribers.discard(q)


def reset_stale_running() -> None:
    """启动时收敛残留 running 消息（进程重启后 ACTIVE 已丢失）：
    有内容→done；无内容→error。"""
    db = SessionLocal()
    try:
        rows = db.query(ChatMessage).filter(ChatMessage.status == "running").all()
        for m in rows:
            if m.content:
                m.status = "done"
            else:
                m.status = "error"
                m.error = "服务重启，生成中断"
        if rows:
            db.commit()
            logger.info("[chat] 启动收敛 %d 条残留 running 消息", len(rows))
    finally:
        db.close()
