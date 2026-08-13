import { useState, useMemo } from "react";
import type { SectorGroup, SectorStock } from "@/types/api";
import { createPortal } from "react-dom";
import { X, Search, ArrowUp, ArrowDown } from "lucide-react";
import clsx from "clsx";

interface SectorAllStocksModalProps {
  sector: SectorGroup | null;
  reportDate?: string;
  onClose: () => void;
  onStockClick?: (code: string) => void;
}

type SortKey = "fund_count" | "change_pct" | "total_market_value" | "price";

function fmtPct(v?: number | null) {
  if (v === null || v === undefined) return "--";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

function fmtMv(v?: number | null) {
  if (v === null || v === undefined) return "--";
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(0)}万`;
  return v.toFixed(0);
}

function fmtPrice(v?: number | null) {
  if (v === null || v === undefined) return "--";
  return v.toFixed(2);
}

export function SectorAllStocksModal({ sector, reportDate, onClose, onStockClick }: SectorAllStocksModalProps) {
  const [keyword, setKeyword] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("fund_count");
  const [priceMin, setPriceMin] = useState<string>("");
  const [priceMax, setPriceMax] = useState<string>("");

  const filtered = useMemo(() => {
    if (!sector) return [];
    let arr: SectorStock[] = [...sector.stocks];
    if (keyword.trim()) {
      const kw = keyword.trim().toLowerCase();
      arr = arr.filter(
        (s) => s.code.includes(kw) || (s.name || "").toLowerCase().includes(kw)
      );
    }
    const pMin = priceMin ? parseFloat(priceMin) : null;
    const pMax = priceMax ? parseFloat(priceMax) : null;
    if (pMin !== null && !Number.isNaN(pMin)) {
      arr = arr.filter((s) => (s.price ?? -Infinity) >= pMin);
    }
    if (pMax !== null && !Number.isNaN(pMax)) {
      arr = arr.filter((s) => (s.price ?? Infinity) <= pMax);
    }
    arr.sort((a, b) => {
      const va = (a[sortKey] as number | null | undefined) ?? -Infinity;
      const vb = (b[sortKey] as number | null | undefined) ?? -Infinity;
      return (vb as number) - (va as number);
    });
    return arr;
  }, [sector, keyword, sortKey, priceMin, priceMax]);

  if (!sector) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(15,23,42,0.35)", backdropFilter: "blur(1px)" }}
      onClick={onClose}
    >
      <div
        className="bg-white rounded-md shadow-xl w-[min(960px,92vw)] max-h-[88vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-200">
          <div className="flex items-baseline gap-2">
            <h3 className="text-[14px] font-semibold text-slate-800">
              {sector.industry_name}
            </h3>
            <span className="text-[11px] text-slate-500">
              共 {sector.stocks.length} 只
              {(sector.funded_count ?? 0) > 0 && (
                <span className="text-slate-400">
                  （{sector.funded_count} 只有基金重仓）
                </span>
              )}
              {reportDate && (
                <span className="ml-2">· 持仓报告期 {reportDate}</span>
              )}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* filter bar */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-2 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-1">
            <Search className="w-3 h-3 text-slate-400" />
            <input
              type="text"
              placeholder="代码 / 名称"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              className="px-2 py-0.5 text-[12px] border border-slate-300 rounded w-32 focus:outline-none focus:border-slate-500"
            />
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[11px] text-slate-500">股价</span>
            <input
              type="number"
              placeholder="不限"
              value={priceMin}
              onChange={(e) => setPriceMin(e.target.value)}
              className="w-16 px-1.5 py-0.5 text-[12px] border border-slate-300 rounded tabular"
            />
            <span className="text-slate-400 text-[11px]">~</span>
            <input
              type="number"
              placeholder="不限"
              value={priceMax}
              onChange={(e) => setPriceMax(e.target.value)}
              className="w-16 px-1.5 py-0.5 text-[12px] border border-slate-300 rounded tabular"
            />
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[11px] text-slate-500">排序</span>
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              className="px-1.5 py-0.5 text-[12px] border border-slate-300 rounded bg-white"
            >
              <option value="fund_count">持仓基金数</option>
              <option value="change_pct">涨跌幅</option>
              <option value="price">股价</option>
              <option value="total_market_value">持仓市值</option>
            </select>
          </div>
          <div className="ml-auto text-[11px] text-slate-500">
            匹配 {filtered.length} / {sector.stocks.length} 只
          </div>
        </div>

        {/* table */}
        <div className="flex-1 overflow-auto">
          <table className="w-full text-[12px]">
            <thead className="bg-slate-50 text-slate-500 text-[11px] sticky top-0">
              <tr>
                <th className="text-left px-3 py-1.5 font-normal w-12">#</th>
                <th className="text-left px-3 py-1.5 font-normal">股票</th>
                <th className="text-right px-3 py-1.5 font-normal">现价</th>
                <th className="text-right px-3 py-1.5 font-normal">涨跌幅</th>
                <th className="text-right px-3 py-1.5 font-normal">持仓基金</th>
                <th className="text-right px-3 py-1.5 font-normal">持仓市值</th>
                <th className="text-right px-3 py-1.5 font-normal">总市值(亿)</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center text-slate-400 py-6">
                    无匹配
                  </td>
                </tr>
              )}
              {filtered.map((s, i) => {
                const up = (s.change_pct ?? 0) > 0;
                const down = (s.change_pct ?? 0) < 0;
                return (
                  <tr
                    key={s.code}
                    onClick={() => onStockClick?.(s.code)}
                    className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                  >
                    <td className="px-3 py-1.5 tabular text-slate-400">{i + 1}</td>
                    <td className="px-3 py-1.5">
                      <span className="text-slate-800 font-medium">{s.name || s.code}</span>
                      <span className="text-[10px] text-slate-400 ml-1.5 tabular">{s.code}</span>
                    </td>
                    <td className="px-3 py-1.5 text-right tabular text-slate-700">
                      {fmtPrice(s.price)}
                    </td>
                    <td
                      className={clsx(
                        "px-3 py-1.5 text-right tabular",
                        up ? "text-up" : down ? "text-down" : "text-slate-500"
                      )}
                    >
                      <span className="inline-flex items-center gap-0.5">
                        {up && <ArrowUp className="w-2.5 h-2.5" />}
                        {down && <ArrowDown className="w-2.5 h-2.5" />}
                        {fmtPct(s.change_pct)}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-right tabular text-slate-700">
                      {(s.fund_count ?? 0) > 0 ? (
                        `×${s.fund_count}`
                      ) : (
                        <span className="text-slate-300 text-[10px]">无重仓</span>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular text-slate-700">
                      {fmtMv(s.total_market_value)}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular text-slate-700">
                      {s.market_cap ? s.market_cap.toFixed(1) : "--"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* footer */}
        <div className="border-t border-slate-200 px-4 py-1.5 text-[10px] text-slate-400 flex items-center gap-1">
          提示：点击行可进入股票详情 · Esc 关闭
        </div>
      </div>
    </div>,
    document.body
  );
}
