import client from "./client";
import type { PersistedFilters } from "@/store/filterStore";

export interface FilterPreferenceResponse {
  scope: string;
  filters: Partial<PersistedFilters> | null;
  updated_at?: string;
}

export const fetchFilterPreference = (scope: string) =>
  client.get<FilterPreferenceResponse>(`/filter-preferences/${scope}`).then((r) => r.data);

export const saveFilterPreference = (scope: string, filters: PersistedFilters) =>
  client.put<FilterPreferenceResponse>(`/filter-preferences/${scope}`, filters).then((r) => r.data);

export const resetFilterPreference = (scope: string) =>
  client.delete<{ scope: string; status: string }>(`/filter-preferences/${scope}`).then((r) => r.data);
