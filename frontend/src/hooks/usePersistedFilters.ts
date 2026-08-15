import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { fetchFilterDefaults } from "@/api/funds";
import {
  fetchFilterPreference,
  saveFilterPreference,
} from "@/api/filterPreferences";
import { useFilterStore, type PersistedFilters } from "@/store/filterStore";

const SCOPE = "holdings";

function cacheKey(userId: number) {
  return `filter-preference:${SCOPE}:user:${userId}`;
}

function readCache(userId: number): Partial<PersistedFilters> | null {
  try {
    const raw = localStorage.getItem(cacheKey(userId));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function usePersistedFilters() {
  const { user } = useAuth();
  const [loaded, setLoaded] = useState(false);
  const loadingUserRef = useRef<number | null>(null);
  const {
    minScale,
    minRet1y,
    priceMin,
    priceMax,
    industry,
    sortBy,
    fundedOnly,
    selectedBoards,
    setSystemDefaults,
    hydratePreference,
  } = useFilterStore();

  const preference = useMemo<PersistedFilters>(
    () => ({
      minScale,
      minRet1y,
      priceMin,
      priceMax,
      industry,
      sortBy,
      fundedOnly,
      selectedBoards,
    }),
    [
      minScale,
      minRet1y,
      priceMin,
      priceMax,
      industry,
      sortBy,
      fundedOnly,
      selectedBoards,
    ],
  );

  useEffect(() => {
    if (!user?.id || loadingUserRef.current === user.id) return;
    loadingUserRef.current = user.id;
    setLoaded(false);
    const cached = readCache(user.id);
    if (cached) hydratePreference(cached);

    Promise.all([fetchFilterDefaults(), fetchFilterPreference(SCOPE)])
      .then(([defaults, stored]) => {
        setSystemDefaults(defaults);
        if (stored.filters) {
          hydratePreference(stored.filters);
        } else if (!cached) {
          hydratePreference({
            minScale: defaults.min_scale,
            minRet1y: defaults.min_ret_1y,
            priceMin: defaults.price_min,
            priceMax: defaults.price_max,
            industry: defaults.industry,
          });
        }
      })
      .catch(() => {
        // localStorage 已先恢复；接口失败时继续使用本地状态
      })
      .finally(() => setLoaded(true));
  }, [user?.id, hydratePreference, setSystemDefaults]);

  useEffect(() => {
    if (!user?.id || !loaded) return;
    const timer = window.setTimeout(() => {
      localStorage.setItem(cacheKey(user.id), JSON.stringify(preference));
      saveFilterPreference(SCOPE, preference).catch(() => {
        // 本地缓存仍保留，下次进入页面时继续尝试同步
      });
    }, 700);
    return () => window.clearTimeout(timer);
  }, [user?.id, loaded, preference]);

  return { loaded };
}
