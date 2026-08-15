import client from "./client";
import type { Candidate } from "@/lib/promptBuilder";

/** 榜单单项（进场 / 退场） */
export interface BoardItem {
  code: string;
  name: string;
  industry: string;
  direction: "in" | "out";
  reason: string;
  fund_count: number;
  mv_change_pct_qoq: number | null;
  funds_add: number;
  funds_cut: number;
  funds_new: number;
  funds_exit: number;
  avg_fund_ret_1y: number;
  smart_money_index: number;
  pct_rank_1y: number;
  latest_price: number | null;
}

export interface BoardsResponse {
  in: BoardItem[];
  out: BoardItem[];
  report_dates: string[];
  data_as_of: string | null;
  note: string | null;
}

/** 进场榜 / 退场榜（各 Top 20） */
export const fetchBoards = () =>
  client.get<BoardsResponse>("/screener/candidates").then((r) => r.data);

export const fetchFactors = (code: string) =>
  client.get<Omit<Candidate, "holders">>("/screener/factors/" + code).then((r) => r.data);

export const fetchHolders = (code: string) =>
  client
    .get<{ code: string; items: NonNullable<Candidate["holders"]> }>("/screener/holders/" + code)
    .then((r) => r.data);

export const fetchIndustries = () =>
  client.get<{ items: string[] }>("/screener/industries").then((r) => r.data);
