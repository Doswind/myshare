import client from "./client";
import { streamChat, type StreamChatCallbacks } from "@/lib/sseStream";

export interface OpenClawHealth {
  ok: boolean;
  reachable: boolean;
  version: string | null;
  has_token: boolean;
}

export const fetchOpenclawHealth = () =>
  client.get<OpenClawHealth>("/openclaw/health").then((r) => r.data);

export interface StreamChatArgs {
  message: string;
  code?: string;
  previousResponseId?: string;
  user?: string;
  signal?: AbortSignal;
}

/**
 * 流式调用 OpenClaw chat（内部用 fetch+ReadableStream 解析 SSE）
 *
 * fetch 不走 axios interceptor，所以需要手动从 localStorage 拿 token 加 Authorization
 * （参考 client.ts 的实现）
 */
export async function openclawStreamChat(args: StreamChatArgs, cbs: StreamChatCallbacks) {
  const token = localStorage.getItem("access_token");
  // 重写 fetch 加上 Authorization 头（最小侵入：包装一层）
  const originalOnDelta = cbs.onDelta;
  const wrappedCbs: StreamChatCallbacks = {
    onDelta: originalOnDelta,
    onDone: cbs.onDone,
    onError: cbs.onError,
  };

  // 由于 streamChat 内部用 fetch 且默认只设 Content-Type/Accept，
  // 这里我们改成直接调 fetch：透传 token
  const url = "/api/openclaw/chat";
  const body: any = {
    message: args.message,
    previous_response_id: args.previousResponseId,
    user: args.user,
  };
  if (args.code) body.code = args.code;

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal: args.signal,
    });
  } catch (e: any) {
    wrappedCbs.onError?.(new Error(`网络请求失败：${e?.message || e}`));
    return;
  }

  if (!resp.ok || !resp.body) {
    let detail = "";
    try {
      detail = await resp.text();
    } catch {
      /* ignore */
    }
    wrappedCbs.onError?.(new Error(`HTTP ${resp.status}${detail ? `：${detail.slice(0, 200)}` : ""}`));
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let done = false;
  try {
    while (!done) {
      const { value, done: rd } = await reader.read();
      done = rd;
      if (value) buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        for (const line of block.split("\n")) {
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (!data) continue;
          if (data === "[DONE]") {
            wrappedCbs.onDone?.();
            try {
              await reader.cancel();
            } catch {
              /* ignore */
            }
            return;
          }
          try {
            wrappedCbs.onDelta?.(JSON.parse(data));
          } catch (e: any) {
            wrappedCbs.onError?.(new Error(`SSE 数据解析失败：${e?.message || e}`));
          }
        }
      }
    }
    wrappedCbs.onDone?.();
  } catch (e: any) {
    if (e?.name === "AbortError") return;
    wrappedCbs.onError?.(new Error(`SSE 流读取失败：${e?.message || e}`));
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* ignore */
    }
  }
}

/** 同步调用（demo 期仅返回 ok） */
export const openclawChatSync = (body: StreamChatArgs) =>
  client.post("/openclaw/chat/sync", body).then((r) => r.data);

/** 反馈 */
export const openclawFeedback = (body: {
  code?: string;
  previous_response_id?: string;
  rating: "up" | "down";
  comment?: string;
}) => client.post("/openclaw/feedback", body).then((r) => r.data);