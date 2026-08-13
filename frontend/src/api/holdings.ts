import client from "./client";
import type { SectorGroupedResponse } from "@/types/api";

export interface BoardOption {
  name: string;
  prefixes: string[];
}

export const fetchHoldingsBySector = (params: {
  min_scale?: number;
  min_ret_1y?: number;
  industry_name?: string;
  price_min?: number;
  price_max?: number;
  boards?: string[]; // 板块过滤（多选）
  sort_by?: string;
  page?: number;
  page_size?: number;
}) =>
  client
    .get<SectorGroupedResponse>("/holdings/by-sector", { params })
    .then((r) => r.data);

export const fetchBoards = () =>
  client
    .get<{ boards: BoardOption[] }>("/holdings/boards")
    .then((r) => r.data.boards);
