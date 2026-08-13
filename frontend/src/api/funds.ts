import client from "./client";
import type { Fund, FundListResponse, FilterDefaults } from "@/types/api";

export const fetchFunds = (params: {
  min_scale?: number;
  min_ret_1y?: number;
  fund_type?: string;
  sort?: string;
  page?: number;
  page_size?: number;
}) => client.get<FundListResponse>("/funds", { params }).then((r) => r.data);

export const fetchFund = (code: string) =>
  client.get<Fund>(`/funds/${code}`).then((r) => r.data);

export const fetchFundHoldings = (code: string, report_date?: string) =>
  client
    .get(`/funds/${code}/holdings`, { params: { report_date } })
    .then((r) => r.data);

export const fetchFilterDefaults = () =>
  client.get<FilterDefaults>("/filters/defaults").then((r) => r.data);

export const updateFilterDefaults = (updates: Partial<FilterDefaults>) =>
  client.post<FilterDefaults>("/filters/defaults", updates).then((r) => r.data);

export const resetFilterDefaults = () =>
  client.post<FilterDefaults>("/filters/reset").then((r) => r.data);
