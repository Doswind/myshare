import { Sparkles, ChevronDown, ChevronRight } from "lucide-react";
import clsx from "clsx";
import type { BoardItem } from "@/api/screener";

interface Props {
  items: BoardItem[];
  direction: "in" | "out";
  expandedCode: string | null;
  onToggleExpand: (code: string) => void;
  onAnalyze: (row: BoardItem) => void;
}

function posLabel(pct: number): { label: string; color: string } {
  if (pct < 25) return { label: `${pct.toFixed(0)}% 低位`, color: "text-blue-600" };
  if (pct < 50) return { label: `${pct.toFixed(0)}% 中位`, color: "text-slate-500" };
  if (pct < 75) return { label: `${pct.toFixed(0)}% 偏高`, color: "text-slate-500" };
  return { label: `${pct.toFixed(0)}% 高位`, color: "text-red-600" };
}

function mvText(mv: number | null): string {
  if (mv === null || mv === undefined) return "新进";
  return `${mv >= 0 ? "+" : ""}${mv.toFixed(0)}%`;
}

export function CandidateTable({ items, direction, expandedCode, onToggleExpand, onAnalyze }: Props) {
  if (!items.length) {
    return <div className="text-center text-slate-400 py-6 text-[12px]">暂无{direction === "in" ? "进场" : "退场"}标的</div>;
  }
  const mvColor = direction === "in" ? "text-up" : "text-down";

  return (
    <div className="divide-y divide-slate-100">
      {items.map((c) => {
        const expanded = expandedCode === c.code;
        const pos = posLabel(c.pct_rank_1y);
        return (
          <div key={c.code}>
            <div
              className={clsx(
                "px-3 py-2 hover:bg-slate-50 cursor-pointer transition-colors",
                expanded && "bg-slate-50",
              )}
              onClick={() => onToggleExpand(c.code)}
            >
              <div className="flex items-center gap-2">
                {expanded ? (
                  <ChevronDown className="w-3 h-3 text-slate-400 shrink-0" />
                ) : (
                  <ChevronRight className="w-3 h-3 text-slate-400 shrink-0" />
                )}
                <span className="text-slate-800 font-medium text-[12px]">{c.name}</span>
                <span className="text-slate-400 tabular text-[11px]">{c.code}</span>
                <span className="text-slate-400 text-[11px]">{c.industry}</span>
                <span className={clsx("text-[11px] tabular ml-auto", mvColor)}>
                  {direction === "in" ? "加仓" : "减仓"} {mvText(c.mv_change_pct_qoq)}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onAnalyze(c);
                  }}
                  className="inline-flex items-center gap-0.5 rounded border border-blue-300 text-blue-600 hover:bg-blue-50 px-1.5 py-0.5 text-[11px] transition-colors shrink-0"
                >
                  <Sparkles className="w-3 h-3" />
                  析股
                </button>
              </div>
              <div className="mt-1 pl-5 text-[11px] text-slate-600 leading-relaxed">
                <span className={pos.color}>近1年{pos.label}</span>
                <span className="mx-1 text-slate-300">·</span>
                <span>{c.reason}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
