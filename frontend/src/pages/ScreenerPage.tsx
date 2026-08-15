import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchBoards, fetchFactors, fetchIndustries, type BoardItem } from "@/api/screener";
import { fetchOpenclawHealth } from "@/api/openclaw";
import { CandidateTable } from "@/components/screener/CandidateTable";
import { FactorPanel } from "@/components/screener/FactorPanel";
import { GeneralChat } from "@/components/screener/GeneralChat";
import { buildAnalysisPrompt, type Candidate } from "@/lib/promptBuilder";
import { AlertTriangle, RefreshCw, Sparkles, TrendingUp, TrendingDown } from "lucide-react";

export default function ScreenerPage() {
  const [industry, setIndustry] = useState<string>("");
  const [expandedCode, setExpandedCode] = useState<string | null>(null);
  const [chatStock, setChatStock] = useState<Candidate | null>(null);

  const boardsQ = useQuery({
    queryKey: ["screener-boards"],
    queryFn: () => fetchBoards(),
  });
  const industriesQ = useQuery({
    queryKey: ["screener-industries"],
    queryFn: () => fetchIndustries(),
  });
  const healthQ = useQuery({
    queryKey: ["openclaw-health"],
    queryFn: () => fetchOpenclawHealth(),
    refetchInterval: 30_000,
  });

  const inList = boardsQ.data?.in ?? [];
  const outList = boardsQ.data?.out ?? [];

  const filterByIndustry = (xs: BoardItem[]) =>
    industry ? xs.filter((c) => c.industry === industry) : xs;
  const inFiltered = useMemo(() => filterByIndustry(inList), [inList, industry]);
  const outFiltered = useMemo(() => filterByIndustry(outList), [outList, industry]);

  const healthUnreachable = healthQ.data && healthQ.data.reachable === false;

  function handleToggleExpand(code: string) {
    setExpandedCode((cur) => (cur === code ? null : code));
  }

  async function handleAnalyze(row: BoardItem) {
    let factors;
    try {
      factors = await fetchFactors(row.code);
    } catch {
      // 失败时仍打开抽屉，promptBuilder 会用占位 "—"
    }
    setChatStock({
      code: row.code,
      name: row.name,
      industry: row.industry,
      factors: (factors?.factors ?? {}) as any,
      capital: (factors?.capital ?? { fund_count: row.fund_count }) as any,
      valuation: factors?.valuation,
      trend: (factors?.trend ?? {}) as any,
      latest_price: row.latest_price ?? factors?.latest_price,
      direction: row.direction,
      reason: row.reason,
    });
  }

  return (
    <div className="space-y-3">
      {healthUnreachable && (
        <div className="rounded border border-yellow-300 bg-yellow-50 px-3 py-2 flex items-start gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-yellow-600 shrink-0 mt-0.5" />
          <div className="flex-1 text-[11px] text-yellow-800">
            <div className="font-medium">OpenClaw 不可达</div>
            <div className="mt-0.5">
              请确认 SSH 隧道已建立：
              <code className="bg-yellow-100 px-1 mx-1 rounded">
                ssh -N -L 18789:127.0.0.1:18789 user@网关机器
              </code>
              ，或 Gateway 进程已启动。{!healthQ.data?.has_token && "另外检查 .env 中 OPENCLAW_TOKEN 是否设置。"}
            </div>
          </div>
          <button
            onClick={() => healthQ.refetch()}
            className="flex items-center gap-0.5 text-[11px] text-yellow-700 hover:text-yellow-900 px-1.5 py-0.5 rounded"
          >
            <RefreshCw className="w-3 h-3" />
            重试
          </button>
        </div>
      )}

      <div className="rounded-md border border-slate-200 bg-white">
        <div className="px-3 py-2.5 border-b border-slate-200 flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-blue-500" />
            <h2 className="text-[13px] font-semibold text-slate-800">选股分析 · 主力动向</h2>
            <span className="text-[10px] text-slate-400">
              基于真实持仓与 K 线 · 报告期 {boardsQ.data?.report_dates?.join(" vs ") || "—"}
            </span>
          </div>
          <select
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            className="border border-slate-200 rounded px-1.5 py-0.5 text-[11px] bg-white"
          >
            <option value="">全部行业</option>
            {(industriesQ.data?.items ?? []).map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </div>

        {boardsQ.isLoading ? (
          <div className="text-center text-slate-400 py-6 text-[12px]">加载榜单中…</div>
        ) : boardsQ.error ? (
          <div className="text-center text-red-500 py-6 text-[12px]">
            加载失败：{(boardsQ.error as Error)?.message}
          </div>
        ) : boardsQ.data?.note ? (
          <div className="text-center text-slate-500 py-6 text-[12px] px-4">{boardsQ.data.note}</div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-200">
              <div>
                <div className="px-3 py-1.5 bg-red-50/60 border-b border-slate-100 flex items-center gap-1.5 text-[12px] font-medium text-up">
                  <TrendingUp className="w-3.5 h-3.5" />
                  主力进场榜（加仓 / 新进）· {inFiltered.length}
                </div>
                <CandidateTable
                  items={inFiltered}
                  direction="in"
                  expandedCode={expandedCode}
                  onToggleExpand={handleToggleExpand}
                  onAnalyze={handleAnalyze}
                />
              </div>
              <div>
                <div className="px-3 py-1.5 bg-green-50/60 border-b border-slate-100 flex items-center gap-1.5 text-[12px] font-medium text-down">
                  <TrendingDown className="w-3.5 h-3.5" />
                  主力退场榜（减仓 / 退出）· {outFiltered.length}
                </div>
                <CandidateTable
                  items={outFiltered}
                  direction="out"
                  expandedCode={expandedCode}
                  onToggleExpand={handleToggleExpand}
                  onAnalyze={handleAnalyze}
                />
              </div>
            </div>
            {expandedCode && <FactorPanel code={expandedCode} />}
          </>
        )}
      </div>

      {chatStock && (
        <GeneralChat
          variant="drawer"
          open={!!chatStock}
          onClose={() => setChatStock(null)}
          code={chatStock.code}
          title={`智能析股 · ${chatStock.name}`}
          initialInput={buildAnalysisPrompt(chatStock.code, [chatStock])}
          placeholder="可编辑上方预填的分析提示词后发送，或继续追问…"
        />
      )}

      <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
        <GeneralChat />
      </div>
    </div>
  );
}
