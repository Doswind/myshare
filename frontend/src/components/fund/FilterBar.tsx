import { useFilterStore } from "@/store/filterStore";
import { useQuery } from "@tanstack/react-query";
import { fetchIndustryNames } from "@/api/stocks";
import { RangeSlider, DoubleRangeSlider } from "@/components/common/RangeSlider";
import { RefreshCw, X } from "lucide-react";
import { useDebounce } from "@/hooks/useDebounce";

export function FilterBar() {
  const {
    minScale, minRet1y, priceMin, priceMax, industry, sortBy, fundedOnly,
    setMinScale, setMinRet1y, setPriceRange, setIndustry, setSortBy, setFundedOnly, reset,
  } = useFilterStore();

  const { data: industries = [] } = useQuery({
    queryKey: ["industries"],
    queryFn: fetchIndustryNames,
    staleTime: 5 * 60_000,
  });

  // debounce 用于滑块
  const dMinScale = useDebounce(minScale, 250);
  const dMinRet1y = useDebounce(minRet1y, 250);
  const dPriceMin = useDebounce(priceMin, 400);
  const dPriceMax = useDebounce(priceMax, 400);

  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 shadow-sm">
      <div className="grid grid-cols-1 sm:flex sm:flex-wrap sm:items-center gap-x-4 gap-y-2">
        <RangeSlider
          label="规模 ≥"
          value={minScale}
          min={1}
          max={500}
          step={1}
          suffix="亿"
          onChange={setMinScale}
        />
        <RangeSlider
          label="1年收益 ≥"
          value={minRet1y}
          min={-30}
          max={100}
          step={1}
          suffix="%"
          onChange={setMinRet1y}
        />
        <DoubleRangeSlider
          label="股价"
          valueMin={priceMin}
          valueMax={priceMax}
          min={0}
          max={2000}
          step={1}
          suffix="元"
          onChange={setPriceRange}
        />
        <div className="flex items-center gap-2 w-full sm:min-w-[140px]">
          <span className="text-[11px] text-slate-500 whitespace-nowrap">行业</span>
          <select
            value={industry ?? ""}
            onChange={(e) => setIndustry(e.target.value || null)}
            className="flex-1 px-1.5 py-0.5 text-[12px] border border-slate-300 rounded bg-white cursor-pointer"
          >
            <option value="">全部</option>
            {industries.map((i) => (
              <option key={i.name} value={i.name}>
                {i.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 w-full sm:min-w-[140px]">
          <span className="text-[11px] text-slate-500 whitespace-nowrap">排序</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="flex-1 px-1.5 py-0.5 text-[12px] border border-slate-300 rounded bg-white cursor-pointer"
          >
            <option value="fund_count">持仓基金数</option>
            <option value="change_pct">涨跌幅</option>
            <option value="total_market_value">持仓市值</option>
          </select>
        </div>
        <label className="flex items-center gap-1.5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={fundedOnly}
            onChange={(e) => setFundedOnly(e.target.checked)}
            className="w-3.5 h-3.5 accent-slate-700"
          />
          <span className="text-[11px] text-slate-600 whitespace-nowrap">仅看重仓股</span>
        </label>
        <button
          onClick={reset}
          className="rounded border border-slate-300 px-2 py-0.5 text-[12px] text-slate-600 hover:bg-slate-100 transition-colors flex items-center gap-1 justify-center sm:justify-start"
        >
          <X className="w-3 h-3" />
          重置
        </button>
      </div>
    </div>
  );
}
