import client from "./client";
import type { CrawlConfig } from "@/types/api";

export const fetchCrawlConfigs = () =>
  client.get<CrawlConfig[]>("/crawl-config").then((r) => r.data);

export const updateCrawlConfig = (
  jobKey: string,
  updates: Partial<CrawlConfig>
) =>
  client
    .post<CrawlConfig>(`/crawl-config/${jobKey}`, updates)
    .then((r) => r.data);

export const bulkUpdateCrawlConfigs = (items: CrawlConfig[]) =>
  client.post<CrawlConfig[]>("/crawl-config/bulk/update", items).then((r) => r.data);

export const resetCrawlConfigs = () =>
  client.post<CrawlConfig[]>("/crawl-config/reset").then((r) => r.data);
