"""OpenClaw Gateway HTTP 客户端

官方接口：POST {base_url}/v1/responses （OpenResponses API，OpenAI 协议兼容）
- 认证：Authorization: Bearer <token>
- 流式：stream=true 返回 SSE
- 会话保持：previous_response_id 或 user 字段
- 远程访问：通过 ssh -N -L 18789:127.0.0.1:18789 user@网关机器

异常类型：
- OpenClawAuthError：401 / token 无效
- OpenClawTimeoutError：超时
- OpenClawUnavailableError：网络异常 / token 未配置 / 5xx
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OpenClawError(Exception):
    """OpenClaw 调用基类异常"""


class OpenClawAuthError(OpenClawError):
    """认证失败（401 / token 无效）"""


class OpenClawTimeoutError(OpenClawError):
    """调用超时"""


class OpenClawUnavailableError(OpenClawError):
    """不可达 / token 未配置 / 5xx"""


def _build_payload(
    message: str,
    previous_response_id: Optional[str] = None,
    user: Optional[str] = None,
    stream: bool = True,
) -> dict:
    """构造 OpenResponses 请求体

    参考 OpenResponses 协议：model + input + 可选 previous_response_id/user
    """
    payload: dict = {
        "model": settings.openclaw_agent_model,
        "stream": stream,
        "input": message,
    }
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    if user:
        payload["user"] = user
    return payload


def _build_headers() -> dict:
    """构造请求头：Bearer 鉴权 + SSE 接受"""
    return {
        "Authorization": f"Bearer {settings.openclaw_token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }


async def chat_stream(
    message: str,
    previous_response_id: Optional[str] = None,
    user: Optional[str] = None,
) -> AsyncIterator[dict]:
    """流式调用 /v1/responses，逐事件 yield 解析后的 dict。

    每个事件是 SSE data 行解析后的 JSON 对象（OpenResponses 原生字段）。
    流以 data: [DONE] 终止。

    Raises:
        OpenClawUnavailableError: token 未配置
        OpenClawAuthError: 401
        OpenClawTimeoutError: httpx 超时
        OpenClawUnavailableError: 其他网络/HTTP 错误
    """
    if not settings.openclaw_token:
        raise OpenClawUnavailableError("OPENCLAW_TOKEN 未配置")

    url = f"{settings.openclaw_base_url.rstrip('/')}/v1/responses"
    payload = _build_payload(message, previous_response_id, user, stream=True)
    headers = _build_headers()

    timeout = httpx.Timeout(settings.openclaw_timeout_sec, connect=5.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code == 401:
                    body = await resp.aread()
                    raise OpenClawAuthError(
                        f"OpenClaw 401 Unauthorized：token 无效或过期。"
                        f"请检查 .env 中的 OPENCLAW_TOKEN。body={body[:200]!r}"
                    )
                if resp.status_code >= 500:
                    body = await resp.aread()
                    raise OpenClawUnavailableError(
                        f"OpenClaw {resp.status_code}：{body[:200]!r}"
                    )
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise OpenClawUnavailableError(
                        f"OpenClaw {resp.status_code}：{body[:200]!r}"
                    )

                # 逐行解析 SSE
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    # SSE 规范：data: <payload>\n\n
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if not data or data == "[DONE]":
                        if data == "[DONE]":
                            return
                        continue
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        logger.warning("OpenClaw SSE 数据非 JSON：%r", data[:200])
                        continue
    except httpx.TimeoutException as e:
        raise OpenClawTimeoutError(f"OpenClaw 调用超时：{e}") from e
    except httpx.ConnectError as e:
        raise OpenClawUnavailableError(
            f"OpenClaw 不可达（{settings.openclaw_base_url}）：{e}"
        ) from e
    except (OpenClawAuthError, OpenClawTimeoutError, OpenClawUnavailableError):
        raise
    except Exception as e:
        raise OpenClawUnavailableError(f"OpenClaw 调用异常：{e}") from e


async def chat_sync(
    message: str,
    previous_response_id: Optional[str] = None,
    user: Optional[str] = None,
) -> dict:
    """同步（非流式）调用 /v1/responses，返回完整响应 dict。

    Raises: 同 chat_stream
    """
    if not settings.openclaw_token:
        raise OpenClawUnavailableError("OPENCLAW_TOKEN 未配置")

    url = f"{settings.openclaw_base_url.rstrip('/')}/v1/responses"
    payload = _build_payload(message, previous_response_id, user, stream=False)
    headers = _build_headers()

    timeout = httpx.Timeout(settings.openclaw_timeout_sec, connect=5.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 401:
                raise OpenClawAuthError(
                    f"OpenClaw 401 Unauthorized：token 无效或过期。"
                    f"请检查 .env 中的 OPENCLAW_TOKEN。"
                )
            if resp.status_code >= 500:
                raise OpenClawUnavailableError(f"OpenClaw {resp.status_code}")
            if resp.status_code >= 400:
                raise OpenClawUnavailableError(
                    f"OpenClaw {resp.status_code}：{resp.text[:200]}"
                )
            return resp.json()
    except httpx.TimeoutException as e:
        raise OpenClawTimeoutError(f"OpenClaw 调用超时：{e}") from e
    except httpx.ConnectError as e:
        raise OpenClawUnavailableError(
            f"OpenClaw 不可达（{settings.openclaw_base_url}）：{e}"
        ) from e
    except (OpenClawAuthError, OpenClawTimeoutError, OpenClawUnavailableError):
        raise
    except Exception as e:
        raise OpenClawUnavailableError(f"OpenClaw 调用异常：{e}") from e


async def health() -> dict:
    """探测 OpenClaw Gateway 可达性（用于前端顶部横幅）

    Returns: {ok, version, reachable}
    - 始终返回 ok=True（健康检查不应 5xx），不可达时 reachable=False
    """
    base = settings.openclaw_base_url.rstrip("/")
    url = f"{base}/health"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=2.0)) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                body: dict = {}
                try:
                    body = resp.json()
                except Exception:
                    pass
                return {
                    "ok": True,
                    "reachable": True,
                    "version": body.get("version"),
                    "has_token": bool(settings.openclaw_token),
                }
            return {"ok": True, "reachable": False, "version": None, "has_token": bool(settings.openclaw_token)}
    except Exception:
        return {"ok": True, "reachable": False, "version": None, "has_token": bool(settings.openclaw_token)}