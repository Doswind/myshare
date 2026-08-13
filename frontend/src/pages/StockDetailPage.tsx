import { useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchStock, fetchStockQuote, fetchFundsHoldingStock } from "@/api/stocks";
import {
  ArrowLeft,
  ExternalLink,
  BarChart3,
  FileText,
  Briefcase,
  LineChart,
  Building2,
  Coins,
} from "lucide-react";
import clsx from "clsx";

type TabKey = "info" | "kline" | "funds";

export default function StockDetailPage() {
  const params = useParams();
  const stockCode = params.code || "";
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>("info");

  const { data: stock } = useQuery({
    queryKey: ["stock", stockCode],
    queryFn: () => fetchStock(stockCode),
    enabled: !!stockCode,
  });
  const { data: quote } = useQuery({
    queryKey: ["stock-quote", stockCode],
    queryFn: () => fetchStockQuote(stockCode),
    enabled: !!stockCode,
  });
  const { data: holdingFunds = [] } = useQuery({
    queryKey: ["stock-funds", stockCode],
    queryFn: () => fetchFundsHoldingStock(stockCode),
    enabled: !!stockCode,
  });

  // 沪市 1 / 深市 0 -> sh / sz
  const market = stock?.market === 1 ? "sh" : "sz";
  const marketCN = stock?.market === 1 ? "沪" : "深";
  const marketPrefix = stock?.market === 1 ? "SH" : "SZ";
  const secid = stock?.secid || `${stock?.market ?? 0}.${stockCode}`;

  // 常用外链
  const links = useMemo(
    () => [
      {
        label: "东财行情",
        icon: LineChart,
        url: `https://quote.eastmoney.com/${market}${stockCode}.html`,
        desc: "实时行情 + K线 + 资金流向",
      },
      {
        label: "东财 F10",
        icon: Building2,
        url: `https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/Index?type=web&code=${marketPrefix}${stockCode}`,
        desc: "公司简况 / 主营 / 股东 / 管理层",
      },
      {
        label: "财务数据",
        icon: Coins,
        url: `https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=${marketPrefix}${stockCode}`,
        desc: "三大表 / 杜邦 / 估值",
      },
      {
        label: "雪球",
        icon: FileText,
        url: `https://xueqiu.com/S/${marketPrefix}${stockCode}`,
        desc: "讨论 / 研报 / 公告",
      },
    ],
    [market, marketPrefix, stockCode]
  );

  // 东财行情页（含完整 K线 / 分时 / 资金流向），iframe 嵌入用
  const klineUrl = `https://quote.eastmoney.com/${market}${stockCode}.html`;

  return (
    <div className="space-y-3">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-[12px] text-slate-500 hover:text-slate-800"
      >
        <ArrowLeft className="w-3 h-3" /> 返回
      </button>

      {/* 头部信息 */}
      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-[15px] font-semibold text-slate-800">
              {stock?.name ?? stockCode}
            </h2>
            <div className="text-[11px] text-slate-500 mt-0.5">
              {stockCode} · {stock?.industry_name ?? "未分类"} · {marketCN}
            </div>
          </div>
          {quote && (
            <div className="text-right">
              <div className="text-[20px] font-semibold text-slate-800 tabular">
                {quote.price?.toFixed(2)}
              </div>
              <div
                className={`text-[12px] tabular ${
                  (quote.change_pct ?? 0) >= 0 ? "text-up" : "text-down"
                }`}
              >
                {(quote.change_pct ?? 0) >= 0 ? "+" : ""}
                {quote.change_pct?.toFixed(2)}% ·{" "}
                {(quote.change_amt ?? 0) >= 0 ? "+" : ""}
                {quote.change_amt?.toFixed(2)}
              </div>
            </div>
          )}
        </div>
        {quote && (
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 mt-3 pt-3 border-t border-slate-100 text-[11px]">
            <div>
              <div className="text-slate-400">最高</div>
              <div className="tabular text-slate-700">{quote.high?.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-slate-400">最低</div>
              <div className="tabular text-slate-700">{quote.low?.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-slate-400">市盈率</div>
              <div className="tabular text-slate-700">
                {quote.pe?.toFixed(2) ?? "--"}
              </div>
            </div>
            <div>
              <div className="text-slate-400">市净率</div>
              <div className="tabular text-slate-700">
                {quote.pb?.toFixed(2) ?? "--"}
              </div>
            </div>
            <div>
              <div className="text-slate-400">总市值</div>
              <div className="tabular text-slate-700">
                {quote.market_cap ? `${quote.market_cap.toFixed(1)}亿` : "--"}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Tab 切换 */}
      <div className="flex items-center gap-1 text-[12px] border-b border-slate-200">
        {(
          [
            { key: "info", label: "基本面", icon: FileText },
            { key: "kline", label: "K线 / 资料", icon: BarChart3 },
            {
              key: "funds",
              label: `重仓基金 (${holdingFunds.length})`,
              icon: Briefcase,
            },
          ] as { key: TabKey; label: string; icon: any }[]
        ).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
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

      {/* Tab: 基本面 */}
      {tab === "info" && (
        <div className="space-y-3">
          {/* 公司简况摘要 + 外部资料入口 */}
          <div className="rounded-md border border-slate-200 bg-white p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[12px] text-slate-700 font-medium">
                公司资料
              </span>
              <span className="text-[10px] text-slate-400">
                详细数据跳转第三方平台查看
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px] mb-3">
              <div>
                <span className="text-slate-400">代码：</span>
                <span className="text-slate-700 tabular">{stockCode}</span>
              </div>
              <div>
                <span className="text-slate-400">市场：</span>
                <span className="text-slate-700">{marketCN}市</span>
              </div>
              <div>
                <span className="text-slate-400">行业：</span>
                <span className="text-slate-700">
                  {stock?.industry_name ?? "--"}
                </span>
              </div>
              <div>
                <span className="text-slate-400">内部代码：</span>
                <span className="text-slate-700 tabular">{secid}</span>
              </div>
              <div className="col-span-2">
                <span className="text-slate-400">概念板块：</span>
                <span className="text-slate-700">
                  {stock?.concept_codes?.length
                    ? stock.concept_codes.join("、")
                    : "--"}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-3 border-t border-slate-100">
              {links.map((l) => (
                <a
                  key={l.label}
                  href={l.url}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex flex-col gap-0.5 rounded border border-slate-200 hover:border-blue-400 hover:bg-blue-50/40 transition-colors px-2.5 py-2"
                >
                  <div className="flex items-center gap-1 text-[12px] text-slate-700 group-hover:text-blue-600">
                    <l.icon className="w-3 h-3" />
                    <span className="font-medium">{l.label}</span>
                    <ExternalLink className="w-2.5 h-2.5 ml-auto text-slate-400 group-hover:text-blue-500" />
                  </div>
                  <div className="text-[10px] text-slate-400 leading-tight">
                    {l.desc}
                  </div>
                </a>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab: K线 / 资料 */}
      {tab === "kline" && (
        <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
          <div className="px-3 py-2 border-b border-slate-100 text-[12px] text-slate-700 font-medium flex items-center justify-between">
            <span className="flex items-center gap-1">
              <BarChart3 className="w-3 h-3" /> K线图
            </span>
            <div className="flex items-center gap-2 text-[11px]">
              <a
                href={klineUrl}
                target="_blank"
                rel="noreferrer"
                className="text-blue-500 hover:text-blue-700 flex items-center gap-0.5"
              >
                全屏打开 <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
          <iframe
            src={klineUrl}
            className="w-full bg-white h-[420px] sm:h-[560px]"
            title="K线图"
            sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
          />
        </div>
      )}

      {/* Tab: 重仓基金 */}
      {tab === "funds" && (
        <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
          <div className="px-3 py-2 border-b border-slate-100 text-[12px] text-slate-700 font-medium">
            重仓该股的主力基金 {holdingFunds.length} 只
          </div>
          <table className="w-full text-[12px]">
            <thead className="bg-slate-50 text-slate-500 text-[11px]">
              <tr>
                <th className="text-left px-3 py-1.5 font-normal">基金</th>
                <th className="text-left px-3 py-1.5 font-normal">代码</th>
                <th className="text-right px-3 py-1.5 font-normal">规模(亿)</th>
                <th className="text-right px-3 py-1.5 font-normal">近1年</th>
                <th className="text-right px-3 py-1.5 font-normal">占净值</th>
                <th className="text-right px-3 py-1.5 font-normal">市值(万)</th>
              </tr>
            </thead>
            <tbody>
              {holdingFunds.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="text-center text-slate-400 py-6"
                  >
                    暂无数据
                  </td>
                </tr>
              )}
              {holdingFunds.map((h: any) => (
                <tr
                  key={h.fund_code}
                  className="border-t border-slate-100 hover:bg-slate-50"
                >
                  <td className="px-3 py-1.5 text-slate-800">{h.fund_name}</td>
                  <td className="px-3 py-1.5 text-slate-500 tabular">
                    {h.fund_code}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular">
                    {(h.fund_scale_yi ?? 0).toFixed(2)}
                  </td>
                  <td
                    className={`px-3 py-1.5 text-right tabular ${
                      (h.fund_ret_1y ?? 0) >= 0 ? "text-up" : "text-down"
                    }`}
                  >
                    {(h.fund_ret_1y ?? 0).toFixed(2)}%
                  </td>
                  <td className="px-3 py-1.5 text-right tabular text-slate-700">
                    {(h.ratio_net ?? 0).toFixed(2)}%
                  </td>
                  <td className="px-3 py-1.5 text-right tabular text-slate-700">
                    {(h.market_value ?? 0).toFixed(0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
