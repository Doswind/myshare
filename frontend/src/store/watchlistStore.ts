import { create } from "zustand";

interface WatchlistState {
  codes: string[];
  hasHydrated: boolean;
  setCodes: (codes: string[]) => void;
  hydrate: (codes: string[]) => void;
  contains: (code: string) => boolean;
  toggle: (code: string) => void;
  add: (code: string) => void;
  remove: (code: string) => void;
  reset: () => void;
}

export const useWatchlistStore = create<WatchlistState>((set, get) => ({
  codes: [],
  hasHydrated: false,
  setCodes: (codes) => set({ codes, hasHydrated: true }),
  hydrate: (codes) => set({ codes, hasHydrated: true }),
  contains: (code) => get().codes.includes(code),
  toggle: (code) => {
    const cur = get().codes;
    if (cur.includes(code)) set({ codes: cur.filter((c) => c !== code) });
    else set({ codes: [code, ...cur] });
  },
  add: (code) => {
    const cur = get().codes;
    if (!cur.includes(code)) set({ codes: [code, ...cur] });
  },
  remove: (code) => set({ codes: get().codes.filter((c) => c !== code) }),
  reset: () => set({ codes: [], hasHydrated: false }),
}));
