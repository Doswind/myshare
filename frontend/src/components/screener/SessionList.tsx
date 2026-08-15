import { useState } from "react";
import { Plus, MessageSquare, Trash2, Check, X } from "lucide-react";
import clsx from "clsx";
import type { ChatSessionMeta } from "@/api/openclawSessions";

interface Props {
  sessions: ChatSessionMeta[];
  activeId: string | null;
  loading?: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const mm = `${d.getMonth() + 1}`.padStart(2, "0");
  const dd = `${d.getDate()}`.padStart(2, "0");
  const hh = `${d.getHours()}`.padStart(2, "0");
  const mi = `${d.getMinutes()}`.padStart(2, "0");
  return `${mm}-${dd} ${hh}:${mi}`;
}

/** 左侧历史会话列表：新建 / 选择 / 删除（二次确认） */
export function SessionList({ sessions, activeId, loading, onSelect, onNew, onDelete }: Props) {
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  return (
    <div className="flex flex-col w-[200px] shrink-0 border-r border-slate-200 bg-slate-50/60">
      <button
        onClick={onNew}
        className="flex items-center justify-center gap-1 m-2 px-2 py-1.5 rounded-md bg-blue-500 text-white text-[12px] hover:bg-blue-600"
        title="开启一个新对话"
      >
        <Plus className="w-3.5 h-3.5" />
        新建会话
      </button>
      <div className="flex-1 overflow-auto px-1.5 pb-2 space-y-0.5">
        {loading && (
          <div className="text-center text-slate-400 py-4 text-[11px]">加载中…</div>
        )}
        {!loading && sessions.length === 0 && (
          <div className="text-center text-slate-400 py-4 text-[11px]">暂无历史会话</div>
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={clsx(
              "group flex items-center gap-1.5 px-2 py-1.5 rounded-md cursor-pointer text-[12px]",
              s.id === activeId ? "bg-blue-100 text-blue-800" : "text-slate-600 hover:bg-slate-100",
            )}
          >
            <MessageSquare className="w-3.5 h-3.5 shrink-0 text-slate-400" />
            <div className="min-w-0 flex-1">
              <div className="truncate">{s.title || "新会话"}</div>
              <div className="text-[10px] text-slate-400">{fmtTime(s.updated_at)}</div>
            </div>
            {confirmingId === s.id ? (
              <span className="flex items-center gap-0.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={() => {
                    onDelete(s.id);
                    setConfirmingId(null);
                  }}
                  className="text-red-500 hover:text-red-600"
                  title="确认删除"
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setConfirmingId(null)}
                  className="text-slate-400 hover:text-slate-600"
                  title="取消"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </span>
            ) : (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setConfirmingId(s.id);
                }}
                className="text-slate-300 hover:text-red-500 shrink-0 opacity-0 group-hover:opacity-100"
                title="删除会话"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
