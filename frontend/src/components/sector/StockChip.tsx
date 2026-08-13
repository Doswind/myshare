import type { SectorStock } from "@/types/api";
import { TrendingUp, TrendingDown } from "lucide-react";
import clsx from "clsx";

interface StockChipProps {
  stock: SectorStock;
  onClick?: () => void;
}

function fmtPct(v?: number) {
  if (v === null || v === undefined) return "--";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

function fmtPrice(v?: number) {
  if (v === null || v === undefined) return "--";
  return v.toFixed(2);
}

export function StockChip({ stock, onClick }: StockChipProps) {
  const up = (stock.change_pct ?? 0) > 0;
  const down = (stock.change_pct ?? 0) < 0;
  return (
    <button
      onClick={onClick}
      className={clsx(
        "group flex flex-col items-start px-2 py-1.5 rounded border",
        "border-slate-200 bg-slate-50 hover:bg-slate-100 hover:border-slate-300",
        "transition-all duration-150 text-left"
      )}
    >
      <div className="flex items-center gap-1.5">
        <span className="text-[12px] text-slate-800 font-medium truncate max-w-[100px]">
          {stock.name}
        </span>
        <span className="text-[10px] text-slate-400 tabular">{stock.code}</span>
      </div>
      <div className="flex items-center gap-1.5 mt-0.5">
        <span className="text-[11px] tabular text-slate-700">{fmtPrice(stock.price)}</span>
        <span
          className={clsx(
            "text-[10px] tabular flex items-center gap-0.5",
            up ? "text-up" : down ? "text-down" : "text-slate-500"
          )}
        >
          {up && <TrendingUp className="w-2.5 h-2.5" />}
          {down && <TrendingDown className="w-2.5 h-2.5" />}
          {fmtPct(stock.change_pct)}
        </span>
        <span className="text-[10px] text-slate-400">×{stock.fund_count}</span>
      </div>
    </button>
  );
}
