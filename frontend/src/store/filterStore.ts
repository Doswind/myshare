import { create } from "zustand";
import type { FilterDefaults } from "@/types/api";

export interface PersistedFilters {
  minScale: number;
  minRet1y: number;
  priceMin: number | null;
  priceMax: number | null;
  industry: string | null;
  sortBy: "fund_count" | "change_pct" | "total_market_value";
  fundedOnly: boolean;
  selectedBoards: string[];
}

interface FilterState {
  minScale: PersistedFilters["minScale"];
  minRet1y: PersistedFilters["minRet1y"];
  priceMin: PersistedFilters["priceMin"];
  priceMax: PersistedFilters["priceMax"];
  industry: PersistedFilters["industry"];
  sortBy: PersistedFilters["sortBy"];
  fundedOnly: PersistedFilters["fundedOnly"];
  selectedBoards: PersistedFilters["selectedBoards"];
  systemDefaults: PersistedFilters;

  setMinScale: (v: number) => void;
  setMinRet1y: (v: number) => void;
  setPriceRange: (min: number | null, max: number | null) => void;
  setIndustry: (v: string | null) => void;
  setSortBy: (v: FilterState["sortBy"]) => void;
  setFundedOnly: (v: boolean) => void;
  setSelectedBoards: (v: string[] | ((prev: string[]) => string[])) => void;

  setSystemDefaults: (data: FilterDefaults) => void;
  hydratePreference: (data: Partial<PersistedFilters>) => void;
  reset: () => void;
}

const DEFAULTS: PersistedFilters = {
  minScale: 5,
  minRet1y: 5,
  priceMin: null,
  priceMax: null,
  industry: null,
  sortBy: "fund_count",
  fundedOnly: false,
  selectedBoards: [],
};

export const useFilterStore = create<FilterState>((set) => ({
  ...DEFAULTS,
  systemDefaults: DEFAULTS,
  setMinScale: (v) => set({ minScale: v }),
  setMinRet1y: (v) => set({ minRet1y: v }),
  setPriceRange: (min, max) => set({ priceMin: min, priceMax: max }),
  setIndustry: (v) => set({ industry: v }),
  setSortBy: (v) => set({ sortBy: v }),
  setFundedOnly: (v) => set({ fundedOnly: v }),
  setSelectedBoards: (v) =>
    set((state) => ({
      selectedBoards: typeof v === "function" ? v(state.selectedBoards) : v,
    })),
  setSystemDefaults: (data) =>
    set((state) => {
      const systemDefaults: PersistedFilters = {
        minScale: data.min_scale,
        minRet1y: data.min_ret_1y,
        priceMin: data.price_min,
        priceMax: data.price_max,
        industry: data.industry,
        sortBy: state.systemDefaults.sortBy,
        fundedOnly: state.systemDefaults.fundedOnly,
        selectedBoards: [],
      };
      return { systemDefaults };
    }),
  hydratePreference: (data) =>
    set((state) => ({
      minScale: data.minScale ?? state.minScale,
      minRet1y: data.minRet1y ?? state.minRet1y,
      priceMin: data.priceMin !== undefined ? data.priceMin : state.priceMin,
      priceMax: data.priceMax !== undefined ? data.priceMax : state.priceMax,
      industry: data.industry !== undefined ? data.industry : state.industry,
      sortBy: data.sortBy ?? state.sortBy,
      fundedOnly: data.fundedOnly ?? state.fundedOnly,
      selectedBoards: data.selectedBoards ?? state.selectedBoards,
    })),
  reset: () => set((state) => ({ ...state.systemDefaults })),
}));
