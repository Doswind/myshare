import { Sparkles, ChevronDown, ChevronRight } from "lucide-react";
import clsx from "clsx";

export interface CandidateRow {
  code: string;
  name: string;
  industry: string;
  total_score: number;
  score_position: number;
  score_trend: number;
  score_capital: number;
  fund_count: number;
  pct_rank_1y: number;
}

interface Props {
  candidates: CandidateRow[];
  expandedCode: string | null;
  onToggleExpand: (code: string) => void;
  onAnalyze: (row: CandidateRow) => void;
}

function scoreColor(score: number): string {
  if (score >= 85) return "text-blue-700 font-semibold";
  if (score >= 70) return "text-blue-600";
  if (score < 40) return "text-slate-400";
  return "text-slate-700";
}

function rankHint(pct: number): { label: string; color: string } {
  if (pct < 25) return { label: "近 1 年低位", color: "text-blue-600" };
  if (pct < 50) return { label: "近 1 年中位", color: "text-slate-500" };
  if (pct < 75) return { label: "近 1 年偏高", color: "text-slate-500" };
  return { label: "近 1 年高位", color: "text-red-600" };
}

export function CandidateTable({ candidates, expandedCode, onToggleExpand, onAnalyze }: Props) {
  if (!candidates.length) {
    return (
      <div className="text-center text-slate-400 py-6 text-[12px]">暂无候选</div>
    );
  }

  return (
    <table className="w-full text-[12px]">
      <thead className="bg-slate-50 text-slate-500 text-[11px]">
        <tr>
          <th className="text-left px-3 py-1.5 font-normal w-6"></th>
          <th className="text-left px-3 py-1.5 font-normal">代码</th>
          <th className="text-left px-3 py-1.5 font-normal">名称</th>
          <th className="text-left px-3 py-1.5 font-normal">行业</th>
          <th className="text-right px-3 py-1.5 font-normal">总分</th>
          <th className="text-right px-3 py-1.5 font-normal">位置</th>
          <th className="text-right px-3 py-1.5 font-normal">趋势</th>
          <th className="text-right px-3 py-1.5 font-normal">主力</th>
          <th className="text-right px-3 py-1.5 font-normal">基金数</th>
          <th className="text-left px-3 py-1.5 font-normal">位置提示</th>
          <th className="text-right px-3 py-1.5 font-normal">操作</th>
        </tr>
      </thead>
      <tbody>
        {candidates.map((c) => {
          const expanded = expandedCode === c.code;
          const hint = rankHint(c.pct_rank_1y);
          return (
            <tr
              key={c.code}
              className={clsx(
                "border-t border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors",
                expanded && "bg-slate-50",
              )}
              onClick={() => onToggleExpand(c.code)}
            >
              <td className="px-2 py-1.5 text-slate-400">
                {expanded ? (
                  <ChevronDown className="w-3 h-3" />
                ) : (
                  <ChevronRight className="w-3 h-3" />
                )}
              </td>
              <td className="px-3 py-1.5 text-slate-500 tabular">{c.code}</td>
              <td className="px-3 py-1.5 text-slate-800 font-medium">{c.name}</td>
              <td className="px-3 py-1.5 text-slate-500">{c.industry}</td>
              <td className={clsx("px-3 py-1.5 text-right tabular", scoreColor(c.total_score))}>
                {c.total_score}
              </td>
              <td className={clsx("px-3 py-1.5 text-right tabular", scoreColor(c.score_position))}>
                {c.score_position}
              </td>
              <td className={clsx("px-3 py-1.5 text-right tabular", scoreColor(c.score_trend))}>
                {c.score_trend}
              </td>
              <td className={clsx("px-3 py-1.5 text-right tabular", scoreColor(c.score_capital))}>
                {c.score_capital}
              </td>
              <td className="px-3 py-1.5 text-right tabular text-slate-700">{c.fund_count}</td>
              <td className={clsx("px-3 py-1.5 text-[11px]", hint.color)}>{hint.label}</td>
              <td className="px-3 py-1.5 text-right">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onAnalyze(c);
                  }}
                  className="inline-flex items-center gap-0.5 rounded border border-blue-300 text-blue-600 hover:bg-blue-50 px-2 py-0.5 text-[11px] transition-colors"
                >
                  <Sparkles className="w-3 h-3" />
                  智能析股
                </button>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}