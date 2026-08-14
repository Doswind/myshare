import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchFunds } from "@/api/funds";
import { useFilterStore } from "@/store/filterStore";
import { useDebounce } from "@/hooks/useDebounce";
import { useNavigate } from "react-router-dom";
import { RangeSlider } from "@/components/common/RangeSlider";
import { Pagination } from "@/components/common/Pagination";

const TYPES = [
  { value: "", label: "全部" },
  { value: "gp", label: "股票型" },
  { value: "hh", label: "混合型" },
  { value: "zs", label: "指数型" },
];

export default function FundListPage() {
  const nav = useNavigate();
  const { minScale, minRet1y, setMinScale, setMinRet1y } = useFilterStore();
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const dMinScale = useDebounce(minScale, 300);
  const dMinRet1y = useDebounce(minRet1y, 300);

  // 筛选条件变化时重置到第一页
  const { data, isLoading } = useQuery({
    queryKey: ["funds", dMinScale, dMinRet1y, type, page, pageSize],
    queryFn: () =>
      fetchFunds({
        min_scale: dMinScale,
        min_ret_1y: dMinRet1y,
        fund_type: type || undefined,
        page,
        page_size: pageSize,
      }),
  });

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-2.5">
      <div className="grid grid-cols-1 sm:flex sm:flex-wrap sm:items-center gap-x-4 gap-y-2 rounded-md border border-slate-200 bg-white px-3 py-2">
        <RangeSlider label="规模 ≥" value={minScale} min={1} max={500} suffix="亿" onChange={(v) => { setMinScale(v); setPage(1); }} />
        <RangeSlider label="1年收益 ≥" value={minRet1y} min={-30} max={100} suffix="%" onChange={(v) => { setMinRet1y(v); setPage(1); }} />
        <div className="flex items-center gap-1.5 w-full sm:w-auto">
          <span className="text-[11px] text-slate-500">类型</span>
          {TYPES.map((t) => (
            <button
              key={t.value}
              onClick={() => { setType(t.value); setPage(1); }}
              className={`px-2 py-0.5 text-[12px] rounded border ${
                type === t.value
                  ? "bg-slate-700 text-white border-slate-700"
                  : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="text-[11px] text-slate-500 px-1 flex items-center justify-between">
        <span>共 {total} 只</span>
        {total > pageSize && (
          <span>第 {page} / {totalPages} 页</span>
        )}
      </div>

      <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
        {/* PC 端表格 */}
        <div className="hidden md:block max-h-[calc(100vh-200px)] overflow-auto">
          <table className="w-full text-[12px]">
            <thead className="bg-slate-50 text-slate-500 text-[11px] sticky top-0 z-10">
              <tr>
                <th className="text-left px-3 py-1.5 font-normal">代码</th>
                <th className="text-left px-3 py-1.5 font-normal">名称</th>
                <th className="text-left px-3 py-1.5 font-normal">类型</th>
                <th className="text-right px-3 py-1.5 font-normal">规模(亿)</th>
                <th className="text-right px-3 py-1.5 font-normal">近1月</th>
                <th className="text-right px-3 py-1.5 font-normal">近1年</th>
                <th className="text-right px-3 py-1.5 font-normal">近3年</th>
                <th className="text-left px-3 py-1.5 font-normal">经理</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={8} className="text-center text-slate-400 py-6">
                    加载中…
                  </td>
                </tr>
              )}
              {!isLoading && (data?.items.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={8} className="text-center text-slate-400 py-6">
                    暂无数据，请先在设置中触发「刷新基金」
                  </td>
                </tr>
              )}
              {data?.items.map((f) => (
                <tr
                  key={f.code}
                  onClick={() => nav(`/funds/${f.code}`)}
                  className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors"
                >
                  <td className="px-3 py-1.5 tabular text-slate-500">{f.code}</td>
                  <td className="px-3 py-1.5 text-slate-800">{f.name}</td>
                  <td className="px-3 py-1.5 text-slate-500">
                    {f.fund_type === "gp" ? "股票" : f.fund_type === "hh" ? "混合" : f.fund_type === "zs" ? "指数" : f.fund_type}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular">{(f.scale_yi ?? 0).toFixed(2)}</td>
                  <td className={`px-3 py-1.5 text-right tabular ${(f.ret_1m ?? 0) >= 0 ? "text-up" : "text-down"}`}>
                    {(f.ret_1m ?? 0).toFixed(2)}%
                  </td>
                  <td className={`px-3 py-1.5 text-right tabular font-medium ${(f.ret_1y ?? 0) >= 0 ? "text-up" : "text-down"}`}>
                    {(f.ret_1y ?? 0).toFixed(2)}%
                  </td>
                  <td className={`px-3 py-1.5 text-right tabular ${(f.ret_3y ?? 0) >= 0 ? "text-up" : "text-down"}`}>
                    {(f.ret_3y ?? 0).toFixed(2)}%
                  </td>
                  <td className="px-3 py-1.5 text-slate-500">{f.manager ?? "--"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 移动端卡片列表 */}
        <div className="md:hidden max-h-[calc(100vh-200px)] overflow-auto divide-y divide-slate-100">
          {isLoading && <div className="text-center text-slate-400 py-6 text-[12px]">加载中…</div>}
          {!isLoading && (data?.items.length ?? 0) === 0 && (
            <div className="text-center text-slate-400 py-6 text-[12px]">
              暂无数据，请先在设置中触发「刷新基金」
            </div>
          )}
          {data?.items.map((f) => (
            <div
              key={f.code}
              onClick={() => nav(`/funds/${f.code}`)}
              className="px-3 py-2 active:bg-slate-50 cursor-pointer"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-baseline gap-1.5 min-w-0">
                  <span className="text-[13px] text-slate-800 font-medium truncate">{f.name}</span>
                  <span className="text-[10px] text-slate-400 tabular shrink-0">{f.code}</span>
                </div>
                <span
                  className={`text-[14px] tabular font-medium shrink-0 ml-2 ${
                    (f.ret_1y ?? 0) >= 0 ? "text-up" : "text-down"
                  }`}
                >
                  {(f.ret_1y ?? 0) >= 0 ? "+" : ""}
                  {(f.ret_1y ?? 0).toFixed(2)}%
                </span>
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-500">
                <span className="flex items-center gap-2">
                  <span className="px-1 rounded border border-slate-200">
                    {f.fund_type === "gp" ? "股票" : f.fund_type === "hh" ? "混合" : f.fund_type === "zs" ? "指数" : "--"}
                  </span>
                  <span>规模 {(f.scale_yi ?? 0).toFixed(1)}亿</span>
                </span>
                <span className="tabular">
                  1月 {(f.ret_1m ?? 0) >= 0 ? "+" : ""}{(f.ret_1m ?? 0).toFixed(2)}% · 3年 {(f.ret_3y ?? 0) >= 0 ? "+" : ""}{(f.ret_3y ?? 0).toFixed(2)}%
                </span>
              </div>
            </div>
          ))}
        </div>
        <Pagination
          page={page}
          totalPages={totalPages}
          total={total}
          pageSize={pageSize}
          onPageChange={setPage}
        />
      </div>
    </div>
  );
}
