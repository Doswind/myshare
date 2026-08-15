import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchKline } from "@/api/kline";
import { KLineChart } from "./KLineChart";
import { KLineToolbar, type KLinePeriod } from "./KLineToolbar";

interface Props {
  code: string;
  /** 股票名称（用于图表顶部标识，可选） */
  stockName?: string;
}

/**
 * 整合组件：toolbar + chart + 数据获取
 * - 首屏：只读数据库（refresh=false），秒开，不等抓取/游标比对
 * - 展示后异步刷新：后台带 refresh=true 补漏抓历史 + 交易时段刷当日 bar，结果回填缓存
 *   （新股票首次进入也由后台刷新自动补 6 年历史，无需手动按钮）
 * - 交易时段（工作日 09:30–15:00）自动每 60s 后台刷新，近实时更新当日 bar
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
  const qc = useQueryClient();
  const [period, setPeriod] = useState<KLinePeriod>("daily");
  const [refreshing, setRefreshing] = useState(false);

  // 首屏展示查询：只读数据库（refresh=false），保证秒开
  const q = useQuery({
    queryKey: ["kline", code, period],
    queryFn: () => fetchKline(code, undefined, undefined, period, false),
    enabled: !!code,
    staleTime: 30_000,
  });

  // 后台刷新：带 refresh=true（补漏 + 当日实时 bar），成功后回填缓存，不阻塞展示
  const backgroundRefresh = useCallback(async () => {
    if (!code) return;
    setRefreshing(true);
    try {
      const fresh = await fetchKline(code, undefined, undefined, period, true);
      qc.setQueryData(["kline", code, period], fresh);
    } catch {
      // 静默失败：界面继续显示数据库里的数据
    } finally {
      setRefreshing(false);
    }
  }, [code, period, qc]);

  // 首屏数据展示成功后，异步触发一次后台刷新
  useEffect(() => {
    if (!code || !q.isSuccess) return;
    backgroundRefresh();
    // 仅在该 code/period 首次成功时触发一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.isSuccess, code, period]);

  // 交易时段每 60s 后台刷新；窗口外不轮询
  useEffect(() => {
    if (!code || !inTradingWindow()) return;
    const t = setInterval(() => backgroundRefresh(), 60_000);
    return () => clearInterval(t);
  }, [code, backgroundRefresh]);

  function handleRefresh() {
    backgroundRefresh();
  }

  return (
    <div className="rounded-md border border-slate-200 bg-white overflow-hidden">
      <KLineToolbar
        period={period}
        onPeriodChange={setPeriod}
        dataAsOf={q.data?.data_as_of ?? null}
        onRefresh={handleRefresh}
        refreshing={refreshing || q.isFetching}
      />
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
            {q.data?.paused ? (
              <span className="text-yellow-700">
                该股已暂停抓取（连续失败超阈值），请联系管理员复活后再试
              </span>
            ) : refreshing ? (
              "首次加载，正在获取历史数据…"
            ) : (
              "暂无 K 线数据（可能退市或无历史行情）"
            )}
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