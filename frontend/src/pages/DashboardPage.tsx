import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { useFilterStore } from "@/store/filterStore";
import type { SectorGroupedResponse } from "@/types/api";
import { fetchHoldingsBySector } from "@/api/holdings";
import { fetchFilterDefaults } from "@/api/funds";
import { FilterBar } from "@/components/fund/FilterBar";
import { SectorBoard } from "@/components/sector/SectorBoard";
import { useEffect, useState } from "react";
import { useDebounce } from "@/hooks/useDebounce";
import { useNavigate } from "react-router-dom";
import { HelpCircle } from "lucide-react";

function formatError(e: unknown): string {
  if (!e) return "未知错误";
  if (typeof e === "string") return e;
  const anyE = e as any;
  // AxiosError-like
  if (anyE.response?.data?.detail) {
    const d = anyE.response.data.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d.length) {
      const first = d[0];
      return `${first.loc?.join(".") || "?"}: ${first.msg}`;
    }
    return JSON.stringify(d);
  }
  if (anyE.message) return anyE.message;
  try {
    return JSON.stringify(e);
  } catch {
    return String(e);
  }
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const {
    minScale, minRet1y, priceMin, priceMax, industry, sortBy, hydrate,
  } = useFilterStore();

  // 初始化：拉一次后端默认
  useEffect(() => {
    fetchFilterDefaults().then(hydrate).catch(() => {});
  }, [hydrate]);

  // debounce 价格
  const dMinScale = useDebounce(minScale, 250);
  const dMinRet1y = useDebounce(minRet1y, 250);
  const dPriceMin = useDebounce(priceMin, 400);
  const dPriceMax = useDebounce(priceMax, 400);
  const dIndustry = useDebounce(industry, 250);

  const params = {
    min_scale: dMinScale,
    min_ret_1y: dMinRet1y,
    industry_name: dIndustry || undefined,
    price_min: dPriceMin ?? undefined,
    price_max: dPriceMax ?? undefined,
    sort_by: sortBy,
    page: 1,
    page_size: 1000,
  };

  const { data, isLoading, isError, error } = useQuery<SectorGroupedResponse>({
    queryKey: ["holdings-by-sector", params],
    queryFn: () => fetchHoldingsBySector(params),
    refetchInterval: 5 * 60_000,
    placeholderData: keepPreviousData,
  });

  return (
    <div className="space-y-2.5">
      <FilterBar />

      {isError && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          加载失败：{formatError(error)}。请确认后端已启动 (uvicorn app.main:app) 并已抓取数据。
        </div>
      )}

      <div className="flex items-center justify-between text-[11px] text-slate-500 px-1">
        <div className="flex items-center gap-1.5">
          <span>共 {data?.total ?? 0} 只股票</span>
          {data?.report_date && (
            <ReportDateTag date={data.report_date} />
          )}
        </div>
        {isLoading && <span>刷新中…</span>}
      </div>

      <SectorBoard
        sectors={data?.sectors ?? []}
        loading={isLoading}
        reportDate={data?.report_date}
        onStockClick={(code) => navigate(`/stocks/${code}`)}
        onSectorClick={(s) => {
          // 行业卡片点击 → 跳到股票详情筛选
          useFilterStore.getState().setIndustry(s.industry_name);
        }}
      />
    </div>
  );
}

function ReportDateTag({ date }: { date: string }) {
  const [open, setOpen] = useState(false);
  // 解析报告期季度
  const m = date.match(/^(\d{4})[-/](\d{1,2})/);
  const quarter = m
    ? (() => {
        const mo = parseInt(m[2], 10);
        if (mo <= 3) return "Q1";
        if (mo <= 6) return "Q2";
        if (mo <= 9) return "Q3";
        return "Q4";
      })()
    : "";
  return (
    <span className="relative inline-flex items-center gap-1">
      <span className="text-slate-400">·</span>
      <span>持仓报告期 {date}{quarter && ` (${quarter})`}</span>
      <button
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="text-slate-400 hover:text-slate-600 outline-none"
        aria-label="什么是报告期"
      >
        <HelpCircle className="w-3 h-3" />
      </button>
      {open && (
        <span className="absolute left-0 top-5 z-30 w-72 rounded border border-slate-200 bg-white shadow-lg px-3 py-2 text-[11px] leading-relaxed text-slate-600 text-left">
          基金只在 <b>季报</b>（3/31、6/30、9/30、12/31）披露前 10 大重仓股，
          两次季报之间持仓数据不会更新。当前显示的是
          <b> 最近一次已披露季报</b> 的快照。
          <br />
          股票现价、涨跌幅、总市值仍为 <b>实时</b> 数据。
        </span>
      )}
    </span>
  );
}
