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
  fetchWatchlist,
  addWatchlist,
  removeWatchlist,
} from "@/api/watchlist";
import { RefreshCw, CheckCircle2, AlertCircle, Loader2, Star, Trash2, X } from "lucide-react";
import { Modal } from "@/components/common/RangeSlider";

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
  const { data: watchlist = [], refetch: refetchWatchlist } = useQuery({
    queryKey: ["watchlist"],
    queryFn: fetchWatchlist,
    refetchInterval: 60_000,
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);
  const [wlCode, setWlCode] = useState("");
  const [wlNote, setWlNote] = useState("");

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
      showToast("err", `${label}失败：${e.message}`);
    } finally {
      setBusy(null);
    }
  };

  const addWl = async () => {
    const code = wlCode.trim();
    if (!/^\d{6}$/.test(code)) {
      showToast("err", "股票代码必须是 6 位数字");
      return;
    }
    setBusy("wl-add");
    try {
      const it = await addWatchlist(code, undefined, wlNote);
      showToast("ok", `已添加：${it.name || code}`);
      setWlCode("");
      setWlNote("");
      refetchWatchlist();
      qc.invalidateQueries({ queryKey: ["watchlist"] });
    } catch (e: any) {
      showToast("err", `添加失败：${e.message}`);
    } finally {
      setBusy(null);
    }
  };

  const removeWl = async (code: string) => {
    try {
      await removeWatchlist(code);
      showToast("ok", `已移除 ${code}`);
      refetchWatchlist();
      qc.invalidateQueries({ queryKey: ["watchlist"] });
    } catch (e: any) {
      showToast("err", `移除失败：${e.message}`);
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
      </div>

      {/* 自选股管理 */}
      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="text-[13px] font-semibold text-slate-800 mb-2 flex items-center gap-1.5">
          <Star className="w-3.5 h-3.5 text-amber-500" />
          我的自选股
        </div>
        <div className="flex flex-wrap items-center gap-2 mb-2 text-[12px]">
          <input
            value={wlCode}
            onChange={(e) => setWlCode(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addWl()}
            placeholder="6 位股票代码，如 300401"
            className="w-44 px-2 py-0.5 border border-slate-300 rounded tabular"
            maxLength={6}
          />
          <input
            value={wlNote}
            onChange={(e) => setWlNote(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addWl()}
            placeholder="备注（可选）"
            className="flex-1 min-w-[160px] px-2 py-0.5 border border-slate-300 rounded"
          />
          <button
            onClick={addWl}
            disabled={busy === "wl-add"}
            className="px-3 py-0.5 rounded bg-slate-700 text-white hover:bg-slate-800 disabled:opacity-50 flex items-center gap-1"
          >
            {busy === "wl-add" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Star className="w-3 h-3" />}
            添加
          </button>
        </div>
        <div className="text-[11px] text-slate-500 mb-1.5">共 {watchlist.length} 只</div>
        <div className="rounded border border-slate-100 overflow-hidden">
          {watchlist.length === 0 ? (
            <div className="text-center text-slate-400 py-4 text-[12px]">
              暂无自选股，输入 6 位代码添加
            </div>
          ) : (
            <table className="w-full text-[12px]">
              <thead className="bg-slate-50 text-slate-500 text-[11px]">
                <tr>
                  <th className="text-left px-3 py-1.5 font-normal">代码</th>
                  <th className="text-left px-3 py-1.5 font-normal">名称</th>
                  <th className="text-left px-3 py-1.5 font-normal">行业</th>
                  <th className="text-right px-3 py-1.5 font-normal">现价</th>
                  <th className="text-right px-3 py-1.5 font-normal">涨跌幅</th>
                  <th className="text-right px-3 py-1.5 font-normal">重仓基金</th>
                  <th className="text-left px-3 py-1.5 font-normal">备注</th>
                  <th className="text-right px-3 py-1.5 font-normal"></th>
                </tr>
              </thead>
              <tbody>
                {watchlist.map((w) => (
                  <tr key={w.code} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-3 py-1.5 tabular text-slate-500">{w.code}</td>
                    <td className="px-3 py-1.5 text-slate-800">{w.name || <span className="text-slate-400">加载中…</span>}</td>
                    <td className="px-3 py-1.5 text-slate-500">{w.industry_name ?? "--"}</td>
                    <td className="px-3 py-1.5 text-right tabular text-slate-700">
                      {w.price != null ? w.price.toFixed(2) : "--"}
                    </td>
                    <td
                      className={`px-3 py-1.5 text-right tabular ${
                        (w.change_pct ?? 0) >= 0 ? "text-up" : "text-down"
                      }`}
                    >
                      {w.change_pct != null ? `${w.change_pct >= 0 ? "+" : ""}${w.change_pct.toFixed(2)}%` : "--"}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular text-slate-700">
                      {w.fund_count > 0 ? (
                        <span className="inline-flex items-center justify-center min-w-[24px] px-1.5 py-0.5 rounded text-[10px] bg-blue-50 text-blue-700 border border-blue-100">
                              {w.fund_count}
                            </span>
                      ) : (
                        <span className="text-slate-400">0</span>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-slate-500 text-[11px] truncate max-w-[160px]">
                      {w.note || <span className="text-slate-300">--</span>}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      <button
                        onClick={() => removeWl(w.code)}
                        className="text-slate-400 hover:text-red-500 transition-colors"
                        title="移除"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <p className="text-[10px] text-slate-400 mt-2">
          提示：自选股添加后会立即触发一次性行情抓取。在「股票列表」可查看「我的自选」专属分组。
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
