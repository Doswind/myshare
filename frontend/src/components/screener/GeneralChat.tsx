import { useCallback, useEffect, useRef, useState } from "react";
import { Send, Square, Sparkles, Zap, X, AlertTriangle } from "lucide-react";
import clsx from "clsx";

import { MarkdownMessage } from "./MarkdownMessage";
import { AttachmentBar, filesToAttachments, type LocalAttachment } from "./AttachmentBar";
import { useMention } from "./MentionAutocomplete";
import { SessionList } from "./SessionList";
import {
  listSessions,
  getSession,
  createSession,
  deleteSession,
  sendSessionMessage,
  streamSession,
  type ChatSessionMeta,
  type ChatMessage,
} from "@/api/openclawSessions";

type SendMode = "enter" | "mod-enter";
const SEND_MODE_KEY = "openclaw:sendMode";
const ACTIVE_KEY = "openclaw:activeSession";

function loadSendMode(): SendMode {
  try {
    return localStorage.getItem(SEND_MODE_KEY) === "enter" ? "enter" : "mod-enter";
  } catch {
    return "mod-enter";
  }
}

interface Props {
  placeholder?: string;
  /** embedded：内嵌带会话列表；drawer：右侧抽屉（单股析股），无列表 */
  variant?: "embedded" | "drawer";
  /** drawer 专用：开关 */
  open?: boolean;
  /** drawer 专用：关闭回调 */
  onClose?: () => void;
  /** 单股析股：随每条消息发送的股票代码（后端据此注入真实数据） */
  code?: string;
  /** 打开时预填到输入框的文本（如结构化 prompt） */
  initialInput?: string;
  /** 顶栏标题 */
  title?: string;
}

export function GeneralChat({
  placeholder,
  variant = "embedded",
  open,
  onClose,
  code,
  initialInput,
  title,
}: Props) {
  const isDrawer = variant === "drawer";
  const showList = variant === "embedded";

  const [sessions, setSessions] = useState<ChatSessionMeta[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<LocalAttachment[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [sendMode, setSendMode] = useState<SendMode>(() => loadSendMode());

  const abortRef = useRef<AbortController | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const mention = useMention(input, setInput, inputRef);

  // PLACEHOLDER_HELPERS
  const scrollToBottom = useCallback(() => {
    if (messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
  }, []);

  const updateMsg = useCallback((id: number, updater: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? updater(m) : m)));
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const rows = await listSessions();
      setSessions(rows);
      return rows;
    } catch {
      return [];
    }
  }, []);

  // 订阅（首发 / 续接通用）：backlog 覆盖，delta 追加，done/error 落定
  const subscribe = useCallback(
    (sid: string, assistantId: number) => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setStreaming(true);
      streamSession(
        sid,
        assistantId,
        {
          onBacklog: (text) => updateMsg(assistantId, (m) => ({ ...m, content: text, status: "running" })),
          onDelta: (delta) => updateMsg(assistantId, (m) => ({ ...m, content: m.content + delta })),
          onDone: () => {
            setStreaming(false);
            updateMsg(assistantId, (m) => (m.status === "running" ? { ...m, status: "done" } : m));
            refreshSessions();
          },
          onError: (err) => {
            setStreaming(false);
            updateMsg(assistantId, (m) => ({ ...m, status: "error", error: err.message }));
          },
        },
        ctrl.signal,
      );
    },
    [updateMsg, refreshSessions],
  );

  // 加载会话详情；若末条 assistant 仍 running → 自动续接
  const loadSession = useCallback(
    async (sid: string) => {
      abortRef.current?.abort();
      setErrorMsg(null);
      try {
        const detail = await getSession(sid);
        setMessages(detail.messages);
        const last = detail.messages[detail.messages.length - 1];
        if (last && last.role === "assistant" && last.status === "running") {
          subscribe(sid, last.id);
        } else {
          setStreaming(false);
        }
      } catch (e: any) {
        setErrorMsg(e?.message || "加载会话失败");
      }
    },
    [subscribe],
  );

  // PLACEHOLDER_EFFECTS
  // 内嵌模式挂载：拉会话列表，恢复上次会话（或选第一条）
  useEffect(() => {
    if (isDrawer) return;
    let cancelled = false;
    (async () => {
      setSessionsLoading(true);
      const rows = await refreshSessions();
      setSessionsLoading(false);
      if (cancelled) return;
      let target: string | null = null;
      try {
        const stored = localStorage.getItem(ACTIVE_KEY);
        if (stored && rows.some((s) => s.id === stored)) target = stored;
      } catch {
        /* ignore */
      }
      if (!target && rows.length) target = rows[0].id;
      if (target) {
        setActiveId(target);
        loadSession(target);
      }
    })();
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 抽屉模式：每次打开开一段全新会话（懒创建，首发时才落库），预填 prompt
  useEffect(() => {
    if (!isDrawer) return;
    if (open) {
      abortRef.current?.abort();
      setActiveId(null);
      setMessages([]);
      setErrorMsg(null);
      setStreaming(false);
      setAttachments([]);
      setInput(initialInput ?? "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialInput]);

  // 记住当前会话（仅内嵌模式，避免抽屉覆盖通用对话的最近会话）
  useEffect(() => {
    if (isDrawer) return;
    if (activeId) {
      try {
        localStorage.setItem(ACTIVE_KEY, String(activeId));
      } catch {
        /* ignore */
      }
    }
  }, [activeId, isDrawer]);

  // 自动滚到底
  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // PLACEHOLDER_ACTIONS
  function selectSession(id: string) {
    if (id === activeId) return;
    setActiveId(id);
    loadSession(id);
  }

  async function newSession() {
    abortRef.current?.abort();
    setStreaming(false);
    setErrorMsg(null);
    setMessages([]);
    try {
      const s = await createSession();
      setSessions((prev) => [s, ...prev]);
      setActiveId(s.id);
    } catch (e: any) {
      setErrorMsg(e?.message || "新建会话失败");
    }
  }

  async function removeSession(id: string) {
    try {
      await deleteSession(id);
    } catch {
      /* ignore */
    }
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (id === activeId) {
      abortRef.current?.abort();
      setStreaming(false);
      setMessages([]);
      setActiveId(null);
      const remaining = sessions.filter((s) => s.id !== id);
      if (remaining.length) selectSession(remaining[0].id);
    }
  }

  async function handleSend() {
    const text = input.trim();
    if ((!text && attachments.length === 0) || streaming) return;
    setErrorMsg(null);
    mention.close();

    const sentAtt = attachments;
    setInput("");
    setAttachments([]);

    // 确保有会话
    let sid = activeId;
    if (!sid) {
      try {
        const s = await createSession();
        setSessions((prev) => [s, ...prev]);
        setActiveId(s.id);
        sid = s.id;
      } catch (e: any) {
        setErrorMsg(e?.message || "新建会话失败");
        return;
      }
    }

    // 乐观插入用户气泡（随后 loadSession 用权威数据覆盖）
    const tempUser: ChatMessage = {
      id: -Date.now(),
      session_id: sid,
      role: "user",
      content: text,
      status: "done",
      error: null,
      attachments: sentAtt.map((a) => ({ name: a.name, media_type: a.media_type, kind: a.kind })),
      created_at: null,
    };
    setMessages((prev) => [...prev, tempUser]);

    try {
      await sendSessionMessage(sid, {
        message: text,
        code: code || undefined,
        attachments: sentAtt.length
          ? sentAtt.map((a) => ({ name: a.name, media_type: a.media_type, kind: a.kind, data: a.data }))
          : undefined,
      });
      await loadSession(sid); // 拉权威消息并自动续接生成流
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || "发送失败";
      setErrorMsg(msg);
      setMessages((prev) => prev.filter((m) => m.id !== tempUser.id));
    }
  }

  function toggleSendMode() {
    const next: SendMode = sendMode === "enter" ? "mod-enter" : "enter";
    setSendMode(next);
    try {
      localStorage.setItem(SEND_MODE_KEY, next);
    } catch {
      /* ignore */
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (mention.onKeyDown(e)) return;
    if (sendMode === "enter") {
      if (e.key === "Enter" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        handleSend();
      }
    } else if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSend();
    }
  }

  async function addFiles(files: FileList | File[]) {
    const { added, errors } = await filesToAttachments(Array.from(files), attachments);
    if (added.length) setAttachments((prev) => [...prev, ...added]);
    if (errors.length) setErrorMsg(errors.join("；"));
  }

  function handlePaste(e: React.ClipboardEvent<HTMLTextAreaElement>) {
    const files = Array.from(e.clipboardData?.files || []);
    if (files.length) {
      e.preventDefault();
      addFiles(files);
    }
  }

  function handleDrop(e: React.DragEvent) {
    const files = Array.from(e.dataTransfer?.files || []);
    if (files.length) {
      e.preventDefault();
      addFiles(files);
    }
  }

  const canSend = !streaming && (input.trim().length > 0 || attachments.length > 0);
  const inputPlaceholder = placeholder ?? "输入 # 股票 / $ 板块 / / 命令 可快速联想，随便问点什么…";

  // PLACEHOLDER_RENDER
  if (isDrawer && !open) return null;

  const headerTitle = title ?? "通用 AI 对话";

  const inner = (
    <div
      className={clsx(
        "flex bg-white",
        isDrawer ? "h-full w-full sm:w-[560px] shadow-xl border-l border-slate-200" : "h-[520px]",
      )}
    >
      {showList && (
        <SessionList
          sessions={sessions}
          activeId={activeId}
          loading={sessionsLoading}
          onSelect={selectSession}
          onNew={newSession}
          onDelete={removeSession}
        />
      )}
      <div className="flex flex-col flex-1 min-w-0">
        {/* 顶栏 */}
        <div className="flex items-center gap-1.5 px-3 py-2 border-b border-slate-200 bg-slate-50 text-[12px] text-slate-700 font-medium">
          <Sparkles className="w-3.5 h-3.5 text-blue-500" />
          <span>{headerTitle}</span>
          <span className="text-[10px] text-slate-400 font-normal ml-1">
            对话保存在服务端 · 生成中可切页，后台继续
          </span>
          {isDrawer && onClose && (
            <button
              onClick={onClose}
              className="ml-auto text-slate-400 hover:text-slate-700"
              title="关闭"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* 消息列表 */}
        <div ref={messagesRef} className="flex-1 overflow-auto p-3 space-y-2 bg-slate-50/30">
          {messages.length === 0 ? (
            <div className="text-center text-slate-400 py-10 text-[11px]">
              开始对话吧 — 输入 # 股票 / $ 板块 / / 命令 可快速联想
            </div>
          ) : (
            messages.map((m) => (
              <div
                key={m.id}
                className={clsx("flex", m.role === "user" ? "justify-end" : "justify-start")}
              >
                <div
                  className={clsx(
                    "max-w-[90%] rounded-lg px-3 py-2 text-[12px] leading-relaxed",
                    m.role === "user"
                      ? "bg-blue-500 text-white whitespace-pre-wrap"
                      : "bg-white border border-slate-200 text-slate-800",
                  )}
                >
                  {m.role === "assistant" ? (
                    m.status === "error" ? (
                      <span className="text-red-500">{m.error || "生成失败"}</span>
                    ) : m.content ? (
                      <>
                        <MarkdownMessage content={m.content} />
                        {m.status === "running" && (
                          <span className="inline-block w-1.5 h-3 bg-blue-400 animate-pulse ml-0.5" />
                        )}
                      </>
                    ) : (
                      <span className="text-slate-400">生成中…</span>
                    )
                  ) : (
                    <>
                      {m.content}
                      {m.attachments?.length > 0 && (
                        <span className="block mt-1 text-[10px] text-blue-100">
                          [附件 {m.attachments.length} 个：{m.attachments.map((a) => a.name).join("、")}]
                        </span>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))
          )}
          {errorMsg && (
            <div className="rounded border border-yellow-300 bg-yellow-50 px-2.5 py-1.5 flex items-start gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-yellow-600 shrink-0 mt-0.5" />
              <div className="text-[11px] text-yellow-800 flex-1">{errorMsg}</div>
            </div>
          )}
        </div>

        {/* PLACEHOLDER_INPUT */}
        <div className="border-t border-slate-200 p-2.5 bg-white">
          <div
            className="relative rounded-xl border border-slate-200 bg-white focus-within:border-blue-400 focus-within:ring-1 focus-within:ring-blue-100 transition-colors"
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
          >
            {mention.popup}
            <textarea
              ref={inputRef}
              rows={2}
              placeholder={inputPlaceholder}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              className="block w-full text-[12px] px-3 pt-2.5 pb-1 bg-transparent resize-none focus:outline-none max-h-40"
            />
            <div className="flex items-center gap-1 px-2 pb-2 pt-0.5 flex-wrap">
              <AttachmentBar
                value={attachments}
                onChange={setAttachments}
                onError={setErrorMsg}
                disabled={streaming}
              />
              <button
                type="button"
                onClick={toggleSendMode}
                className="flex items-center gap-1 px-1.5 h-7 rounded-md text-[10px] text-slate-500 hover:bg-slate-100"
                title="切换发送快捷键"
              >
                <Zap className="w-3 h-3" />
                {sendMode === "enter" ? "Enter 发送" : "⌘↵ 发送"}
              </button>
              <div className="flex-1" />
              {streaming ? (
                <span className="flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 text-slate-400" title="生成中">
                  <Square className="w-3.5 h-3.5" />
                </span>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!canSend}
                  className={clsx(
                    "flex items-center justify-center w-8 h-8 rounded-full transition-colors",
                    canSend
                      ? "bg-blue-500 text-white hover:bg-blue-600"
                      : "bg-slate-100 text-slate-400 cursor-not-allowed",
                  )}
                  title={sendMode === "enter" ? "发送（Enter）" : "发送（⌘/Ctrl+Enter）"}
                >
                  <Send className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  if (isDrawer) {
    return (
      <div className="fixed inset-0 z-40 flex justify-end">
        <div className="absolute inset-0 bg-black/20" onClick={onClose} />
        <div className="relative h-full">{inner}</div>
      </div>
    );
  }
  return inner;
}
