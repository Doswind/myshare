import client from "./client";
import type { ChatAttachment } from "./openclaw";

export interface ChatSessionMeta {
  id: number;
  title: string;
  last_response_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ChatMessage {
  id: number;
  session_id: number;
  role: "user" | "assistant";
  content: string;
  status: "done" | "running" | "error";
  error: string | null;
  attachments: { name: string; media_type: string; kind: "image" | "file" }[];
  created_at: string | null;
}

export interface ChatSessionDetail extends ChatSessionMeta {
  messages: ChatMessage[];
}

export interface SendMessageResult {
  user_message_id: number;
  assistant_message_id: number;
}

export const createSession = () =>
  client.post<ChatSessionMeta>("/openclaw/sessions").then((r) => r.data);

export const listSessions = () =>
  client.get<ChatSessionMeta[]>("/openclaw/sessions").then((r) => r.data);

export const getSession = (sid: number) =>
  client.get<ChatSessionDetail>(`/openclaw/sessions/${sid}`).then((r) => r.data);

export const deleteSession = (sid: number) =>
  client.delete(`/openclaw/sessions/${sid}`).then((r) => r.data);

export const sendSessionMessage = (
  sid: number,
  body: { message: string; code?: string; attachments?: ChatAttachment[] },
) =>
  client
    .post<SendMessageResult>(`/openclaw/sessions/${sid}/messages`, body)
    .then((r) => r.data);

export interface StreamSessionCallbacks {
  /** 订阅时先收到已累积的全文（用于断线续接补齐） */
  onBacklog?: (text: string) => void;
  /** 实时增量 */
  onDelta?: (delta: string) => void;
  onDone?: () => void;
  onError?: (err: Error) => void;
}

/**
 * 订阅某条 assistant 消息的生成流（backlog + 实时增量）。
 * 首发与"切回续接"都用它：backlog 一次性补齐已生成内容，随后续接实时 delta。
 */
export async function streamSession(
  sid: number,
  messageId: number,
  cbs: StreamSessionCallbacks,
  signal?: AbortSignal,
) {
  const token = localStorage.getItem("access_token");
  const url = `/api/openclaw/sessions/${sid}/stream?message_id=${messageId}`;

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "text/event-stream",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      signal,
    });
  } catch (e: any) {
    cbs.onError?.(new Error(`网络请求失败：${e?.message || e}`));
    return;
  }

  if (!resp.ok || !resp.body) {
    let detail = "";
    try {
      detail = await resp.text();
    } catch {
      /* ignore */
    }
    cbs.onError?.(new Error(`HTTP ${resp.status}${detail ? `：${detail.slice(0, 200)}` : ""}`));
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
            cbs.onDone?.();
            try {
              await reader.cancel();
            } catch {
              /* ignore */
            }
            return;
          }
          try {
            const evt = JSON.parse(data);
            if (evt.type === "backlog") cbs.onBacklog?.(evt.text || "");
            else if (evt.type === "delta") cbs.onDelta?.(evt.delta || "");
            else if (evt.type === "error") cbs.onError?.(new Error(evt.error || "生成失败"));
            // type === "done" 由后续 [DONE] 收尾
          } catch {
            /* ignore parse error */
          }
        }
      }
    }
    cbs.onDone?.();
  } catch (e: any) {
    if (e?.name === "AbortError") return;
    cbs.onError?.(new Error(`SSE 流读取失败：${e?.message || e}`));
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* ignore */
    }
  }
}
