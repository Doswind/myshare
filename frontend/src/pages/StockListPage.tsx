import { useEffect, useMemo, useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useFilterStore } from "@/store/filterStore";
import { useDebounce } from "@/hooks/useDebounce";
import { fetchHoldingsBySector, fetchBoards, type BoardOption } from "@/api/holdings";
import { fetchFilterDefaults } from "@/api/funds";
import { fetchWatchlist, type WatchlistItem } from "@/api/watchlist";
import { FilterBar } from "@/components/fund/FilterBar";
import { WatchlistAddBox, WatchlistRemoveButton } from "@/components/watchlist/WatchlistAddBox";
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Star,
  BarChart3,
  Filter,
  X,
} from "lucide-react";
import clsx from "clsx";

type SortKey =
  | "fund_count"
  | "change_pct"
  | "price"
  | "market_cap"
  | "total_market_value";

type Tab = "sector" | "watchlist";

function fmtMv(v?: number | null) {
  if (v === null || v === undefined) return "--";
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(0)}万`;
  return v.toFixed(0);
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

/** 客户端兜底：按代码前缀识别板块（与后端 classify_board 一致） */
function boardOfCode(code: string): string {
  const c = (code || "").trim();
  if (!c) return "其它";
  if (c.startsWith("600") || c.startsWith("601") || c.startsWith("603") || c.startsWith("605")) return "沪主板";
  if (c.startsWith("688")) return "科创板";
  if (c.startsWith("000") || c.startsWith("001") || c.startsWith("002")) return "深主板";
  if (c.startsWith("300") || c.startsWith("301")) return "创业板";
  if (c.startsWith("8") || c.startsWith("9") || c.startsWith("43") || c.startsWith("83") || c.startsWith("87")) return "北交所";
  return "其它";
}

export default function StockListPage() {
  const nav = useNavigate();
  const {
    minScale, minRet1y, priceMin, priceMax, industry, sortBy, hydrate,
  } = useFilterStore();

  const [tab, setTab] = useState<Tab>("sector");
  const [search, setSearch] = useState("");
  const [localSort, setLocalSort] = useState<SortKey>((sortBy as SortKey) ?? "fund_count");
  const [asc, setAsc] = useState(false);
  const [selectedBoards, setSelectedBoards] = useState<string[]>([]);

  useEffect(() => {
    fetchFilterDefaults().then(hydrate).catch(() => {});
  }, [hydrate]);

  const dMinScale = useDebounce(minScale, 250);
  const dMinRet1y = useDebounce(minRet1y, 250);
  const dPriceMin = useDebounce(priceMin, 400);
  const dPriceMax = useDebounce(priceMax, 400);
  const dIndustry = useDebounce(industry, 250);
  const dSearch = useDebounce(search, 250);

  // 持仓 Tab
  const sectorParams = {
    min_scale: dMinScale,
    min_ret_1y: dMinRet1y,
    industry_name: dIndustry || undefined,
    price_min: dPriceMin ?? undefined,
    price_max: dPriceMax ?? undefined,
    boards: selectedBoards.length ? selectedBoards : undefined,
    sort_by: sortBy,
    page: 1,
    page_size: 500,
  };
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["holdings-by-sector-list", sectorParams],
    queryFn: () => fetchHoldingsBySector(sectorParams),
    refetchInterval: 5 * 60_000,
    placeholderData: keepPreviousData,
    enabled: tab === "sector",
  });

  // 板块列表（一次性获取）
  const { data: boardOptions = [] } = useQuery<BoardOption[]>({
    queryKey: ["boards"],
    queryFn: fetchBoards,
    staleTime: Infinity,
  });

  // 自选 Tab
  const { data: watchlist = [], isLoading: wlLoading } = useQuery({
    queryKey: ["watchlist"],
    queryFn: fetchWatchlist,
    refetchInterval: 60_000,
    enabled: tab === "watchlist",
  });

  // 持仓 Tab - 展平
  const sectorStocks = useMemo(() => {
    const list: any[] = [];
    (data?.sectors ?? []).forEach((s) => {
      s.stocks.forEach((st: any) =>
        list.push({ ...st, industry_name: st.industry_name ?? s.industry_name })
      );
    });
    return list;
  }, [data]);

  // 自选 Tab - 转成统一格式
  const watchlistStocks = useMemo(
    () =>
      watchlist.map((w: WatchlistItem) => ({
        code: w.code,
        name: w.name,
        industry_name: w.industry_name,
        board: (w as any).board ?? boardOfCode(w.code),
        price: w.price,
        change_pct: w.change_pct,
        market_cap: w.market_cap,
        fund_count: w.fund_count,
        total_market_value: 0,
        total_ratio: 0,
        market: w.market,
        note: w.note,
      })),
    [watchlist]
  );

  const sourceArr = tab === "sector" ? sectorStocks : watchlistStocks;
  const totalCount = tab === "sector" ? data?.total ?? 0 : watchlist.length;
  const reportDate = tab === "sector" ? data?.report_date : watchlist[0]?.report_date;
  const loading = tab === "sector" ? isLoading : wlLoading;

  // 客户端搜索 + 排序
  const view = useMemo(() => {
    let arr = sourceArr;
    // 板块过滤（两个 Tab 都生效）
    if (selectedBoards.length) {
      arr = arr.filter((s) => selectedBoards.includes(s.board ?? boardOfCode(s.code)));
    }
    const kw = dSearch.trim();
    if (kw) {
      const k = kw.toLowerCase();
      arr = arr.filter(
        (s) =>
          s.code?.toLowerCase().includes(k) ||
          s.name?.toLowerCase().includes(k) ||
          s.industry_name?.toLowerCase().includes(k) ||
          s.board?.toLowerCase().includes(k)
      );
    }
    const sorted = [...arr].sort((a, b) => {
      const va = a[localSort as keyof typeof a];
      const vb = b[localSort as keyof typeof b];
      const an = typeof va === "number" ? va : -Infinity;
      const bn = typeof vb === "number" ? vb : -Infinity;
      return asc ? an - bn : bn - an;
    });
    return sorted;
  }, [sourceArr, dSearch, localSort, asc]);

  const onSort = (k: SortKey) => {
    if (localSort === k) setAsc((v) => !v);
    else {
      setLocalSort(k);
      setAsc(false);
    }
  };

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (localSort !== k) return <ArrowUpDown className="w-3 h-3 opacity-30" />;
    return asc ? <ArrowUp className="w-3 h-3 text-blue-500" /> : <ArrowDown className="w-3 h-3 text-blue-500" />;
  };

  return (
    <div className="space-y-2.5">
      {/* Tab 切换 */}
      <div className="flex items-center gap-1 text-[12px] border-b border-slate-200">
        {(
          [
            { key: "sector", label: "持仓看板（按行业）", icon: BarChart3 },
            { key: "watchlist", label: `我的自选 (${watchlist.length})`, icon: Star },
          ] as { key: Tab; label: string; icon: any }[]
        ).map((t) => (
          <button
            key={t.key}
            onClick={() => {
              setTab(t.key);
              setSearch("");
              if (t.key === "watchlist") {
                setLocalSort("change_pct");
                setAsc(false);
              } else {
                setLocalSort("fund_count");
                setAsc(false);
              }
            }}
            className={clsx(
              "px-3 py-1.5 flex items-center gap-1 border-b-2 -mb-px transition-colors",
              tab === t.key
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            )}
          >
            <t.icon className="w-3 h-3" />
            {t.label}
          </button>
        ))}
      </div>

      {tab === "sector" && <FilterBar />}

      {tab === "sector" && isError && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          加载失败：{formatErr(error)}
        </div>
      )}

      <div className="rounded-md border border-slate-200 bg-white px-3 py-2 space-y-1.5">
        {tab === "watchlist" && (
          <WatchlistAddBox
            existingCodes={watchlist.map((w) => w.code)}
            onAdded={() => {
              setSearch("");
            }}
          />
        )}
        {/* 板块过滤 chips */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center gap-1 text-[11px] text-slate-500 shrink-0">
            <Filter className="w-3 h-3" /> 板块
          </span>
          {boardOptions.map((b) => {
            const active = selectedBoards.includes(b.name);
            return (
              <button
                key={b.name}
                onClick={() =>
                  setSelectedBoards((prev) =>
                    prev.includes(b.name) ? prev.filter((x) => x !== b.name) : [...prev, b.name]
                  )
                }
                className={clsx(
                  "px-2 py-0.5 rounded-full text-[11px] border transition-colors",
                  active
                    ? "bg-blue-500 text-white border-blue-500"
                    : "bg-white text-slate-600 border-slate-300 hover:border-blue-400 hover:text-blue-600"
                )}
                title={`代码前缀: ${b.prefixes.join(", ")}`}
              >
                {b.name}
              </button>
            );
          })}
          {selectedBoards.length > 0 && (
            <button
              onClick={() => setSelectedBoards([])}
              className="text-[11px] text-slate-400 hover:text-slate-600 inline-flex items-center gap-0.5"
            >
              <X className="w-3 h-3" /> 清除
            </button>
          )}
          <span className="text-[11px] text-slate-500 tabular ml-auto">
            共 {view.length} / {totalCount} 只
            {reportDate && <span className="ml-2 text-slate-400">报告期 {reportDate}</span>}
            {loading && <span className="ml-2 text-slate-400">刷新中…</span>}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={tab === "watchlist" ? "在自选里搜索 代码 / 名称 / 行业 / 板块" : "搜索 代码 / 名称 / 行业 / 板块"}
            className="flex-1 min-w-[180px] px-2 py-0.5 text-[12px] border border-slate-300 rounded bg-white outline-none focus:border-blue-400"
          />
        </div>
      </div>

      <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
        {/* PC 端表格 */}
        <div className="hidden md:block max-h-[calc(100vh-200px)] overflow-auto">
          <table className="w-full text-[12px]">
            <thead className="bg-slate-50 text-slate-500 text-[11px] sticky top-0 z-10">
              <tr>
                <th className="text-left px-3 py-1.5 font-normal whitespace-nowrap">代码</th>
                <th className="text-left px-3 py-1.5 font-normal whitespace-nowrap">名称</th>
                <th className="text-left px-3 py-1.5 font-normal whitespace-nowrap">行业</th>
                <th className="text-left px-3 py-1.5 font-normal whitespace-nowrap">板块</th>
                <th
                  className="text-right px-3 py-1.5 font-normal whitespace-nowrap cursor-pointer hover:text-slate-800"
                  onClick={() => onSort("price")}
                >
                  <span className="inline-flex items-center gap-0.5">价格 <SortIcon k="price" /></span>
                </th>
                <th
                  className="text-right px-3 py-1.5 font-normal whitespace-nowrap cursor-pointer hover:text-slate-800"
                  onClick={() => onSort("change_pct")}
                >
                  <span className="inline-flex items-center gap-0.5">涨跌幅 <SortIcon k="change_pct" /></span>
                </th>
                <th
                  className="text-right px-3 py-1.5 font-normal whitespace-nowrap cursor-pointer hover:text-slate-800"
                  onClick={() => onSort("market_cap")}
                >
                  <span className="inline-flex items-center gap-0.5">总市值 <SortIcon k="market_cap" /></span>
                </th>
                <th
                  className="text-right px-3 py-1.5 font-normal whitespace-nowrap cursor-pointer hover:text-slate-800"
                  onClick={() => onSort("fund_count")}
                >
                  <span className="inline-flex items-center gap-0.5">重仓基金 <SortIcon k="fund_count" /></span>
                </th>
                {tab === "sector" && (
                  <th
                    className="text-right px-3 py-1.5 font-normal whitespace-nowrap cursor-pointer hover:text-slate-800"
                    onClick={() => onSort("total_market_value")}
                  >
                    <span className="inline-flex items-center gap-0.5">总持仓市值 <SortIcon k="total_market_value" /></span>
                  </th>
                )}
                {tab === "watchlist" && (
                  <th className="text-left px-3 py-1.5 font-normal whitespace-nowrap">备注</th>
                )}
                {tab === "watchlist" && (
                  <th className="text-right px-3 py-1.5 font-normal whitespace-nowrap w-10"></th>
                )}
              </tr>
            </thead>
            <tbody>
              {view.length === 0 && !loading && (
                <tr>
                  <td colSpan={tab === "sector" ? 9 : 9} className="text-center text-slate-400 py-6">
                    {tab === "watchlist"
                      ? "暂无自选股，使用上方搜索框添加（支持代码 / 中文名 / 拼音首字母）"
                      : "暂无符合筛选条件的股票"}
                  </td>
                </tr>
              )}
              {view.map((s) => (
                <tr
                  key={s.code}
                  onClick={() => nav(`/stocks/${s.code}`)}
                  className="border-t border-slate-100 hover:bg-blue-50/40 cursor-pointer transition-colors"
                >
                  <td className="px-3 py-1.5 tabular text-slate-500 whitespace-nowrap">{s.code}</td>
                  <td className="px-3 py-1.5 text-slate-800 whitespace-nowrap">
                    {s.name}
                    <span className="ml-1.5 text-[10px] text-slate-400">
                      {s.code?.startsWith("6") || s.code?.startsWith("9") ? "沪" : "深"}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-slate-600 whitespace-nowrap">{s.industry_name ?? "--"}</td>
                  <td className="px-3 py-1.5 text-slate-500 whitespace-nowrap">
                    <span className="inline-flex px-1.5 py-0.5 rounded text-[10px] bg-slate-50 border border-slate-200">
                      {s.board ?? boardOfCode(s.code)}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-right tabular text-slate-700">
                    {s.price != null ? s.price.toFixed(2) : "--"}
                  </td>
                  <td
                    className={clsx(
                      "px-3 py-1.5 text-right tabular",
                      (s.change_pct ?? 0) >= 0 ? "text-up" : "text-down"
                    )}
                  >
                    {s.change_pct != null
                      ? `${s.change_pct >= 0 ? "+" : ""}${s.change_pct.toFixed(2)}%`
                      : "--"}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular text-slate-700">
                    {s.market_cap != null ? `${s.market_cap.toFixed(1)}亿` : "--"}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular">
                    {(s.fund_count ?? 0) > 0 ? (
                      <span className="inline-flex items-center justify-center min-w-[24px] px-1.5 py-0.5 rounded text-[10px] bg-blue-50 text-blue-700 border border-blue-100">
                        {s.fund_count}
                      </span>
                    ) : (
                      <span className="text-[10px] text-slate-300">无重仓</span>
                    )}
                  </td>
                  {tab === "sector" && (
                    <td className="px-3 py-1.5 text-right tabular text-slate-700">
                      {fmtMv(s.total_market_value)}
                    </td>
                  )}
                  {tab === "watchlist" && (
                    <td className="px-3 py-1.5 text-slate-500 text-[11px] truncate max-w-[160px]">
                      {(s as any).note || <span className="text-slate-300">--</span>}
                    </td>
                  )}
                  {tab === "watchlist" && (
                    <td className="px-3 py-1.5 text-right">
                      <WatchlistRemoveButton code={s.code} name={s.name} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 移动端卡片列表 */}
        <div className="md:hidden max-h-[calc(100vh-200px)] overflow-auto divide-y divide-slate-100">
          {view.length === 0 && !loading && (
            <div className="text-center text-slate-400 py-6 text-[12px]">
              {tab === "watchlist"
                ? "暂无自选股，使用上方搜索框添加"
                : "暂无符合筛选条件的股票"}
            </div>
          )}
          {view.map((s) => (
            <div
              key={s.code}
              onClick={() => nav(`/stocks/${s.code}`)}
              className="px-3 py-2 active:bg-blue-50/60 cursor-pointer"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-baseline gap-1.5 min-w-0">
                  <span className="text-[13px] text-slate-800 font-medium truncate">{s.name}</span>
                  <span className="text-[10px] text-slate-400 tabular shrink-0">{s.code}</span>
                </div>
                <div className="text-right shrink-0 ml-2">
                  <div className="text-[14px] text-slate-800 tabular font-medium">
                    {s.price != null ? s.price.toFixed(2) : "--"}
                  </div>
                  <div
                    className={clsx(
                      "text-[11px] tabular",
                      (s.change_pct ?? 0) >= 0 ? "text-up" : "text-down"
                    )}
                  >
                    {s.change_pct != null
                      ? `${s.change_pct >= 0 ? "+" : ""}${s.change_pct.toFixed(2)}%`
                      : "--"}
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-500">
                <span className="truncate">{s.industry_name ?? "--"}</span>
                <span className="flex items-center gap-2 shrink-0 ml-2 tabular">
                  {(s.fund_count ?? 0) > 0 ? (
                    <span className="inline-flex items-center justify-center min-w-[20px] px-1 rounded bg-blue-50 text-blue-700 border border-blue-100">
                      {s.fund_count}只
                    </span>
                  ) : (
                    <span className="text-[10px] text-slate-300">无重仓</span>
                  )}
                  <span>市值 {s.market_cap != null ? `${s.market_cap.toFixed(0)}亿` : "--"}</span>
                  {tab === "watchlist" && (
                    <span onClick={(e) => e.stopPropagation()}>
                      <WatchlistRemoveButton code={s.code} name={s.name} />
                    </span>
                  )}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
