import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchFund, fetchFundHoldings } from "@/api/funds";
import { ArrowLeft, Star } from "lucide-react";

function fmtPct(v?: number | null, withSign = true) {
  if (v === null || v === undefined) return "--";
  const sign = withSign && v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

function fmtYi(v?: number | null) {
  if (v === null || v === undefined) return "--";
  return `${v.toFixed(2)} 亿`;
}

function fundTypeText(t?: string | null) {
  if (!t) return "其他";
  return t === "gp" ? "股票型" : t === "hh" ? "混合型" : t === "zs" ? "指数型" : t === "zq" ? "债券型" : t === "qdii" ? "QDII" : t;
}

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

  // 业绩指标（6 个：1m/3m/6m/1y/3y/5y + 成立来）
  const perf = [
    { label: "近1月", v: fund.ret_1m },
    { label: "近3月", v: fund.ret_3m },
    { label: "近6月", v: fund.ret_6m },
    { label: "近1年", v: fund.ret_1y },
    { label: "近3年", v: fund.ret_3y },
    { label: "成立来", v: fund.inception_return ?? fund.ret_5y ?? fund.ret_3y },
  ];

  return (
    <div className="space-y-3">
      <button
        onClick={() => nav(-1)}
        className="flex items-center gap-1 text-[12px] text-slate-500 hover:text-slate-800"
      >
        <ArrowLeft className="w-3 h-3" /> 返回
      </button>

      {/* 净值 + 业绩 区 */}
      <div className="rounded-md border border-slate-200 bg-white p-4">
        <div className="flex items-start justify-between gap-4">
          {/* 单位净值 */}
          <div className="flex-1 min-w-0 border-r border-slate-100 pr-4">
            <div className="flex items-center gap-1.5">
              <span className="text-[12px] text-slate-500">单位净值</span>
              {fund.nav_date && <span className="text-[10px] text-slate-400">({fund.nav_date})</span>}
            </div>
            <div className="flex items-baseline gap-2 mt-1">
              <span className={`text-[28px] font-semibold tabular leading-none ${
                (fund.ret_this_year ?? 0) >= 0 ? "text-up" : "text-down"
              }`}>
                {(fund.nav ?? 0).toFixed(4)}
              </span>
              {fund.ret_this_year !== undefined && fund.ret_this_year !== null && (
                <span className={`text-[12px] tabular ${
                  fund.ret_this_year >= 0 ? "text-up" : "text-down"
                }`}>
                  {fmtPct(fund.ret_this_year)}
                </span>
              )}
            </div>
          </div>
          {/* 累计净值 */}
          <div className="flex-1 min-w-0">
            <div className="text-[12px] text-slate-500">累计净值</div>
            <div className="text-[22px] font-semibold text-slate-800 tabular mt-1">
              {(fund.acc_nav ?? fund.nav ?? 0).toFixed(4)}
            </div>
          </div>
        </div>

        {/* 6 项收益 */}
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mt-4 pt-3 border-t border-slate-100">
          {perf.map((it) => (
            <div key={it.label}>
              <div className="text-[11px] text-slate-400">{it.label}</div>
              <div className={`text-[14px] font-medium tabular mt-0.5 ${
                (it.v ?? 0) >= 0 ? "text-up" : "text-down"
              }`}>
                {it.v !== undefined && it.v !== null ? fmtPct(it.v) : "--"}
              </div>
            </div>
          ))}
        </div>

        {/* 基本信息 */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-y-2.5 gap-x-4 mt-4 pt-3 border-t border-slate-100 text-[12px]">
          <div>
            <span className="text-slate-400">类型：</span>
            <Link to="/funds" className="text-blue-600 hover:underline">
              {fundTypeText(fund.fund_type)}
            </Link>
            {fund.risk_level && (
              <span className="text-slate-400"> | {fund.risk_level}</span>
            )}
          </div>
          <div>
            <span className="text-slate-400">规模：</span>
            <span className="tabular text-slate-700">{fmtYi(fund.scale_yi)}</span>
            {fund.nav_date && (
              <span className="text-slate-400 text-[10px] ml-1">({fund.nav_date})</span>
            )}
          </div>
          <div>
            <span className="text-slate-400">基金经理：</span>
            <span className="text-blue-600">{fund.manager ?? "--"}</span>
          </div>
          <div>
            <span className="text-slate-400">成立日：</span>
            <span className="tabular text-slate-700">{fund.inception_date ?? "--"}</span>
          </div>
          <div>
            <span className="text-slate-400">管理人：</span>
            <span className="text-blue-600">{fund.company ?? "--"}</span>
          </div>
          <div>
            <span className="text-slate-400">基金评级：</span>
            {fund.rating ? (
              <span className="inline-flex items-center gap-0.5">
                {[1, 2, 3, 4, 5].map((n) => (
                  <Star
                    key={n}
                    className={`w-3.5 h-3.5 ${
                      n <= (fund.rating ?? 0)
                        ? "fill-amber-400 text-amber-400"
                        : "text-slate-200"
                    }`}
                  />
                ))}
                <span className="text-[10px] text-slate-400 ml-1">晨星</span>
              </span>
            ) : (
              <span className="text-slate-300">--</span>
            )}
          </div>
        </div>
      </div>

      {/* 重仓股 */}
      <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
        <div className="px-3 py-2 border-b border-slate-100 text-[12px] text-slate-700 font-medium">
          重仓股（前 10 大）
          {holdings[0]?.report_date && <span className="text-[10px] text-slate-400 ml-2">报告期 {holdings[0].report_date}</span>}
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
