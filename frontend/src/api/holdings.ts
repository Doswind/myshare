import client from "./client";
import type { SectorGroupedResponse } from "@/types/api";

export const fetchHoldingsBySector = (params: {
  min_scale?: number;
  min_ret_1y?: number;
  industry_name?: string;
  price_min?: number;
  price_max?: number;
  sort_by?: string;
  page?: number;
  page_size?: number;
}) =>
  client
    .get<SectorGroupedResponse>("/holdings/by-sector", { params })
    .then((r) => r.data);
