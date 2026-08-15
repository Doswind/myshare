import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { fetchKline, fetchKlineData } from "@/api/kline";
import { KLineChart } from "./KLineChart";
import { KLineToolbar, type KLinePeriod } from "./KLineToolbar";

interface Props {
  code: string;
  /** 股票名称（用于图表顶部标识，可选） */
  stockName?: string;
}

/**
 * 整合组件：toolbar + chart + 数据获取
 * - 周期切换：触发新请求
 * - 刷新：带 refresh=true，后端先补漏抓历史再刷当日实时 bar（结果入库）
 * - 交易时段（工作日 09:30–15:00）自动每 60s 轮询，近实时更新当日 bar
 * - 获取历史行情：调后端接口抓 AKShare 增量数据，抓完自动 refetch chart
 */

/** 是否处于 A 股交易时段（工作日 09:30–15:00；节假日由后端兜底不抓） */
function inTradingWindow(): boolean {
  const now = new Date();
  const day = now.getDay(); // 0=周日, 6=周六
  if (day === 0 || day === 6) return false;
  const hm = now.getHours() * 60 + now.getMinutes();
  return hm >= 9 * 60 + 30 && hm <= 15 * 60;
}

export function KLineTab({ code, stockName }: Props) {
  const [period, setPeriod] = useState<KLinePeriod>("daily");
  const [fetchingHistory, setFetchingHistory] = useState(false);
  const [historyMsg, setHistoryMsg] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["kline", code, period],
    // refresh=true：后端补漏抓历史 + 交易时段刷当日实时 bar（均入库）
    queryFn: () => fetchKline(code, undefined, undefined, period, true),
    enabled: !!code,
    staleTime: 0,
    // 交易时段每 60s 轮询近实时；窗口外不轮询
    refetchInterval: () => (inTradingWindow() ? 60_000 : false),
  });

  function handleRefresh() {
    q.refetch();
  }

  async function handleFetchHistory() {
    if (fetchingHistory) return;
    setFetchingHistory(true);
    setHistoryMsg(null);
    try {
      // 增量抓取（按 tracking.last_trade_date → today；新股票首次自动补 6 年）
      const result = await fetchKlineData(code);
      if (result.ok) {
        setHistoryMsg(
          `已补充 ${result.bars} 根 K 线（最后交易日 ${result.last_trade_date ?? "—"}，耗时 ${result.elapsed_sec}s）`,
        );
        // 抓完立刻刷图（让用户看到新数据）
        q.refetch();
      } else if (result.status === "paused") {
        setHistoryMsg("该股已暂停抓取（连续失败超阈值），请联系管理员复活");
      } else if (result.status === "empty") {
        setHistoryMsg("该股没有可获取的历史数据（可能退市或新上市）");
      } else {
        setHistoryMsg(`抓取失败：${result.status}`);
      }
    } catch (e: any) {
      setHistoryMsg(`请求失败：${e?.message ?? e}`);
    } finally {
      setFetchingHistory(false);
      // 5 秒后自动清除消息（避免长期显示）
      setTimeout(() => setHistoryMsg(null), 5000);
    }
  }

  return (
    <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
      <KLineToolbar
        period={period}
        onPeriodChange={setPeriod}
        dataAsOf={q.data?.data_as_of ?? null}
        onRefresh={handleRefresh}
        refreshing={q.isFetching}
      />
      {historyMsg && (
        <div
          className={clsx(
            "px-3 py-1.5 text-[11px] border-b",
            historyMsg.startsWith("已补充")
              ? "bg-green-50 text-green-700 border-green-200"
              : historyMsg.startsWith("抓取失败") || historyMsg.startsWith("请求失败") || historyMsg.startsWith("已暂停")
                ? "bg-yellow-50 text-yellow-700 border-yellow-200"
                : "bg-slate-50 text-slate-600 border-slate-200",
          )}
        >
          {historyMsg}
        </div>
      )}
      <div className="p-2">
        {q.isLoading ? (
          <div className="text-center text-slate-400 py-12 text-[12px]">K 线加载中…</div>
        ) : q.error ? (
          <div className="text-center text-red-500 py-12 text-[12px]">
            加载失败：{(q.error as Error)?.message}
            <button
              onClick={() => q.refetch()}
              className="ml-2 underline text-blue-500 hover:text-blue-700"
            >
              重试
            </button>
          </div>
        ) : q.data && q.data.bars && q.data.bars.length > 0 ? (
          <KLineChart bars={q.data.bars} stockName={stockName} />
        ) : (
          <div className="text-center text-slate-400 py-12 text-[12px]">
            暂无 K 线数据
            <button
              onClick={handleFetchHistory}
              disabled={fetchingHistory}
              className="ml-2 underline text-blue-500 hover:text-blue-700 disabled:opacity-50"
            >
              {fetchingHistory ? "获取中…" : "获取历史数据"}
            </button>
          </div>
        )}
      </div>
      {q.data?.truncated && (
        <div className="px-3 py-1.5 text-[10px] text-yellow-700 bg-yellow-50 border-t border-yellow-200">
          ⚠ 数据可能未到最新（DB 最后交易日 {q.data.bars[q.data.bars.length - 1]?.日期 ?? "?"}）
        </div>
      )}
    </div>
  );
}