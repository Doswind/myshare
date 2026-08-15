import { useQuery } from "@tanstack/react-query";
import { fetchFactors, fetchHolders } from "@/api/screener";
import type { Holder } from "@/lib/promptBuilder";

interface Props {
  code: string;
}

function pct(n: number, digits = 1): string {
  return `${n >= 0 ? "" : "-"}${Math.abs(n).toFixed(digits)}%`;
}
function signed(n: number, digits = 1): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}`;
}
function num(n: number, digits = 1): string {
  return n.toFixed(digits);
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-slate-200 bg-white p-2.5">
      <div className="text-[11px] text-slate-500 font-medium mb-1.5">{title}</div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">{children}</div>
    </div>
  );
}

function Field({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <>
      <div className="text-slate-400">{label}</div>
      <div className={`tabular text-right ${color || "text-slate-700"}`}>{value}</div>
    </>
  );
}

function HoldersTable({ holders }: { holders: Holder[] }) {
  if (!holders.length) {
    return <div className="text-center text-slate-400 py-3 text-[11px]">无重仓基金数据</div>;
  }
  return (
    <table className="w-full text-[11px]">
      <thead className="bg-slate-50 text-slate-500">
        <tr>
          <th className="text-left px-2 py-1 font-normal">基金</th>
          <th className="text-right px-2 py-1 font-normal">规模(亿)</th>
          <th className="text-right px-2 py-1 font-normal">近1年</th>
          <th className="text-right px-2 py-1 font-normal">占净值</th>
          <th className="text-right px-2 py-1 font-normal">市值(万)</th>
        </tr>
      </thead>
      <tbody>
        {holders.map((h) => (
          <tr key={h.fund_code} className="border-t border-slate-100">
            <td className="px-2 py-1 text-slate-700">
              {h.fund_name}
              <span className="text-slate-400 ml-1 text-[10px]">{h.fund_code}</span>
            </td>
            <td className="px-2 py-1 text-right tabular text-slate-700">
              {h.scale_yi.toFixed(0)}
            </td>
            <td
              className={`px-2 py-1 text-right tabular ${
                h.ret_1y >= 0 ? "text-up" : "text-down"
              }`}
            >
              {h.ret_1y.toFixed(1)}%
            </td>
            <td className="px-2 py-1 text-right tabular text-slate-700">
              {h.ratio_net.toFixed(1)}%
            </td>
            <td className="px-2 py-1 text-right tabular text-slate-700">
              {h.market_value_wan.toFixed(0)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function FactorPanel({ code }: Props) {
  const factors = useQuery({
    queryKey: ["screener-factors", code],
    queryFn: () => fetchFactors(code),
  });
  const holders = useQuery({
    queryKey: ["screener-holders", code],
    queryFn: () => fetchHolders(code),
  });

  if (factors.isLoading || holders.isLoading) {
    return <div className="text-[11px] text-slate-400 px-3 py-2">加载因子数据…</div>;
  }
  if (factors.error || holders.error) {
    return (
      <div className="text-[11px] text-red-500 px-3 py-2">
        加载失败：{(factors.error as Error)?.message || (holders.error as Error)?.message}
      </div>
    );
  }
  if (!factors.data) return null;

  const f = factors.data.factors;
  const cap = factors.data.capital;
  const tr = factors.data.trend;

  return (
    <div className="bg-slate-50/60 border-t border-slate-200 px-3 py-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
        <Group title="位置因子（事实标注，非预测）">
          <Field label="近 1 年价格百分位" value={pct(f.pct_rank_1y)} />
          <Field label="近 3 年价格百分位" value={pct(f.pct_rank_3y)} />
          <Field
            label="距近 1 年高点回撤"
            value={signed(f.drawdown_1y) + "%"}
            color={f.drawdown_1y < -20 ? "text-blue-600" : "text-slate-700"}
          />
          <Field label="相对 MA60 z-score" value={num(f.vs_ma60_z, 2)} />
          <Field
            label="RSI(14)"
            value={num(f.rsi_14, 1)}
            color={f.rsi_14 < 30 ? "text-blue-600" : f.rsi_14 > 70 ? "text-red-500" : "text-slate-700"}
          />
          <Field label="布林带位置" value={pct(f.boll_pos)} />
          <Field label="连续下跌天数" value={`${f.consecutive_down} 天`} />
          <Field
            label="20 日均量比"
            value={num(f.volume_ratio_20d, 2)}
            color={f.volume_ratio_20d < 0.7 ? "text-blue-600" : "text-slate-700"}
          />
        </Group>

        <Group title="趋势与动量">
          <Field
            label="MA20 / MA60 / MA250"
            value={`${tr.ma20_dir} / ${tr.ma60_dir} / ${tr.ma250_dir}`}
          />
          <Field
            label="近 20 日收益率"
            value={signed(tr.ret_20d) + "%"}
            color={tr.ret_20d >= 0 ? "text-up" : "text-down"}
          />
          <Field
            label="近 60 日收益率"
            value={signed(tr.ret_60d) + "%"}
            color={tr.ret_60d >= 0 ? "text-up" : "text-down"}
          />
        </Group>

        <Group title="主力资金行为（本系统独占，季度环比）">
          <Field label="持有该股的主力基金数" value={cap.fund_count} />
          <Field label="合计持仓市值" value={`${num(cap.total_mv_yi, 1)} 亿`} />
          <Field
            label="上季度环比加减仓"
            value={
              cap.mv_change_pct_qoq === null || cap.mv_change_pct_qoq === undefined
                ? "新进建仓"
                : signed(cap.mv_change_pct_qoq) + "%"
            }
            color={
              cap.mv_change_pct_qoq === null || cap.mv_change_pct_qoq === undefined
                ? "text-up"
                : cap.mv_change_pct_qoq > 0
                  ? "text-up"
                  : "text-down"
            }
          />
          <Field
            label="加/减/新进/退出（只）"
            value={`${cap.funds_add ?? 0} / ${cap.funds_cut ?? 0} / ${cap.funds_new ?? 0} / ${cap.funds_exit ?? 0}`}
          />
          <Field
            label="持仓基金近1年收益中位数"
            value={pct(cap.avg_fund_ret_1y)}
            color={cap.avg_fund_ret_1y >= 15 ? "text-up" : "text-slate-700"}
          />
          <Field
            label="近1年跑赢比例"
            value={num(cap.smart_money_index, 2)}
            color={cap.smart_money_index >= 0.6 ? "text-up" : "text-slate-700"}
          />
        </Group>
      </div>

      <div className="mt-2.5 rounded border border-slate-200 bg-white overflow-hidden">
        <div className="px-2.5 py-1.5 border-b border-slate-100 text-[11px] text-slate-500 font-medium">
          重仓基金明细（{holders.data?.items.length ?? 0} 只）
        </div>
        <HoldersTable holders={holders.data?.items ?? []} />
      </div>

      <div className="mt-2 text-[10px] text-slate-400">
        数据日期：{factors.data.data_as_of} · 基于真实持仓与 K 线计算，不构成投资建议
      </div>
    </div>
  );
}