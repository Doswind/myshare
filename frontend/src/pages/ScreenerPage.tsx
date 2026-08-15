import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchCandidates, fetchFactors, fetchIndustries } from "@/api/screener";
import { fetchOpenclawHealth } from "@/api/openclaw";
import { CandidateTable } from "@/components/screener/CandidateTable";
import { FactorPanel } from "@/components/screener/FactorPanel";
import { AIChatDialog } from "@/components/screener/AIChatDialog";
import type { Candidate } from "@/lib/promptBuilder";
import { AlertTriangle, RefreshCw, Sparkles } from "lucide-react";

export default function ScreenerPage() {
  const [industry, setIndustry] = useState<string>("");
  const [minScore, setMinScore] = useState<string>("");
  const [expandedCode, setExpandedCode] = useState<string | null>(null);
  const [chatStock, setChatStock] = useState<Candidate | null>(null);

  const candidatesQ = useQuery({
    queryKey: ["screener-candidates"],
    queryFn: () => fetchCandidates(),
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

  const allCandidates = candidatesQ.data?.items ?? [];

  const filtered = useMemo(() => {
    let xs = allCandidates;
    if (industry) xs = xs.filter((c) => c.industry === industry);
    const ms = Number(minScore);
    if (!Number.isNaN(ms) && minScore !== "") xs = xs.filter((c) => c.total_score >= ms);
    return xs;
  }, [allCandidates, industry, minScore]);

  const healthUnreachable =
    healthQ.data && healthQ.data.reachable === false;

  function handleToggleExpand(code: string) {
    setExpandedCode((cur) => (cur === code ? null : code));
  }

  async function handleAnalyze(row: { code: string; name: string; industry: string }) {
    const c = allCandidates.find((x) => x.code === row.code);
    if (!c) return;
    // 拉真实因子数据（列表接口只返回精简字段，prompt 需要完整数据）
    let factors;
    try {
      factors = await fetchFactors(row.code);
    } catch {
      // 失败时仍打开抽屉，promptBuilder 会用占位 "—"
    }
    setChatStock({
      code: c.code,
      name: c.name,
      industry: c.industry,
      total_score: c.total_score,
      score_position: c.score_position,
      score_trend: c.score_trend,
      score_capital: c.score_capital,
      factors: (factors?.factors ?? {}) as any,
      capital: (factors?.capital ?? { fund_count: c.fund_count }) as any,
      valuation: (factors?.valuation ?? {}) as any,
      trend: (factors?.trend ?? {}) as any,
      latest_price: c.latest_price ?? factors?.latest_price,
    });
  }

  return (
    <div className="space-y-3">
      {/* OpenClaw 健康横幅 */}
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
        {/* 顶部说明 + 筛选 */}
        <div className="px-3 py-2.5 border-b border-slate-200 flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-blue-500" />
            <h2 className="text-[13px] font-semibold text-slate-800">选股分析（Demo）</h2>
            <span className="text-[10px] text-slate-400">
              {filtered.length} / {allCandidates.length} 只候选 · 全部为 mock 数据
            </span>
          </div>
          <div className="flex items-center gap-2 text-[11px]">
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
            <div className="flex items-center gap-1">
              <span className="text-slate-400">≥</span>
              <input
                type="number"
                min={0}
                max={100}
                value={minScore}
                onChange={(e) => setMinScore(e.target.value)}
                placeholder="分数"
                className="w-16 border border-slate-200 rounded px-1.5 py-0.5 text-[11px] tabular bg-white"
              />
            </div>
          </div>
        </div>

        {/* 候选表 */}
        {candidatesQ.isLoading ? (
          <div className="text-center text-slate-400 py-6 text-[12px]">加载候选中…</div>
        ) : candidatesQ.error ? (
          <div className="text-center text-red-500 py-6 text-[12px]">
            加载失败：{(candidatesQ.error as Error)?.message}
          </div>
        ) : (
          <>
            <CandidateTable
              candidates={filtered}
              expandedCode={expandedCode}
              onToggleExpand={handleToggleExpand}
              onAnalyze={handleAnalyze}
            />
            {expandedCode && (
              <FactorPanel code={expandedCode} />
            )}
          </>
        )}
      </div>

      {/* AI 对话抽屉（单股模式） */}
      {chatStock && (
        <AIChatDialog
          mode={{ kind: "stock", stock: chatStock }}
          variant="drawer"
          open={!!chatStock}
          onClose={() => setChatStock(null)}
        />
      )}

      {/* 通用 AI 对话卡片（页面内嵌，始终可见） */}
      <div className="rounded-md border border-slate-200 bg-white">
        <div className="px-3 py-2.5 border-b border-slate-200 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-blue-500" />
            <h2 className="text-[13px] font-semibold text-slate-800">通用 AI 对话</h2>
            <span className="text-[10px] text-slate-400">
              OpenClaw 对话 · 不绑定股票 · 按 Ctrl/Cmd + Enter 发送
            </span>
          </div>
        </div>
        <div className="p-3">
          <AIChatDialog mode={{ kind: "general" }} variant="embedded" />
        </div>
      </div>
    </div>
  );
}