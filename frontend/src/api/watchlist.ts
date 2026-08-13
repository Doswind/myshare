import client from "./client";

export interface WatchlistItem {
  code: string;
  name: string;
  note: string;
  sort_order: number;
  created_at: string | null;
  price: number | null;
  change_pct: number | null;
  change_amt: number | null;
  pe: number | null;
  pb: number | null;
  market_cap: number | null;
  quote_at: string | null;
  industry_name: string | null;
  market: number;
  fund_count: number;
  report_date: string | null;
}

export const fetchWatchlist = () =>
  client.get<WatchlistItem[]>("/watchlist").then((r) => r.data);

export const addWatchlist = (code: string, name?: string, note?: string) =>
  client
    .post<WatchlistItem>("/watchlist", { code, name, note: note ?? "" })
    .then((r) => r.data);

export const updateWatchlist = (code: string, body: { note?: string; sort_order?: number }) =>
  client.patch<WatchlistItem>(`/watchlist/${code}`, body).then((r) => r.data);

export const removeWatchlist = (code: string) =>
  client.delete(`/watchlist/${code}`).then((r) => r.data);
