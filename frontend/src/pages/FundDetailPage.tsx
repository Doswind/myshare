import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchFund, fetchFundHoldings } from "@/api/funds";
import { ArrowLeft } from "lucide-react";

export default function FundDetailPage() {
  const { code = "" } = useParams();
  const nav = useNavigate();
  const { data: fund, isLoading } = useQuery({
    queryKey: ["fund", code],
    queryFn: () => fetchFund(code),
    enabled: !!code,
  });
  const { data: holdings = [] } = useQuery({
    queryKey: ["fund-holdings", code],
    queryFn: () => fetchFundHoldings(code),
    enabled: !!code,
  });

  if (isLoading) return <div className="text-center text-slate-400 py-10 text-[12px]">加载中…</div>;
  if (!fund) return <div className="text-center text-slate-400 py-10 text-[12px]">基金不存在</div>;

  return (
    <div className="space-y-3">
      <button
        onClick={() => nav(-1)}
        className="flex items-center gap-1 text-[12px] text-slate-500 hover:text-slate-800"
      >
        <ArrowLeft className="w-3 h-3" /> 返回
      </button>

      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-[15px] font-semibold text-slate-800">{fund.name}</h2>
            <div className="text-[11px] text-slate-500 mt-0.5">
              {fund.code} · {fund.fund_type === "gp" ? "股票型" : fund.fund_type === "hh" ? "混合型" : "其他"} · {fund.company ?? "--"}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[11px] text-slate-500">单位净值</div>
            <div className="text-[18px] font-semibold text-slate-800 tabular">
              {(fund.nav ?? 0).toFixed(4)}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-4 gap-3 mt-3 pt-3 border-t border-slate-100">
          {[
            { label: "近1月", v: fund.ret_1m },
            { label: "近1年", v: fund.ret_1y },
            { label: "近3年", v: fund.ret_3y },
            { label: "近5年", v: fund.ret_5y },
          ].map((it) => (
            <div key={it.label} className="text-center">
              <div className="text-[10px] text-slate-400">{it.label}</div>
              <div className={`text-[13px] font-medium tabular ${(it.v ?? 0) >= 0 ? "text-up" : "text-down"}`}>
                {it.v !== undefined && it.v !== null ? `${it.v >= 0 ? "+" : ""}${it.v.toFixed(2)}%` : "--"}
              </div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-3 mt-2 text-[12px]">
          <div><span className="text-slate-400">规模：</span><span className="tabular text-slate-700">{(fund.scale_yi ?? 0).toFixed(2)} 亿</span></div>
          <div><span className="text-slate-400">经理：</span><span className="text-slate-700">{fund.manager ?? "--"}</span></div>
          <div><span className="text-slate-400">成立：</span><span className="text-slate-700">{fund.inception_date ?? "--"}</span></div>
        </div>
      </div>

      <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
        <div className="px-3 py-2 border-b border-slate-100 text-[12px] text-slate-700 font-medium">
          重仓股（前 10 大）{holdings[0]?.report_date && <span className="text-[10px] text-slate-400 ml-2">报告期 {holdings[0].report_date}</span>}
        </div>
        <table className="w-full text-[12px]">
          <thead className="bg-slate-50 text-slate-500 text-[11px]">
            <tr>
              <th className="text-left px-3 py-1.5 font-normal w-12">#</th>
              <th className="text-left px-3 py-1.5 font-normal">股票</th>
              <th className="text-right px-3 py-1.5 font-normal">持股(万)</th>
              <th className="text-right px-3 py-1.5 font-normal">市值(万)</th>
              <th className="text-right px-3 py-1.5 font-normal">占净值</th>
            </tr>
          </thead>
          <tbody>
            {holdings.length === 0 && (
              <tr>
                <td colSpan={5} className="text-center text-slate-400 py-6">
                  暂无持仓数据
                </td>
              </tr>
            )}
            {holdings.map((h: typeof holdings[number]) => (
              <tr key={h.stock_code} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-3 py-1.5 tabular text-slate-400">{h.rank ?? "--"}</td>
                <td className="px-3 py-1.5">
                  <Link to={`/stocks/${h.stock_code}`} className="text-slate-800 hover:text-slate-600">
                    {h.stock_name ?? h.stock_code}
                    <span className="text-[10px] text-slate-400 ml-1.5 tabular">{h.stock_code}</span>
                  </Link>
                </td>
                <td className="px-3 py-1.5 text-right tabular text-slate-700">{(h.shares ?? 0).toFixed(2)}</td>
                <td className="px-3 py-1.5 text-right tabular text-slate-700">{(h.market_value ?? 0).toFixed(0)}</td>
                <td className="px-3 py-1.5 text-right tabular text-slate-700">{(h.ratio_net ?? 0).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
