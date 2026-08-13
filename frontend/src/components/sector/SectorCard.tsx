import type { SectorGroup } from "@/types/api";
import { StockChip } from "./StockChip";
import { ArrowUp, ArrowDown, ChevronRight } from "lucide-react";
import clsx from "clsx";

interface SectorCardProps {
  sector: SectorGroup;
  dragging?: boolean;
  onSectorClick?: () => void;
  onStockClick?: (code: string) => void;
  onShowAllStocks?: () => void;
}

function fmtMv(v?: number) {
  if (v === null || v === undefined) return "--";
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(0)}万`;
  return v.toFixed(0);
}

function fmtPct(v?: number) {
  if (v === null || v === undefined) return "--";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

export function SectorCard({ sector, dragging, onSectorClick, onStockClick, onShowAllStocks }: SectorCardProps) {
  const up = (sector.avg_change_pct ?? 0) > 0;
  const down = (sector.avg_change_pct ?? 0) < 0;

  return (
    <div
      onClick={(e) => {
        // 仅当点击的是卡片本身（不是子按钮）时触发板块筛选
        if ((e.target as HTMLElement).closest("button")) return;
        onSectorClick?.();
      }}
      className={clsx(
        "rounded-md border bg-white p-2.5 cursor-pointer select-none",
        "border-slate-200 hover:border-slate-300 hover:shadow-md",
        "transition-all duration-150 hover:-translate-y-0.5",
        dragging && "opacity-40"
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[13px] font-semibold text-slate-800">
            {sector.industry_name}
          </span>
          <span className="text-[10px] text-slate-400 tabular">
            {sector.stock_count}只
            {(sector.funded_count ?? 0) > 0 && sector.funded_count !== sector.stock_count && (
              <span className="text-slate-300">（{sector.funded_count}只重仓）</span>
            )}
          </span>
        </div>
        <div
          className={clsx(
            "text-[11px] tabular flex items-center gap-0.5 px-1.5 py-0.5 rounded",
            up
              ? "text-up bg-red-50"
              : down
              ? "text-down bg-green-50"
              : "text-slate-500 bg-slate-50"
          )}
        >
          {up && <ArrowUp className="w-2.5 h-2.5" />}
          {down && <ArrowDown className="w-2.5 h-2.5" />}
          {fmtPct(sector.avg_change_pct)}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {sector.stocks.slice(0, 6).map((s) => (
          <StockChip
            key={s.code}
            stock={s}
            onClick={() => onStockClick?.(s.code)}
          />
        ))}
      </div>
      <div className="flex items-center justify-between gap-2 mt-1.5">
        <div className="text-[10px] text-slate-400 tabular">
          持仓市值 {fmtMv(sector.total_market_value)}
        </div>
        {sector.stocks.length > 6 && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onShowAllStocks?.();
            }}
            className="flex items-center gap-0.5 text-[10px] text-slate-500 hover:text-blue-600 hover:bg-blue-50/60 rounded px-1.5 py-0.5 transition-colors"
          >
            <span>还有 {sector.stocks.length - 6} 只未显示</span>
            <span className="text-blue-500">查看全部</span>
            <ChevronRight className="w-3 h-3 text-blue-500" />
          </button>
        )}
      </div>
    </div>
  );
}
