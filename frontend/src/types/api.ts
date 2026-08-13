/** API 类型 */
export interface Fund {
  code: string;
  name: string;
  abbr?: string;
  fund_type?: string;
  nav?: number;
  acc_nav?: number;
  nav_date?: string;
  scale_yi?: number;
  ret_1m?: number;
  ret_3m?: number;
  ret_6m?: number;
  ret_1y?: number;
  ret_3y?: number;
  ret_5y?: number;
  ret_this_year?: number;
  inception_date?: string;
  manager?: string;
  company?: string;
  is_main?: boolean;
  updated_at?: string;
}

export interface FundListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Fund[];
}

export interface Holding {
  fund_code: string;
  stock_code: string;
  stock_name?: string;
  report_date: string;
  shares?: number;
  market_value?: number;
  ratio_net?: number;
  rank?: number;
  source?: string;
}

export interface SectorStock {
  code: string;
  name: string;
  industry_name?: string;
  price?: number;
  change_pct?: number;
  market_cap?: number;
  fund_count: number;
  total_market_value?: number;
  total_ratio?: number;
}

export interface SectorGroup {
  industry_name: string;
  stock_count: number;
  avg_change_pct?: number;
  total_market_value?: number;
  stocks: SectorStock[];
}

export interface SectorGroupedResponse {
  total: number;
  page: number;
  page_size: number;
  sectors: SectorGroup[];
  report_date?: string;
}

export interface Stock {
  code: string;
  name: string;
  market: number;
  secid?: string;
  industry_code?: string;
  industry_name?: string;
  concept_codes?: string[];
  updated_at?: string;
}

export interface StockQuote {
  code: string;
  snapshot_at: string;
  price?: number;
  change_pct?: number;
  change_amt?: number;
  volume?: number;
  turnover?: number;
  turnover_rate?: number;
  pe?: number;
  pb?: number;
  market_cap?: number;
  circ_market_cap?: number;
  high?: number;
  low?: number;
  open?: number;
  pre_close?: number;
}

export interface JobLog {
  id: number;
  job_id: string;
  job_name?: string;
  started_at?: string;
  finished_at?: string;
  status: string;
  items_processed: number;
  error_message?: string;
}

export interface ScheduledJob {
  id: string;
  name: string;
  next_run?: string;
  trigger: string;
}

export interface FilterDefaults {
  min_scale: number;
  min_ret_1y: number;
  price_min: number | null;
  price_max: number | null;
  industry: string | null;
}
