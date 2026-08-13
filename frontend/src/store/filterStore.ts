import { create } from "zustand";
import type { FilterDefaults } from "@/types/api";

interface FilterState {
  minScale: number;
  minRet1y: number;
  priceMin: number | null;
  priceMax: number | null;
  industry: string | null;
  sortBy: "fund_count" | "change_pct" | "total_market_value";

  setMinScale: (v: number) => void;
  setMinRet1y: (v: number) => void;
  setPriceRange: (min: number | null, max: number | null) => void;
  setIndustry: (v: string | null) => void;
  setSortBy: (v: FilterState["sortBy"]) => void;

  hydrate: (data: FilterDefaults) => void;
  reset: () => void;
}

const DEFAULTS = {
  minScale: 5,
  minRet1y: 5,
  priceMin: null as number | null,
  priceMax: null as number | null,
  industry: null as string | null,
  sortBy: "fund_count" as const,
};

export const useFilterStore = create<FilterState>((set) => ({
  ...DEFAULTS,
  setMinScale: (v) => set({ minScale: v }),
  setMinRet1y: (v) => set({ minRet1y: v }),
  setPriceRange: (min, max) => set({ priceMin: min, priceMax: max }),
  setIndustry: (v) => set({ industry: v }),
  setSortBy: (v) => set({ sortBy: v }),
  hydrate: (data) =>
    set({
      minScale: data.min_scale,
      minRet1y: data.min_ret_1y,
      priceMin: data.price_min,
      priceMax: data.price_max,
      industry: data.industry,
    }),
  reset: () => set(DEFAULTS),
}));
