import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchFilterDefaults, updateFilterDefaults, resetFilterDefaults } from "@/api/funds";
import {
  fetchJobs,
  fetchScheduledJobs,
  triggerFundRefresh,
  triggerQuoteRefresh,
  triggerSectorRefresh,
} from "@/api/stocks";
import {
  fetchCrawlConfigs,
  bulkUpdateCrawlConfigs,
  resetCrawlConfigs,
} from "@/api/crawlConfig";
import type { CrawlConfig } from "@/types/api";
import { RefreshCw, CheckCircle2, AlertCircle, Loader2, Save, RotateCcw, Lock } from "lucide-react";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data: defaults } = useQuery({ queryKey: ["filter-defaults"], queryFn: fetchFilterDefaults });
  const { data: scheduled = [] } = useQuery({
    queryKey: ["scheduled-jobs"],
    queryFn: fetchScheduledJobs,
    refetchInterval: 30_000,
  });
  const { data: jobs = [] } = useQuery({
    queryKey: ["job-logs"],
    queryFn: fetchJobs,
    refetchInterval: 10_000,
  });
  const { data: crawlConfigs = [] } = useQuery({
    queryKey: ["crawl-configs"],
    queryFn: fetchCrawlConfigs,
    refetchInterval: 15_000,
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);
  const [draftConfigs, setDraftConfigs] = useState<Record<string, CrawlConfig>>({});
  const [saving, setSaving] = useState(false);

  const showToast = (type: "ok" | "err", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  };

  const run = async (key: string, fn: () => Promise<any>, label: string) => {
    setBusy(key);
    try {
      const r = await fn();
      showToast("ok", `${label}已启动：${r.stock_count ? `涉及 ${r.stock_count} 只股票` : r.message || ""}`);
      qc.invalidateQueries({ queryKey: ["job-logs"] });
    } catch (e: any) {
      showToast("err", `${label}失败：${formatErr(e)}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-3 max-w-4xl">
      {/* 抓取触发 */}
      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="text-[13px] font-semibold text-slate-800 mb-2">手动抓取</div>
        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={() => run("funds", triggerFundRefresh, "基金抓取")}
            disabled={busy !== null}
            className="flex items-center justify-center gap-1.5 px-3 py-2 rounded border border-slate-300 bg-white hover:bg-slate-50 text-[12px] text-slate-700 disabled:opacity-50"
          >
            {busy === "funds" ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            抓取基金+持仓（约 5–10 分钟）
          </button>
          <button
            onClick={() => run("sectors", triggerSectorRefresh, "行业抓取")}
            disabled={busy !== null}
            className="flex items-center justify-center gap-1.5 px-3 py-2 rounded border border-slate-300 bg-white hover:bg-slate-50 text-[12px] text-slate-700 disabled:opacity-50"
          >
            {busy === "sectors" ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            抓取行业+成分股
          </button>
          <button
            onClick={() => run("quotes", () => triggerQuoteRefresh(true), "行情抓取")}
            disabled={busy !== null}
            className="flex items-center justify-center gap-1.5 px-3 py-2 rounded border border-slate-300 bg-white hover:bg-slate-50 text-[12px] text-slate-700 disabled:opacity-50"
          >
            {busy === "quotes" ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            抓取行情（持仓股）
          </button>
        </div>
        <p className="text-[10px] text-slate-400 mt-2">
          首次使用请先抓取基金 → 行业 → 行情。完整流程约 10–15 分钟。完成后到「持仓看板」查看。
        </p>
      </div>

      {/* 调度任务 */}
      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="text-[13px] font-semibold text-slate-800 mb-2">已注册的调度任务</div>
        <table className="w-full text-[12px]">
          <thead className="text-slate-500 text-[11px]">
            <tr className="border-b border-slate-100">
              <th className="text-left py-1 font-normal">任务</th>
              <th className="text-left py-1 font-normal">触发规则</th>
              <th className="text-left py-1 font-normal">下次执行</th>
            </tr>
          </thead>
          <tbody>
            {scheduled.map((j) => (
              <tr key={j.id} className="border-b border-slate-50">
                <td className="py-1.5 text-slate-800">{j.name}</td>
                <td className="py-1.5 text-slate-500">{j.trigger}</td>
                <td className="py-1.5 tabular text-slate-700">
                  {j.next_run ? new Date(j.next_run).toLocaleString("zh-CN") : "--"}
                </td>
              </tr>
            ))}
            {scheduled.length === 0 && (
              <tr><td colSpan={3} className="text-center text-slate-400 py-3">暂无调度任务</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 抓取策略配置 */}
      <CrawlStrategySection
        configs={crawlConfigs}
        draft={draftConfigs}
        setDraft={setDraftConfigs}
        saving={saving}
        setSaving={setSaving}
        onSave={async () => {
          setSaving(true);
          try {
            const items = Object.values(draftConfigs);
            if (items.length === 0) {
              showToast("ok", "未修改");
            } else {
              await bulkUpdateCrawlConfigs(items);
              qc.invalidateQueries({ queryKey: ["crawl-configs"] });
              qc.invalidateQueries({ queryKey: ["scheduled-jobs"] });
              setDraftConfigs({});
              showToast("ok", `已保存 ${items.length} 条配置，调度器已热重载`);
            }
          } catch (e: any) {
            showToast("err", `保存失败：${formatErr(e)}`);
          } finally {
            setSaving(false);
          }
        }}
        onReset={async () => {
          if (!confirm("确定要重置所有抓取配置为默认值吗？")) return;
          try {
            await resetCrawlConfigs();
            qc.invalidateQueries({ queryKey: ["crawl-configs"] });
            qc.invalidateQueries({ queryKey: ["scheduled-jobs"] });
            setDraftConfigs({});
            showToast("ok", "已重置为默认配置");
          } catch (e: any) {
            showToast("err", `重置失败：${formatErr(e)}`);
          }
        }}
      />

      {/* 主力筛选默认阈值 */}
      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="text-[13px] font-semibold text-slate-800 mb-2">主力筛选默认阈值</div>
        <div className="flex items-center gap-3 text-[12px]">
          <label className="flex items-center gap-1.5">
            <span className="text-slate-500">规模 ≥</span>
            <input
              type="number"
              defaultValue={defaults?.min_scale}
              id="input-min-scale"
              className="w-20 px-1.5 py-0.5 border border-slate-300 rounded tabular"
            />
            <span className="text-slate-400">亿</span>
          </label>
          <label className="flex items-center gap-1.5">
            <span className="text-slate-500">近1年 ≥</span>
            <input
              type="number"
              defaultValue={defaults?.min_ret_1y}
              id="input-min-ret"
              className="w-20 px-1.5 py-0.5 border border-slate-300 rounded tabular"
            />
            <span className="text-slate-400">%</span>
          </label>
          <button
            onClick={async () => {
              const ms = Number((document.getElementById("input-min-scale") as HTMLInputElement).value);
              const mr = Number((document.getElementById("input-min-ret") as HTMLInputElement).value);
              await updateFilterDefaults({ min_scale: ms, min_ret_1y: mr });
              qc.invalidateQueries({ queryKey: ["filter-defaults"] });
              showToast("ok", "默认值已更新");
            }}
            className="px-2.5 py-0.5 rounded bg-slate-700 text-white hover:bg-slate-800"
          >
            保存
          </button>
          <button
            onClick={async () => {
              await resetFilterDefaults();
              qc.invalidateQueries({ queryKey: ["filter-defaults"] });
              showToast("ok", "已重置默认值");
            }}
            className="px-2.5 py-0.5 rounded border border-slate-300 text-slate-600 hover:bg-slate-50"
          >
            重置
          </button>
        </div>
        <p className="text-[10px] text-slate-400 mt-2">
          阈值越低 → 抓取的基金/股票越多（规模 ≥5亿 且 近1年 ≥5% 约 500+ 只基金）。修改后下次刷新基金生效。
        </p>
        <p className="text-[10px] text-slate-400 mt-1">
          自选股管理已迁移到「股票列表 → 我的自选」Tab。
        </p>
      </div>

      {/* 任务日志 */}
      <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
        <div className="px-3 py-2 border-b border-slate-100 text-[12px] text-slate-700 font-medium">
          最近任务日志（最新 50 条）
        </div>
        <table className="w-full text-[12px]">
          <thead className="bg-slate-50 text-slate-500 text-[11px]">
            <tr>
              <th className="text-left px-3 py-1.5 font-normal">时间</th>
              <th className="text-left px-3 py-1.5 font-normal">任务</th>
              <th className="text-left px-3 py-1.5 font-normal">状态</th>
              <th className="text-right px-3 py-1.5 font-normal">处理数</th>
              <th className="text-left px-3 py-1.5 font-normal">错误</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 && (
              <tr><td colSpan={5} className="text-center text-slate-400 py-4">暂无日志</td></tr>
            )}
            {jobs.map((j) => (
              <tr key={j.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-3 py-1.5 tabular text-slate-500">
                  {j.started_at ? new Date(j.started_at).toLocaleString("zh-CN") : "--"}
                </td>
                <td className="px-3 py-1.5 text-slate-800">{j.job_name}</td>
                <td className="px-3 py-1.5">
                  <span
                    className={`inline-flex items-center gap-1 text-[11px] ${
                      j.status === "success"
                        ? "text-emerald-600"
                        : j.status === "failed"
                        ? "text-red-600"
                        : "text-amber-600"
                    }`}
                  >
                    {j.status === "success" ? (
                      <CheckCircle2 className="w-3 h-3" />
                    ) : j.status === "failed" ? (
                      <AlertCircle className="w-3 h-3" />
                    ) : (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    )}
                    {j.status}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-right tabular text-slate-700">{j.items_processed}</td>
                <td className="px-3 py-1.5 text-red-500 text-[11px] truncate max-w-xs" title={j.error_message ?? ""}>
                  {j.error_message ?? ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {toast && (
        <div
          className={`fixed bottom-4 right-4 z-50 px-3 py-2 rounded shadow text-[12px] ${
            toast.type === "ok"
              ? "bg-emerald-600 text-white"
              : "bg-red-600 text-white"
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}

function formatErr(e: unknown): string {
  if (!e) return "未知错误";
  if (typeof e === "string") return e;
  const a = e as any;
  if (a.response?.data?.detail) {
    const d = a.response.data.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d.length) {
      return `${d[0].loc?.join(".") || "?"}: ${d[0].msg}`;
    }
    return JSON.stringify(d);
  }
  if (a.message) return a.message;
  try { return JSON.stringify(e); } catch { return String(e); }
}

// ---------- 抓取策略配置子组件 ----------
function CrawlStrategySection({
  configs,
  draft,
  setDraft,
  saving,
  onSave,
  onReset,
}: {
  configs: CrawlConfig[];
  draft: Record<string, CrawlConfig>;
  setDraft: React.Dispatch<React.SetStateAction<Record<string, CrawlConfig>>>;
  saving: boolean;
  setSaving: React.Dispatch<React.SetStateAction<boolean>>;
  onSave: () => void;
  onReset: () => void;
}) {
  // 合并：已保存配置 ∪ 用户草稿
  const merged: CrawlConfig[] = configs.map((c) => draft[c.job_key] || c);

  const updateField = <K extends keyof CrawlConfig>(key: string, field: K, value: CrawlConfig[K]) => {
    setDraft((prev) => {
      const base = prev[key] || configs.find((c) => c.job_key === key)!;
      // locked 任务的 trading_only 不允许改
      if (field === "trading_only" && base.trading_only_locked) {
        return prev;  // 忽略
      }
      return { ...prev, [key]: { ...base, [field]: value } };
    });
  };

  const dirtyCount = Object.keys(draft).length;

  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-[13px] font-semibold text-slate-800">抓取策略配置</div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            修改后保存即可热重载调度器，无需重启服务。
            <span className="ml-2">关闭=不调度 · daily=每天定时 · interval=按周期（可设交易窗口）</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onReset}
            disabled={saving}
            className="flex items-center gap-1 px-2 py-1 rounded border border-slate-300 text-slate-600 hover:bg-slate-50 text-[11px] disabled:opacity-50"
          >
            <RotateCcw className="w-3 h-3" /> 重置默认
          </button>
          <button
            onClick={onSave}
            disabled={saving || dirtyCount === 0}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-700 text-white hover:bg-slate-800 text-[11px] disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
            保存 {dirtyCount > 0 && <span className="ml-1">({dirtyCount})</span>}
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-[12px] min-w-[760px]">
          <thead className="text-slate-500 text-[11px] bg-slate-50">
            <tr>
              <th className="text-left py-1.5 px-2 font-normal w-8">开</th>
              <th className="text-left py-1.5 px-2 font-normal">任务</th>
              <th className="text-left py-1.5 px-2 font-normal w-24">类型</th>
              <th className="text-left py-1.5 px-2 font-normal w-32">频率/时间</th>
              <th className="text-left py-1.5 px-2 font-normal w-40">运行窗口</th>
              <th className="text-left py-1.5 px-2 font-normal w-16">仅交易日</th>
              <th className="text-left py-1.5 px-2 font-normal">说明</th>
            </tr>
          </thead>
          <tbody>
            {merged.map((c) => {
              const dirty = !!draft[c.job_key];
              const showIntervalFields = c.cron_type === "interval";
              return (
                <tr key={c.job_key} className={`border-t border-slate-100 ${dirty ? "bg-amber-50/50" : ""}`}>
                  {/* 开关 */}
                  <td className="py-1.5 px-2">
                    <button
                      onClick={() => updateField(c.job_key, "enabled", !c.enabled)}
                      className={`w-7 h-4 rounded-full transition-colors relative ${
                        c.enabled ? "bg-emerald-500" : "bg-slate-300"
                      }`}
                      title={c.enabled ? "已启用" : "已关闭"}
                    >
                      <span
                        className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${
                          c.enabled ? "left-3.5" : "left-0.5"
                        }`}
                      />
                    </button>
                  </td>
                  {/* 任务名 */}
                  <td className="py-1.5 px-2 text-slate-800">
                    <div>{c.display_name}</div>
                    <div className="text-[10px] text-slate-400 font-mono">{c.job_key}</div>
                  </td>
                  {/* 类型 */}
                  <td className="py-1.5 px-2">
                    <select
                      value={c.cron_type}
                      onChange={(e) => updateField(c.job_key, "cron_type", e.target.value as CrawlConfig["cron_type"])}
                      disabled={!c.enabled}
                      className="px-1.5 py-0.5 border border-slate-300 rounded text-[12px] disabled:bg-slate-50 disabled:text-slate-400"
                    >
                      <option value="off">关闭</option>
                      <option value="daily">每天定时</option>
                      <option value="interval">按周期</option>
                    </select>
                  </td>
                  {/* 频率/时间 */}
                  <td className="py-1.5 px-2">
                    {c.cron_type === "daily" && (
                      <input
                        type="time"
                        value={c.time_of_day}
                        onChange={(e) => updateField(c.job_key, "time_of_day", e.target.value)}
                        disabled={!c.enabled}
                        className="w-24 px-1.5 py-0.5 border border-slate-300 rounded tabular text-[12px] disabled:bg-slate-50"
                      />
                    )}
                    {c.cron_type === "interval" && (
                      <div className="flex items-center gap-1">
                        <span className="text-slate-500 text-[11px]">每</span>
                        <input
                          type="number"
                          min={1}
                          max={1440}
                          value={c.interval_minutes}
                          onChange={(e) => updateField(c.job_key, "interval_minutes", Number(e.target.value) || 1)}
                          disabled={!c.enabled}
                          className="w-14 px-1.5 py-0.5 border border-slate-300 rounded tabular text-[12px] disabled:bg-slate-50"
                        />
                        <span className="text-slate-500 text-[11px]">分</span>
                      </div>
                    )}
                    {c.cron_type === "off" && <span className="text-slate-300">--</span>}
                  </td>
                  {/* 运行窗口：仅 interval 任务有效 */}
                  <td className="py-1.5 px-2">
                    {showIntervalFields ? (
                      <div className="flex items-center gap-1">
                        <input
                          type="time"
                          value={c.window_start}
                          onChange={(e) => updateField(c.job_key, "window_start", e.target.value)}
                          disabled={!c.enabled}
                          className="w-20 px-1.5 py-0.5 border border-slate-300 rounded tabular text-[12px] disabled:bg-slate-50"
                        />
                        <span className="text-slate-400 text-[11px]">~</span>
                        <input
                          type="time"
                          value={c.window_end}
                          onChange={(e) => updateField(c.job_key, "window_end", e.target.value)}
                          disabled={!c.enabled}
                          className="w-20 px-1.5 py-0.5 border border-slate-300 rounded tabular text-[12px] disabled:bg-slate-50"
                        />
                      </div>
                    ) : (
                      <span className="text-slate-300 text-[11px]">--</span>
                    )}
                  </td>
                  {/* 仅交易日：locked 任务显示🔒，不可改 */}
                  <td className="py-1.5 px-2">
                    <div className="flex items-center gap-1">
                      <input
                        type="checkbox"
                        checked={c.trading_only}
                        disabled={c.trading_only_locked || !c.enabled}
                        onChange={(e) => updateField(c.job_key, "trading_only", e.target.checked)}
                        className="w-3.5 h-3.5 disabled:cursor-not-allowed"
                        title={
                          c.trading_only_locked
                            ? "已强制锁定：周末/节假日抓取无意义，不可修改"
                            : "勾选：仅 A 股交易日抓取"
                        }
                      />
                      {c.trading_only_locked && (
                        <Lock className="w-3 h-3 text-slate-400" />
                      )}
                    </div>
                  </td>
                  {/* 说明 */}
                  <td className="py-1.5 px-2 text-[11px] text-slate-500 leading-tight">
                    {c.description}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
