import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Search, Plus, Loader2, Star } from "lucide-react";
import {
  searchStocks,
  addWatchlist,
  removeWatchlist,
  type StockSearchHit,
} from "@/api/watchlist";
import clsx from "clsx";

interface Props {
  /** 已添加的代码列表（用于禁用） */
  existingCodes?: string[];
  /** 添加成功后的回调 */
  onAdded?: (item: { code: string; name: string }) => void;
  className?: string;
}

export function WatchlistAddBox({ existingCodes = [], onAdded, className }: Props) {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<StockSearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);
  const [hi, setHi] = useState(-1);
  const boxRef = useRef<HTMLDivElement>(null);
  const debRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 输入防抖 → 调用 search
  useEffect(() => {
    if (debRef.current) clearTimeout(debRef.current);
    if (!q.trim()) {
      setHits([]);
      setOpen(false);
      return;
    }
    debRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await searchStocks(q.trim(), 10);
        setHits(r);
        setOpen(r.length > 0);
        setHi(-1);
      } catch (e) {
        setHits([]);
      } finally {
        setLoading(false);
      }
    }, 200);
    return () => {
      if (debRef.current) clearTimeout(debRef.current);
    };
  }, [q]);

  // 点击外部关闭
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  // 顶部 toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(t);
  }, [toast]);

  const doAdd = async (h: StockSearchHit) => {
    if (busy) return;
    setBusy(true);
    try {
      const it = await addWatchlist(h.code);
      showToast("ok", `已添加：${it.name || h.code}`);
      setQ("");
      setHits([]);
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      onAdded?.({ code: it.code, name: it.name });
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || "添加失败";
      showToast("err", msg);
    } finally {
      setBusy(false);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHi((v) => Math.min(v + 1, hits.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHi((v) => Math.max(v - 1, -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (hi >= 0 && hits[hi]) {
        doAdd(hits[hi]);
      } else if (hits.length > 0) {
        doAdd(hits[0]);
      } else if (q.trim()) {
        // 没有联想结果时，直接尝试按当前输入添加
        doAdd({ code: q.trim(), name: q.trim() } as StockSearchHit);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  const showToast = (type: "ok" | "err", msg: string) => setToast({ type, msg });

  const isAdded = (code: string) => existingCodes.includes(code);

  return (
    <div ref={boxRef} className={clsx("relative", className)}>
      <div className="flex items-center gap-1.5 text-[12px]">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onKeyDown}
            onFocus={() => hits.length > 0 && setOpen(true)}
            placeholder="输入代码 / 名称 / 拼音首字母 搜索自选"
            className="w-full pl-7 pr-7 py-1 border border-slate-300 rounded bg-white outline-none focus:border-blue-400"
          />
          {loading && (
            <Loader2 className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 animate-spin" />
          )}
        </div>
        <button
          onClick={() => {
            if (hi >= 0 && hits[hi]) doAdd(hits[hi]);
            else if (hits.length > 0) doAdd(hits[0]);
            else if (q.trim())
              doAdd({ code: q.trim(), name: q.trim() } as StockSearchHit);
          }}
          disabled={busy || !q.trim()}
          className="px-2.5 py-1 rounded bg-slate-700 text-white hover:bg-slate-800 disabled:opacity-50 flex items-center gap-1"
        >
          {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
          添加
        </button>
      </div>

      {/* 联想下拉 */}
      {open && hits.length > 0 && (
        <div className="absolute z-30 left-0 right-12 mt-1 rounded border border-slate-200 bg-white shadow-lg max-h-72 overflow-auto">
          {hits.map((h, i) => {
            const added = isAdded(h.code);
            return (
              <div
                key={h.code}
                onClick={() => !added && doAdd(h)}
                className={clsx(
                  "px-2.5 py-1.5 text-[12px] flex items-center justify-between border-b border-slate-50 last:border-0",
                  added ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
                  i === hi ? "bg-blue-50" : "hover:bg-slate-50"
                )}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="tabular text-slate-500 w-14 shrink-0">{h.code}</span>
                  <span className="text-slate-800 truncate">{h.name}</span>
                  {h.industry_name && (
                    <span className="text-[10px] text-slate-400 shrink-0">· {h.industry_name}</span>
                  )}
                </div>
                <div className="flex items-center gap-1.5 shrink-0 ml-2">
                  {h.pinyin_abbr && (
                    <span className="text-[10px] text-slate-400 tabular">{h.pinyin_abbr}</span>
                  )}
                  {added ? (
                    <span className="text-[10px] text-emerald-600 flex items-center gap-0.5">
                      <Star className="w-2.5 h-2.5 fill-current" />
                      已添加
                    </span>
                  ) : (
                    <Plus className="w-3 h-3 text-slate-400" />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {open && !loading && hits.length === 0 && q.trim() && (
        <div className="absolute z-30 left-0 right-12 mt-1 rounded border border-slate-200 bg-white shadow px-3 py-2 text-[12px] text-slate-400">
          没有匹配的股票
        </div>
      )}

      {toast && (
        <div
          className={clsx(
            "absolute z-40 right-0 top-9 px-2.5 py-1 rounded shadow text-[11px] text-white",
            toast.type === "ok" ? "bg-emerald-600" : "bg-red-600"
          )}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}

/** 列表行内的删除按钮（带确认） */
export function WatchlistRemoveButton({ code, name }: { code: string; name: string }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const onClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (busy) return;
    if (!confirm(`确定从自选移除 ${name || code}？`)) return;
    setBusy(true);
    try {
      await removeWatchlist(code);
      qc.invalidateQueries({ queryKey: ["watchlist"] });
    } finally {
      setBusy(false);
    }
  };
  return (
    <button
      onClick={onClick}
      className="text-slate-300 hover:text-red-500 transition-colors text-[11px]"
      title="移除自选"
    >
      {busy ? "..." : "✕"}
    </button>
  );
}
