import { useEffect, useRef, useState } from "react";
import { Search, Loader2 } from "lucide-react";
import { searchStocks, type StockSearchHit } from "@/api/watchlist";
import clsx from "clsx";

interface Props {
  value: string;
  onChange: (v: string) => void;
  /** 选中某个联想结果时触发（回车选中或点击） */
  onSelect: (hit: StockSearchHit) => void;
  placeholder?: string;
  className?: string;
}

/**
 * 带联想下拉的股票搜索框。
 *
 * 走后端 /stocks/search，天然支持 代码 / 中文名 / 拼音全拼 / 拼音首字母。
 * 输入 200ms 防抖；下拉支持 ↑/↓ 选择、Enter 确认、Esc 关闭、点击外部关闭。
 */
export function StockSearchBox({ value, onChange, onSelect, placeholder, className }: Props) {
  const [hits, setHits] = useState<StockSearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [hi, setHi] = useState(-1);
  const boxRef = useRef<HTMLDivElement>(null);
  const debRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 输入防抖 → 联想
  useEffect(() => {
    if (debRef.current) clearTimeout(debRef.current);
    const q = value.trim();
    if (!q) {
      setHits([]);
      setOpen(false);
      return;
    }
    debRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await searchStocks(q, 10);
        setHits(r);
        setOpen(r.length > 0);
        setHi(-1);
      } catch {
        setHits([]);
      } finally {
        setLoading(false);
      }
    }, 200);
    return () => {
      if (debRef.current) clearTimeout(debRef.current);
    };
  }, [value]);

  // 点击外部关闭
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const pick = (h: StockSearchHit) => {
    setOpen(false);
    setHits([]);
    onSelect(h);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || hits.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHi((v) => Math.min(v + 1, hits.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHi((v) => Math.max(v - 1, -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (hi >= 0 && hits[hi]) pick(hits[hi]);
      else if (hits.length > 0) pick(hits[0]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={boxRef} className={clsx("relative", className)}>
      <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onFocus={() => hits.length > 0 && setOpen(true)}
        placeholder={placeholder}
        className="w-full pl-7 pr-7 py-0.5 text-[12px] border border-slate-300 rounded bg-white outline-none focus:border-blue-400"
      />
      {loading && (
        <Loader2 className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 animate-spin" />
      )}

      {open && hits.length > 0 && (
        <div className="absolute z-30 left-0 right-0 mt-1 rounded border border-slate-200 bg-white shadow-lg max-h-72 overflow-auto">
          {hits.map((h, i) => (
            <div
              key={h.code}
              onClick={() => pick(h)}
              className={clsx(
                "px-2.5 py-1.5 text-[12px] flex items-center justify-between border-b border-slate-50 last:border-0 cursor-pointer",
                i === hi ? "bg-blue-50" : "hover:bg-slate-50",
              )}
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="tabular text-slate-500 w-14 shrink-0">{h.code}</span>
                <span className="text-slate-800 truncate">{h.name}</span>
                {h.industry_name && (
                  <span className="text-[10px] text-slate-400 shrink-0">· {h.industry_name}</span>
                )}
              </div>
              {h.pinyin_abbr && (
                <span className="text-[10px] text-slate-400 tabular shrink-0 ml-2 uppercase">
                  {h.pinyin_abbr}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {open && !loading && hits.length === 0 && value.trim() && (
        <div className="absolute z-30 left-0 right-0 mt-1 rounded border border-slate-200 bg-white shadow px-3 py-2 text-[12px] text-slate-400">
          没有匹配的股票
        </div>
      )}
    </div>
  );
}
