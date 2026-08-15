import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { X, Trash2, Send, Pencil, AlertTriangle, Sparkles, Square } from "lucide-react";
import clsx from "clsx";

import { openclawStreamChat } from "@/api/openclaw";
import {
  buildAnalysisPrompt,
  extractTextDelta,
  extractResponseId,
  type Candidate,
} from "@/lib/promptBuilder";

/**
 * 模式：
 * - "general" — 通用对话（不绑定股票，无 prompt 编辑首屏）
 * - { stock: Candidate } — 单股对话（预填结构化 prompt，可编辑）
 *
 * Variant：
 * - "drawer" — 固定右侧抽屉（带遮罩，需 open/onClose）
 * - "embedded" — 内嵌卡片（无遮罩，消息区 max-h 限制）
 */
type Mode =
  | { kind: "general" }
  | { kind: "stock"; stock: Candidate };

type Variant = "drawer" | "embedded";

interface Props {
  mode: Mode;
  variant?: Variant;
  /** drawer 模式必填：控制开关 */
  open?: boolean;
  /** drawer 模式必填：关闭回调 */
  onClose?: () => void;
  /** 通用模式可选：标题（默认「通用 AI 对话」） */
  title?: string;
  /** 通用模式可选：输入框 placeholder */
  placeholder?: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface PersistedState {
  messages: Message[];
  response_id: string | null;
}

const RATE_LIMIT_SECONDS = 60;
const GENERAL_SCOPE = "general";

function getScope(mode: Mode): string {
  return mode.kind === "general" ? GENERAL_SCOPE : mode.stock.code;
}

function storageKey(scope: string) {
  return `openclaw:chat:${scope}`;
}

function loadPersisted(scope: string): PersistedState {
  try {
    const raw = sessionStorage.getItem(storageKey(scope));
    if (!raw) return { messages: [], response_id: null };
    return JSON.parse(raw);
  } catch {
    return { messages: [], response_id: null };
  }
}

function savePersisted(scope: string, state: PersistedState) {
  try {
    sessionStorage.setItem(storageKey(scope), JSON.stringify(state));
  } catch {
    /* quota */
  }
}

function clearPersisted(scope: string) {
  try {
    sessionStorage.removeItem(storageKey(scope));
  } catch {
    /* ignore */
  }
}

export function AIChatDialog(props: Props) {
  const { mode, variant = "drawer", open, onClose, title, placeholder } = props;
  const scope = getScope(mode);
  const isGeneral = mode.kind === "general";
  const isEmbedded = variant === "embedded";

  // 单股模式才有 prompt 预填
  const initialPrompt = useMemo(() => {
    if (isGeneral) return "";
    return buildAnalysisPrompt(mode.stock.code, [mode.stock]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  // 拉一次持久化的对话历史（按 scope 隔离）
  const [persisted, setPersisted] = useState<PersistedState>(() => loadPersisted(scope));

  // 当 scope 切换时重新加载
  useEffect(() => {
    setPersisted(loadPersisted(scope));
    setInput("");
    setDraft("");
    setErrorMsg(null);
    setDisconnected(false);
    setIsEditingPrompt(false);
    setPromptDraft(initialPrompt);
  }, [scope, initialPrompt]);

  // 对话消息 + 流式状态
  const [draft, setDraft] = useState<string>("");
  const [input, setInput] = useState<string>("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [disconnected, setDisconnected] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [cooldownLeft, setCooldownLeft] = useState(0);
  const [isEditingPrompt, setIsEditingPrompt] = useState(false);
  const [promptDraft, setPromptDraft] = useState(initialPrompt);

  const abortRef = useRef<AbortController | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  // 自动滚到底
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [persisted.messages.length, draft]);

  // 冷却倒计时
  useEffect(() => {
    if (cooldownLeft <= 0) return;
    const t = setInterval(() => setCooldownLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [cooldownLeft]);

  // 关闭时取消进行中的请求（仅 drawer 模式）
  useEffect(() => {
    if (variant === "drawer" && open === false) {
      abortRef.current?.abort();
      abortRef.current = null;
      setIsStreaming(false);
      setDraft("");
    }
  }, [variant, open]);

  // drawer 模式：未打开不渲染
  if (variant === "drawer" && !open) return null;

  // embedded 模式：始终渲染
  // embedded 模式要主动聚焦输入框（首次挂载时）
  useEffect(() => {
    if (isEmbedded && persisted.messages.length > 0) {
      inputRef.current?.focus();
    }
  }, [isEmbedded, persisted.messages.length]);

  const messages = persisted.messages;
  const responseId = persisted.response_id;

  function handleSend() {
    // 单股首屏：必须从 promptDraft 取（textarea 里的文本）
    // 通用模式 / 单股已发过：直接用 input
    const text =
      messages.length === 0 && !isGeneral && isEditingPrompt
        ? promptDraft.trim()
        : input.trim();
    if (!text || isStreaming) return;

    setErrorMsg(null);
    setDisconnected(false);
    setDraft("");
    setInput("");

    const userMsg: Message = { role: "user", content: text };
    const next: PersistedState = {
      messages: [...messages, userMsg],
      response_id: responseId,
    };
    setPersisted(next);
    savePersisted(scope, next);

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setIsStreaming(true);
    setCooldownLeft(RATE_LIMIT_SECONDS);

    let accDraft = "";
    let lastResponseId: string | null = responseId;

    openclawStreamChat(
      {
        message: text,
        code: isGeneral ? undefined : mode.stock.code,
        previousResponseId: responseId ?? undefined,
        signal: ctrl.signal,
      },
      {
        onDelta: (event: any) => {
          if (event?.type === "error") {
            const code = event?.error?.code || "unknown";
            const msg = event?.error?.message || "未知错误";
            setErrorMsg(`OpenClaw 错误（${code}）：${msg}`);
            setDisconnected(true);
            setIsStreaming(false);
            return;
          }
          const text = extractTextDelta(event);
          if (text) {
            accDraft += text;
            setDraft(accDraft);
          }
          const rid = extractResponseId(event);
          if (rid) lastResponseId = rid;
        },
        onDone: () => {
          setIsStreaming(false);
          if (accDraft) {
            const final: PersistedState = {
              messages: [...next.messages, { role: "assistant", content: accDraft }],
              response_id: lastResponseId,
            };
            setPersisted(final);
            savePersisted(scope, final);
          }
          setDraft("");
        },
        onError: (err) => {
          if (err.name === "AbortError") return;
          setErrorMsg(err.message);
          setDisconnected(true);
          setIsStreaming(false);
        },
      },
    );
  }

  function handleClear() {
    clearPersisted(scope);
    setPersisted({ messages: [], response_id: null });
    setInput("");
    setDraft("");
    setErrorMsg(null);
    setDisconnected(false);
    setIsEditingPrompt(false);
    setPromptDraft(initialPrompt);
  }

  function handleRetry() {
    setDisconnected(false);
    setErrorMsg(null);
    handleSend();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSend();
    }
  }

  function handleAbort() {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  }

  // 是否显示 prompt 编辑首屏（仅单股模式首条消息前）
  const showPromptEditor = !isGeneral && messages.length === 0;

  // 是否可以发送
  const canSend =
    !isStreaming &&
    cooldownLeft === 0 &&
    (messages.length > 0 || isGeneral
      ? input.trim().length > 0
      : showPromptEditor
        ? isEditingPrompt && promptDraft.trim().length > 0
        : true);

  // 标题
  const headerTitle = isGeneral
    ? (title ?? "通用 AI 对话")
    : `智能析股 · ${mode.stock.name}`;
  const headerSub = isGeneral ? null : mode.stock.code;
  const inputPlaceholder = isGeneral
    ? (placeholder ?? "随便聊点什么，例如：今天白酒板块怎么看？")
    : (placeholder ?? "继续追问，例如：如果白酒板块整体下行呢？");

  // 消息列表 max-height：embedded 模式限制避免撑高整页
  const messagesClass = isEmbedded
    ? "overflow-auto p-3 space-y-2 bg-slate-50/30"
    : "flex-1 overflow-auto p-3 space-y-2 bg-slate-50/30";
  const messagesStyle = isEmbedded ? { maxHeight: 480 } : undefined;

  // 内层容器（始终渲染）
  const inner = (
    <div
      className={clsx(
        "bg-white flex flex-col border-slate-200",
        isEmbedded ? "rounded-md border" : "shadow-xl w-full sm:w-[480px] h-full border-l",
      )}
    >
      {/* 顶栏 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-200 bg-slate-50">
        <div className="flex items-center gap-1.5 text-[12px] text-slate-700 font-medium">
          <Sparkles className="w-3.5 h-3.5 text-blue-500" />
          <span>
            {headerTitle}
            {headerSub && (
              <span className="text-slate-400 ml-1 text-[11px] tabular">{headerSub}</span>
            )}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleClear}
            className="flex items-center gap-0.5 px-1.5 py-0.5 text-[11px] text-slate-500 hover:text-red-600 rounded"
            title="清空对话"
          >
            <Trash2 className="w-3 h-3" />
          </button>
          {variant === "drawer" && onClose && (
            <button
              onClick={onClose}
              className="flex items-center px-1.5 py-0.5 text-[11px] text-slate-500 hover:text-slate-800 rounded"
              title="关闭"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* 消息列表 */}
      <div ref={messagesRef} className={messagesClass} style={messagesStyle}>
        {showPromptEditor ? (
          // 单股首屏：prompt 预填（只读 / 编辑切换）
          <div className="rounded border border-blue-200 bg-blue-50/40 p-2.5">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] text-blue-700 font-medium">
                结构化提示词（可编辑后发送）
              </span>
              <button
                onClick={() => setIsEditingPrompt((v) => !v)}
                className="flex items-center gap-0.5 text-[11px] text-blue-600 hover:text-blue-800"
              >
                <Pencil className="w-3 h-3" />
                {isEditingPrompt ? "完成编辑" : "编辑"}
              </button>
            </div>
            {isEditingPrompt ? (
              <textarea
                className="w-full h-48 text-[11px] p-2 border border-slate-200 rounded resize-y font-mono leading-relaxed"
                value={promptDraft}
                onChange={(e) => setPromptDraft(e.target.value)}
              />
            ) : (
              <pre className="text-[11px] text-slate-700 whitespace-pre-wrap font-mono leading-relaxed max-h-96 overflow-auto">
                {promptDraft}
              </pre>
            )}
          </div>
        ) : messages.length === 0 ? (
          // 通用模式空状态
          <div className="text-center text-slate-400 py-6 text-[11px]">
            开始对话吧 — 提问后按 Ctrl/Cmd + Enter 发送
          </div>
        ) : (
          messages.map((m, i) => (
            <div
              key={i}
              className={clsx("flex", m.role === "user" ? "justify-end" : "justify-start")}
            >
              <div
                className={clsx(
                  "max-w-[90%] rounded-lg px-3 py-2 text-[12px] leading-relaxed",
                  m.role === "user"
                    ? "bg-blue-500 text-white whitespace-pre-wrap"
                    : "bg-white border border-slate-200 text-slate-800 prose prose-sm prose-slate max-w-none",
                )}
              >
                {m.role === "assistant" ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
                    {m.content}
                  </ReactMarkdown>
                ) : (
                  m.content
                )}
              </div>
            </div>
          ))
        )}

        {/* 流式中草稿 */}
        {isStreaming && draft && (
          <div className="flex justify-start">
            <div className="max-w-[90%] rounded-lg px-3 py-2 text-[12px] leading-relaxed bg-white border border-slate-200 text-slate-800 prose prose-sm prose-slate max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
                {draft}
              </ReactMarkdown>
              <span className="inline-block w-1.5 h-3 bg-blue-400 animate-pulse ml-0.5" />
            </div>
          </div>
        )}

        {/* 中断 / 错误横幅 */}
        {(disconnected || errorMsg) && (
          <div className="rounded border border-yellow-300 bg-yellow-50 px-2.5 py-1.5 flex items-start gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-yellow-600 shrink-0 mt-0.5" />
            <div className="text-[11px] text-yellow-800 flex-1">
              {errorMsg || "连接已中断"}
              <button
                onClick={handleRetry}
                className="ml-2 text-yellow-700 hover:text-yellow-900 underline"
              >
                重试
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 输入区 */}
      <div className="border-t border-slate-200 p-2.5 bg-white">
        {showPromptEditor ? (
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-400">首条消息 = 提示词</span>
            <button
              onClick={handleSend}
              disabled={!canSend}
              className={clsx(
                "flex items-center gap-1 rounded px-3 py-1 text-[12px]",
                canSend
                  ? "bg-blue-500 text-white hover:bg-blue-600"
                  : "bg-slate-100 text-slate-400 cursor-not-allowed",
              )}
            >
              <Send className="w-3 h-3" />
              发送
            </button>
          </div>
        ) : (
          <div className="flex items-end gap-1.5">
            <textarea
              ref={inputRef}
              rows={2}
              placeholder={inputPlaceholder}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
              className="flex-1 text-[12px] p-2 border border-slate-200 rounded resize-none focus:outline-none focus:border-blue-400 disabled:bg-slate-50 disabled:text-slate-400"
            />
            <div className="flex flex-col gap-1">
              {isStreaming ? (
                <button
                  onClick={handleAbort}
                  className="flex items-center justify-center rounded px-2 py-1 text-[11px] bg-red-50 text-red-600 border border-red-200 hover:bg-red-100"
                  title="停止生成"
                >
                  <Square className="w-3 h-3" />
                </button>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!canSend}
                  className={clsx(
                    "flex items-center justify-center rounded px-2 py-1 text-[11px]",
                    canSend
                      ? "bg-blue-500 text-white hover:bg-blue-600"
                      : "bg-slate-100 text-slate-400 cursor-not-allowed",
                  )}
                  title={cooldownLeft > 0 ? `${cooldownLeft}s 后可重发` : "发送（Ctrl/Cmd+Enter）"}
                >
                  <Send className="w-3 h-3" />
                </button>
              )}
              {cooldownLeft > 0 && (
                <span className="text-[10px] text-slate-400 text-center tabular">
                  {cooldownLeft}s
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );

  // drawer 模式：包一层 fixed + 遮罩
  if (variant === "drawer") {
    return (
      <div className="fixed inset-0 z-40 flex justify-end">
        <div className="absolute inset-0 bg-black/20" onClick={onClose} />
        {inner}
      </div>
    );
  }

  // embedded 模式：直接返回内容
  return inner;
}