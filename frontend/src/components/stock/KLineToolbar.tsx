import clsx from "clsx";

export type KLinePeriod = "daily" | "weekly" | "monthly" | "yearly";

interface Props {
  period: KLinePeriod;
  onPeriodChange: (p: KLinePeriod) => void;
  dataAsOf?: string | null;
  onRefresh?: () => void;
  refreshing?: boolean;
}

const PERIODS: { key: KLinePeriod; label: string }[] = [
  { key: "daily", label: "日" },
  { key: "weekly", label: "周" },
  { key: "monthly", label: "月" },
  { key: "yearly", label: "年" },
];

export function KLineToolbar({
  period,
  onPeriodChange,
  dataAsOf,
  onRefresh,
  refreshing,
}: Props) {
  return (
    <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-slate-200 bg-slate-50">
      <div className="flex items-center gap-1">
        {PERIODS.map((p) => (
          <button
            key={p.key}
            onClick={() => onPeriodChange(p.key)}
            className={clsx(
              "rounded px-2.5 py-0.5 text-[11px] transition-colors",
              period === p.key
                ? "bg-blue-500 text-white"
                : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200",
            )}
          >
            {p.label}
          </button>
        ))}
        <span className="ml-2 text-[10px] text-slate-400">前复权</span>
      </div>
      <div className="flex items-center gap-2 text-[10px] text-slate-400">
        {dataAsOf && <span>数据更新于 {dataAsOf}</span>}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className="rounded border border-slate-200 px-1.5 py-0.5 text-[10px] hover:bg-slate-100 disabled:opacity-50"
          >
            {refreshing ? "刷新中…" : "刷新"}
          </button>
        )}
      </div>
    </div>
  );
}