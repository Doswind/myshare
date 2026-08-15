import client from "./client";
import type { Candidate } from "@/lib/promptBuilder";

interface CandidateListItem {
  code: string;
  name: string;
  industry: string;
  total_score: number;
  score_position: number;
  score_trend: number;
  score_capital: number;
  latest_price: number | null;
  market_cap_wan_yi: number | null;
  fund_count: number;
  pct_rank_1y: number;
}

export interface CandidateListResponse {
  total: number;
  items: CandidateListItem[];
}

export const fetchCandidates = (params?: { industry?: string; min_score?: number }) =>
  client
    .get<CandidateListResponse>("/screener/candidates", { params })
    .then((r) => r.data);

export const fetchFactors = (code: string) =>
  client.get<Omit<Candidate, "holders">>("/screener/factors/" + code).then((r) => r.data);

export const fetchHolders = (code: string) =>
  client
    .get<{ code: string; items: NonNullable<Candidate["holders"]> }>("/screener/holders/" + code)
    .then((r) => r.data);

export const fetchIndustries = () =>
  client.get<{ items: string[] }>("/screener/industries").then((r) => r.data);