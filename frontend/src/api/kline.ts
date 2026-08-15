import client from "./client";
import type { KLinePeriod } from "@/components/stock/KLineToolbar";

export interface KLineBar {
  日期: string;
  开盘?: number | null;
  最高?: number | null;
  最低?: number | null;
  收盘?: number | null;
  成交量?: number | null;
  成交额?: number | null;
  振幅?: number | null;
  涨跌幅?: number | null;
  涨跌额?: number | null;
  换手率?: number | null;
}

export interface KLineResponse {
  code: string;
  adjust: string;
  period: string;
  bars: KLineBar[];
  data_as_of: string | null;
  is_intraday: boolean;
  source: string;
  truncated: boolean;
  paused?: boolean;
}

export interface KLinePoolSummary {
  total: number;
  paused: number;
  never_fetched: number;
  pool_size?: number;
}

/** 拉单只股票的 K 线（默认 6 年 / 默认日 K / 不强制刷当日） */
export const fetchKline = (
  code: string,
  from?: string,
  to?: string,
  period: KLinePeriod = "daily",
  refresh = false,
) => {
  const params: Record<string, string | boolean> = { period };
  if (from) params.from = from;
  if (to) params.to = to;
  if (refresh) params.refresh = true;
  return client
    .get<KLineResponse>(`/stocks/${code}/kline`, { params })
    .then((r) => r.data);
};

/** 全池抓取状态汇总（管理用） */
export const fetchKlineStatus = () =>
  client.get<KLinePoolSummary>("/jobs/kline/status").then((r) => r.data);

export interface FetchKlineResult {
  ok: boolean;
  code: string;
  status: "success" | "failed" | "empty" | "paused";
  bars: number;
  last_trade_date: string | null;
  elapsed_sec: number;
}

/** 触发单只股票 K 线增量抓取（同步返回结果） */
export const fetchKlineData = (code: string) =>
  client
    .post<FetchKlineResult>(`/stocks/${code}/kline/fetch`)
    .then((r) => r.data);