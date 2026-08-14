import client from "./client";
import type { Stock, StockQuote, JobLog, ScheduledJob } from "@/types/api";

export const fetchStock = (code: string) =>
  client.get<Stock>(`/stocks/${code}`).then((r) => r.data);

export const fetchStockQuote = (code: string) =>
  client.get<StockQuote>(`/stocks/${code}/quote`).then((r) => r.data);

export const fetchFundsHoldingStock = (code: string) =>
  client.get(`/stocks/${code}/funds`).then((r) => r.data);

export const fetchSectors = () =>
  client.get("/sectors").then((r) => r.data);

export const fetchIndustryNames = () =>
  client.get<{ name: string }[]>("/sectors/by-industry").then((r) => r.data);

export const fetchJobs = () =>
  client.get<JobLog[]>("/jobs").then((r) => r.data);

export const fetchScheduledJobs = () =>
  client.get<ScheduledJob[]>("/jobs/scheduled").then((r) => r.data);

/** 当前正在运行的任务 + 冷却期（in_memory_locks / cooldowns） */
export const fetchRunningJobs = () =>
  client.get<{
    in_memory_locks: string[];
    cooldowns: Record<string, number>;
    db_running_recent: JobLog[];
  }>("/jobs/running").then((r) => r.data);

export const triggerFundRefresh = () =>
  client.post("/jobs/funds/refresh").then((r) => r.data);

export const triggerHoldingsRefresh = () =>
  client.post("/jobs/holdings/refresh").then((r) => r.data);

export const triggerQuoteRefresh = (only_holdings = true) =>
  client.post("/jobs/quotes/refresh", null, { params: { only_holdings } }).then((r) => r.data);

export const triggerSectorRefresh = () =>
  client.post("/jobs/sectors/refresh").then((r) => r.data);

/** 清理卡住的 running 任务（>stuckMinutes 分钟） */
export const cleanupStuckJobs = (stuckMinutes = 30) =>
  client
    .post<{ cleaned_count: number; cleaned: { log_id: number; job_id: string }[] }>(
      "/jobs/cleanup-stuck",
      null,
      { params: { stuck_minutes: stuckMinutes } }
    )
    .then((r) => r.data);
