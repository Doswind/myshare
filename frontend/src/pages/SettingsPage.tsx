import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchFilterDefaults, updateFilterDefaults, resetFilterDefaults } from "@/api/funds";
import {
  fetchJobs,
  fetchScheduledJobs,
  fetchRunningJobs,
  triggerFundRefresh,
  triggerHoldingsRefresh,
  triggerQuoteRefresh,
  triggerSectorRefresh,
} from "@/api/stocks";
import {
  fetchCrawlConfigs,
  bulkUpdateCrawlConfigs,
  resetCrawlConfigs,
} from "@/api/crawlConfig";
import type { CrawlConfig } from "@/types/api";
import { RefreshCw, CheckCircle2, AlertCircle, Loader2, Save, RotateCcw, Lock, Clock } from "lucide-react";
import { ConfirmDialog, type ConfirmOptions } from "@/components/common/ConfirmDialog";
import { Pagination } from "@/components/common/Pagination";
import { useAuth } from "@/contexts/AuthContext";
import { cleanupStuckJobs } from "@/api/stocks";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data: defaults } = useQuery({ queryKey: ["filter-defaults"], queryFn: fetchFilterDefaults });
  const { data: scheduled = [] } = useQuery({
    queryKey: ["scheduled-jobs"],
    queryFn: fetchScheduledJobs,
    refetchInterval: 30_000,
  });
  const [jobPage, setJobPage] = useState(1);
  const [jobPageSize] = useState(20);
  const { data: jobsData } = useQuery({
    queryKey: ["job-logs", jobPage, jobPageSize],
    queryFn: () => fetchJobs(jobPage, jobPageSize),
    refetchInterval: 10_000,
  });
  const jobs = jobsData?.items ?? [];
  const jobTotal = jobsData?.total ?? 0;
  const jobTotalPages = Math.max(1, Math.ceil(jobTotal / jobPageSize));
  const { data: crawlConfigs = [] } = useQuery({
    queryKey: ["crawl-configs"],
    queryFn: fetchCrawlConfigs,
    refetchInterval: 15_000,
  });
  // 任务运行状态 + 冷却期（每秒刷新）
  const { data: runningInfo } = useQuery({
    queryKey: ["job-running"],
    queryFn: fetchRunningJobs,
    refetchInterval: 5_000,
  });
  const inMemoryLocks: string[] = (runningInfo as any)?.in_memory_locks ?? [];
  const serverCooldownsRaw: Record<string, number> = (runningInfo as any)?.cooldowns ?? {};
  const serverCooldowns: Record<string, number> = {
    funds: serverCooldownsRaw.manual_funds ?? 0,
    holdings: serverCooldownsRaw.manual_holdings ?? 0,
    sectors: serverCooldownsRaw.manual_sectors ?? 0,
    quotes: serverCooldownsRaw.manual_quotes ?? 0,
  };
  // DB running 兜底：进程重启后内存锁丢失，但 DB 仍有 running 记录时也禁止重复触发
  const dbRunningIds: string[] = ((runningInfo as any)?.db_running_recent ?? []).map(
    (j: any) => j.job_id as string,
  );

  const [busy, setBusy] = useState<string | null>(null);
  const [cooldowns, setCooldowns] = useState<Record<string, number>>({});
  // 每秒 +1 触发 running 任务耗时重新渲染
  const [tick, setTick] = useState(0);
  const { user } = useAuth();
  const isAdmin = user?.is_admin ?? false;
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);
  const [confirmState, setConfirmState] = useState<(ConfirmOptions & { onOk: () => void }) | null>(null);
  const [draftConfigs, setDraftConfigs] = useState<Record<string, CrawlConfig>>({});
  const [saving, setSaving] = useState(false);

  // 同步服务端冷却期到本地
  useEffect(() => {
    setCooldowns((prev) => {
      const next = { ...serverCooldowns };
      // 保留本地已经开始倒计时的项（避免后端 5s 刷新延迟导致归零）
      for (const k of Object.keys(prev)) {
        if (prev[k] > 0 && (!next[k] || next[k] > prev[k])) {
          next[k] = prev[k];
        }
      }
      return next;
    });
  }, [serverCooldowns]);

  // 倒计时
  useEffect(() => {
    if (Object.values(cooldowns).every((v) => v <= 0)) return;
    const t = setInterval(() => {
      setCooldowns((prev) => {
        const next: Record<string, number> = {};
        let changed = false;
        for (const [k, v] of Object.entries(prev)) {
          const nv = Math.max(0, v - 1);
          next[k] = nv;
          if (nv !== v) changed = true;
        }
        return changed ? next : prev;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [cooldowns]);

  // running 任务耗时 tick（每 1s 触发一次重渲染）
  useEffect(() => {
    const hasRunning = jobs.some((j) => j.status === "running");
    if (!hasRunning) return;
    const t = setInterval(() => setTick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [jobs]);

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
      qc.invalidateQueries({ queryKey: ["job-running"] });
    } catch (e: any) {
      // 429 冷却：把剩余秒数写本地
      const status = e?.response?.status;
      if (status === 429) {
        const remain = Number(e?.response?.headers?.["x-cooldown-remaining"] || 0);
        if (remain > 0) {
          setCooldowns((prev) => ({ ...prev, [key]: remain }));
        }
      }
      showToast("err", `${label}失败：${formatErr(e)}`);
    } finally {
      setBusy(null);
    }
  };

  /** 二次确认后真正执行 */
  const confirmAndRun = (
    key: string,
    fn: () => Promise<any>,
    label: string,
    description: string,
  ) => {
    setConfirmState({
      title: `确认${label}？`,
      description,
      confirmText: `开始${label}`,
      variant: "info",
      onOk: () => {
        setConfirmState(null);
        void run(key, fn, label);
      },
    });
  };

  // 通用冷却判断
  const cooldown = (key: string) => cooldowns[key] ?? 0;

  // 逻辑任务组：组内任一任务在跑（定时 sched_* 或手动 manual_*，含 DB running 兜底），
  // 对应手动按钮都禁用，避免重复触发同一任务
  const LOCK_GROUPS: Record<string, string[]> = {
    funds: ["sched_funds_full", "manual_funds"],
    holdings: ["manual_holdings"],
    sectors: ["sched_sectors", "manual_sectors"],
    quotes: ["sched_quotes", "manual_quotes"],
  };
  const lockIds = new Set([...inMemoryLocks, ...dbRunningIds]);
  const isInLock = (key: string) =>
    (LOCK_GROUPS[key] ?? [`manual_${key}`]).some((k) => lockIds.has(k));

  return (
    <div className="space-y-3 max-w-4xl">
      {/* 抓取触发 */}
      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="text-[13px] font-semibold text-slate-800 mb-2">手动抓取</div>
        <div className="grid grid-cols-4 gap-2">
          <RefreshButton
            label="基金+持仓"
            hint="约 20–30 分钟"
            busy={busy === "funds"}
            disabled={busy !== null || cooldown("funds") > 0 || isInLock("funds")}
            cooldownSec={cooldown("funds")}
            inLock={isInLock("funds")}
            onClick={() => confirmAndRun(
              "funds",
              triggerFundRefresh,
              "基金+持仓抓取",
              "将全量抓取基金列表并按阈值过滤入库（清除不再满足阈值的旧基金），然后抓取全部基金的最新季报重仓持仓。\n耗时约 5-10 分钟，完成后 30 分钟内不允许再次触发。",
            )}
          />
          <RefreshButton
            label="仅刷新持仓"
            hint="约 15–25 分钟"
            busy={busy === "holdings"}
            disabled={busy !== null || cooldown("holdings") > 0 || isInLock("holdings")}
            cooldownSec={cooldown("holdings")}
            inLock={isInLock("holdings")}
            onClick={() => confirmAndRun(
              "holdings",
              triggerHoldingsRefresh,
              "持仓抓取",
              "将拉取 fund 表中全部基金的最新季报重仓持仓，不刷新基金列表。\n耗时约 5-10 分钟，完成后 30 分钟内不允许再次触发。",
            )}
          />
          <RefreshButton
            label="行业+成分股"
            hint="约 1–2 分钟"
            busy={busy === "sectors"}
            disabled={busy !== null || cooldown("sectors") > 0 || isInLock("sectors")}
            cooldownSec={cooldown("sectors")}
            inLock={isInLock("sectors")}
            onClick={() => confirmAndRun(
              "sectors",
              triggerSectorRefresh,
              "行业+成分股抓取",
              "将刷新全部行业分类及成分股数据。\n完成后 15 分钟内不允许再次触发。",
            )}
          />
          <RefreshButton
            label="行情（持仓股）"
            hint="约 30 秒"
            busy={busy === "quotes"}
            disabled={busy !== null || cooldown("quotes") > 0 || isInLock("quotes")}
            cooldownSec={cooldown("quotes")}
            inLock={isInLock("quotes")}
            onClick={() => confirmAndRun(
              "quotes",
              () => triggerQuoteRefresh(true),
              "行情抓取",
              "将刷新所有持仓股的实时行情（最近 1 分钟快照）。\n完成后 1 分钟内不允许再次触发。",
            )}
          />
        </div>
        <p className="text-[10px] text-slate-400 mt-2">
          首次使用请先抓「基金+持仓」→ 行业 → 行情。完整流程约 20–30 分钟。完成后到「持仓看板」查看。
          <span className="ml-1">「仅刷新持仓」适用于基金列表已是最新、只需补充持仓数据的场景。</span>
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
                  {j.next_run ? formatBeijingTime(j.next_run) : "--"}
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
          setConfirmState({
            title: "重置所有抓取配置",
            description: "确定要重置所有抓取任务为默认配置吗？\n此操作不可撤销。",
            confirmText: "重置",
            variant: "warning",
            onOk: async () => {
              setConfirmState(null);
              try {
                await resetCrawlConfigs();
                qc.invalidateQueries({ queryKey: ["crawl-configs"] });
                qc.invalidateQueries({ queryKey: ["scheduled-jobs"] });
                setDraftConfigs({});
                showToast("ok", "已重置为默认配置");
              } catch (e: any) {
                showToast("err", `重置失败：${formatErr(e)}`);
              }
            },
          });
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
          阈值控制基金抓取范围（规模≥5亿 且 近1年≥5%）。fund 表只存满足阈值的基金，持仓看板从此范围内聚合股票。修改阈值后需重新抓「基金+持仓」生效。
        </p>
        <p className="text-[10px] text-slate-400 mt-1">
          自选股管理已迁移到「股票列表 → 我的自选」Tab。
        </p>
      </div>

      {/* 任务日志 */}
      <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
        <div className="px-3 py-2 border-b border-slate-100 text-[12px] text-slate-700 font-medium flex items-center justify-between">
          <span>任务日志（共 {jobTotal} 条）</span>
          {isAdmin && (
            <button
              onClick={() => {
                setConfirmState({
                  title: "清理卡住的任务？",
                  description: "将把 running 状态超过 30 分钟的任务标记为 failed，并释放对应 JobGuard 锁。\n不会影响正在运行（<30 分钟）的任务。",
                  confirmText: "清理",
                  variant: "warning",
                  onOk: async () => {
                    setConfirmState(null);
                    try {
                      const r = await cleanupStuckJobs(30);
                      qc.invalidateQueries({ queryKey: ["job-logs"] });
                      qc.invalidateQueries({ queryKey: ["job-running"] });
                      showToast("ok", `已清理 ${r.cleaned_count} 条卡住任务${r.cleaned.length ? `（${r.cleaned.map((x) => x.job_id).join("、")}）` : ""}`);
                    } catch (e: any) {
                      showToast("err", `清理失败：${formatErr(e)}`);
                    }
                  },
                });
              }}
              className="flex items-center gap-1 px-2 py-0.5 rounded border border-amber-300 text-amber-700 hover:bg-amber-50 text-[11px]"
            >
              <AlertCircle className="w-3 h-3" /> 清理卡住任务
            </button>
          )}
        </div>
        <div className="text-[10px] text-slate-400 px-3 py-1 bg-slate-50 border-b border-slate-100">
          「开始时间」= 任务启动时间 ·「耗时」= 当前 - 开始时间（运行中实时刷新）·「结束时间」= 任务正常完成 / 失败 / 取消的时间
        </div>
        <table className="w-full text-[12px]">
          <thead className="bg-slate-50 text-slate-500 text-[11px]">
            <tr>
              <th className="text-left px-3 py-1.5 font-normal">任务</th>
              <th className="text-left px-3 py-1.5 font-normal">状态</th>
              <th className="text-left px-3 py-1.5 font-normal">开始时间</th>
              <th className="text-right px-3 py-1.5 font-normal">耗时</th>
              <th className="text-left px-3 py-1.5 font-normal">结束时间</th>
              <th className="text-right px-3 py-1.5 font-normal">处理数</th>
              <th className="text-left px-3 py-1.5 font-normal">错误</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 && (
              <tr><td colSpan={7} className="text-center text-slate-400 py-4">暂无日志</td></tr>
            )}
            {jobs.map((j) => {
              const isRunning = j.status === "running";
              // 耗时：running = now - started；success/failed = finished - started
              const startedMs = j.started_at ? new Date(j.started_at).getTime() : 0;
              const finishedMs = j.finished_at ? new Date(j.finished_at).getTime() : 0;
              const durationSec = startedMs
                ? Math.max(0, Math.floor(((finishedMs || Date.now()) - startedMs) / 1000))
                : 0;
              const isLongRunning = isRunning && durationSec > 600;  // >10 分钟亮红，提示卡住
              return (
                <tr key={j.id} className="border-t border-slate-100 hover:bg-slate-50">
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
                  <td className="px-3 py-1.5 tabular text-slate-500">
                    {j.started_at ? formatBeijingTime(j.started_at) : "--"}
                  </td>
                  <td className={`px-3 py-1.5 text-right tabular ${isLongRunning ? "text-red-600 font-semibold" : "text-slate-700"}`}>
                    {formatDuration(durationSec)}
                    {isLongRunning && <span className="ml-1 text-[10px]">⚠ 卡住</span>}
                  </td>
                  <td className="px-3 py-1.5 tabular text-slate-500">
                    {j.finished_at ? formatBeijingTime(j.finished_at, "time") : (
                      <span className="text-amber-600 text-[10px]">进行中…</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular text-slate-700">{j.items_processed}</td>
                  <td className="px-3 py-1.5 text-red-500 text-[11px] truncate max-w-xs" title={j.error_message ?? ""}>
                    {j.error_message ?? ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <Pagination
          page={jobPage}
          totalPages={jobTotalPages}
          total={jobTotal}
          pageSize={jobPageSize}
          onPageChange={setJobPage}
        />
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

      {confirmState && (
        <ConfirmDialog
          open
          title={confirmState.title}
          description={confirmState.description}
          confirmText={confirmState.confirmText}
          cancelText={confirmState.cancelText}
          variant={confirmState.variant}
          onConfirm={confirmState.onOk}
          onCancel={() => setConfirmState(null)}
        />
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

/** 格式化秒数：>=60 显示「X 分钟 Y 秒」，否则「Y 秒」 */
function formatRemain(sec: number): string {
  if (sec >= 60) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return s > 0 ? `${m}分${s}秒` : `${m}分钟`;
  }
  return `${sec}秒`;
}

/** 格式化耗时：>1h 显示「X 小时 Y 分」，>60s 显示「X 分 Y 秒」，否则「Y 秒」 */
function formatDuration(sec: number): string {
  if (sec >= 3600) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return m > 0 ? `${h}h${m}m` : `${h}h`;
  }
  return formatRemain(sec);
}

/** 把 ISO 时间字符串强制按 Asia/Shanghai 时区格式化（避免依赖浏览器时区）

  - mode = "datetime"（默认）：「YYYY/M/D HH:MM:SS」+ 当天只显示时分
  - mode = "time"：只显示「HH:MM:SS」

  后端存的 naive UTC 会被 to_dict 加 +00:00 后输出，所以
  「2026-08-13T16:30:50+00:00」= 北京时间「2026-08-14 00:30:50」
*/
function formatBeijingTime(iso: string, mode: "datetime" | "time" = "datetime"): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--";
  const dateStr = d.toLocaleDateString("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "numeric",
    day: "numeric",
  });
  const timeStr = d.toLocaleTimeString("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour12: false,
  });
  if (mode === "time") return timeStr;
  // 当天不显示日期
  const now = new Date();
  const todayStr = now.toLocaleDateString("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "numeric",
    day: "numeric",
  });
  if (dateStr === todayStr) return timeStr;
  return `${dateStr} ${timeStr}`;
}

/** 手动抓取按钮：带繁忙/冷却/锁三态显示 */
function RefreshButton({
  label,
  hint,
  busy,
  disabled,
  cooldownSec,
  inLock,
  onClick,
}: {
  label: string;
  hint: string;
  busy: boolean;
  disabled: boolean;
  cooldownSec: number;
  inLock: boolean;
  onClick: () => void;
}) {
  const inCooldown = cooldownSec > 0;
  // 状态文案优先级：在跑 > 锁中 > 冷却 > 就绪
  let stateText = hint;
  let stateColor = "text-slate-400";
  let Icon = RefreshCw;
  if (busy) {
    stateText = "正在抓取…";
    stateColor = "text-amber-600";
    Icon = Loader2;
  } else if (inLock) {
    stateText = "已有任务在执行中";
    stateColor = "text-amber-600";
  } else if (inCooldown) {
    stateText = `冷却中（${formatRemain(cooldownSec)}）`;
    stateColor = "text-slate-500";
    Icon = Clock;
  }

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex flex-col items-center justify-center gap-0.5 px-3 py-2 rounded border border-slate-300 bg-white hover:bg-slate-50 text-[12px] text-slate-700 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white"
    >
      <span className="flex items-center gap-1.5">
        <Icon className={`w-3 h-3 ${busy ? "animate-spin" : ""}`} />
        {label}
      </span>
      <span className={`text-[10px] ${stateColor}`}>{stateText}</span>
    </button>
  );
}

// ---------- 抓取策略配置子组件 ----------
const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

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
            <span className="ml-2">关闭=不调度 · daily=每天定时 · weekly=每周定时 · interval=按周期（可设交易窗口）</span>
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
              <th className="text-left py-1.5 px-2 font-normal w-48">频率/时间</th>
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
                      <option value="weekly">每周定时</option>
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
                    {c.cron_type === "weekly" && (
                      <div className="flex items-center gap-1">
                        <span className="text-slate-500 text-[11px]">每</span>
                        <select
                          value={c.day_of_week ?? 0}
                          onChange={(e) => updateField(c.job_key, "day_of_week", Number(e.target.value))}
                          disabled={!c.enabled}
                          className="px-1.5 py-0.5 border border-slate-300 rounded text-[12px] disabled:bg-slate-50 disabled:text-slate-400"
                        >
                          {WEEKDAYS.map((w, i) => (
                            <option key={i} value={i}>{w}</option>
                          ))}
                        </select>
                        <input
                          type="time"
                          value={c.time_of_day}
                          onChange={(e) => updateField(c.job_key, "time_of_day", e.target.value)}
                          disabled={!c.enabled}
                          className="w-[74px] px-1.5 py-0.5 border border-slate-300 rounded tabular text-[12px] disabled:bg-slate-50"
                        />
                      </div>
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
