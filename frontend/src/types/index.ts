// Shared API types mirroring the backend Pydantic schemas.

export interface ScanResultOut {
  symbol: string;
  company_name: string;
  sector: string;

  data_available: boolean;
  error_message: string;

  price: number;
  daily_change_pct: number;
  ema20: number;
  ema50: number;
  rsi14: number;
  macd: number;
  macd_signal: number;
  macd_hist: number;
  volume: number;
  avg_volume20: number;
  atr14: number;
  high_52w: number;
  distance_from_high_pct: number;
  recent_support: number;
  recent_resistance: number;

  technical_score: number;
  news_score: number;
  market_score: number;
  total_score: number;
  status_label: string;

  setup_type: "breakout" | "pullback" | "none";
  entry: number | null;
  stop_loss: number | null;
  target1: number | null;
  target2: number | null;
  risk_reward: number | null;

  reasons: string[];
  warnings: string[];
  news_sentiment: string;

  data_source: string;
  data_timestamp: string;
}

export interface MarketContextOut {
  nifty50_value: number;
  nifty50_change_pct: number;
  nifty500_value: number;
  nifty500_change_pct: number;
  trend: "bullish" | "neutral" | "bearish";
  source: string;
  fetched_at: string;
  is_market_open: boolean;
}

export interface ScanRunOut {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  stocks_scanned: number;
  stocks_failed: number;
  trigger: string;
}

export interface DashboardOut {
  last_scan: ScanRunOut | null;
  market: MarketContextOut;
  candidates: ScanResultOut[];
}

export interface StockOut {
  id: number;
  symbol: string;
  company_name: string;
  sector: string;
  source: string;
  is_active: boolean;
}

export interface UniverseStatus {
  source: string;
  source_url: string;
  last_synced_at: string | null;
  instrument_count: number;
  error: string | null;
  is_stale: boolean;
  refresh_interval_seconds: number;
}

export interface NewsItemOut {
  headline: string;
  source: string;
  url: string;
  published_at: string;
  sentiment: string;
  provider: string;
}

export interface CandleOut {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema20?: number | null;
  ema50?: number | null;
  rsi14?: number | null;
  macd?: number | null;
  macd_signal?: number | null;
  macd_hist?: number | null;
}

export interface StockDetailOut {
  stock: StockOut;
  latest_result: ScanResultOut | null;
  news: NewsItemOut[];
  candles: CandleOut[];
  daily_analysis: DailyAnalysisOut;
  data_source: string;
}

export interface TrendPointOut {
  date: string;
  value: number;
}

export interface DailyAnalysisOut {
  trend: "bullish" | "bearish" | "sideways" | "unavailable";
  signal: "BUY" | "SELL" | "WAIT";
  as_of: string | null;
  reason: string;
  pivots: (TrendPointOut & { kind: "high" | "low"; label: string })[];
  support_line: TrendPointOut[];
  resistance_line: TrendPointOut[];
  support: number | null;
  resistance: number | null;
  volume_ratio: number | null;
  entry: number | null;
  stop_loss: number | null;
  target: number | null;
  risk_reward: number | null;
}

export interface StockQuoteOut {
  symbol: string;
  price: number | null;
  change_pct: number | null;
  source: string;
  is_delayed: boolean;
  timestamp: string | null;
  fetched_at: string | null;
  age_seconds: number | null;
  is_stale: boolean;
  market_open: boolean;
  refresh_seconds: number;
  error: string | null;
}

export interface CsvPreviewOut {
  columns: string[];
  rows: Record<string, string>[];
  row_count: number;
}

export interface CsvImportResult {
  imported: number;
  skipped: number;
  mode: string;
  total_universe: number;
}

export interface DashboardFilters {
  min_score?: number;
  rsi_min?: number;
  rsi_max?: number;
  ema_bullish?: boolean;
  macd_bullish?: boolean;
  volume_breakout?: boolean;
  near_52w_high?: boolean;
  setup?: "breakout" | "pullback" | "";
  sector?: string;
}

export interface AnalysisCandle {
  timestamp: string;
  open: number; high: number; low: number; close: number; volume: number;
  ema20: number | null; ema50: number | null; ema200: number | null;
}

export interface AnalysisPivot {
  timestamp: string; value: number; label: string; kind: "high" | "low";
}

export interface TimeframeEvidence {
  trend_strength?: string; break_of_structure?: string; change_of_character?: string; liquidity_sweep?: string;
  false_breakout?: boolean; false_breakdown?: boolean; breakout_retest?: boolean; breakdown_retest?: boolean;
  demand_zone?: (number | null)[]; supply_zone?: (number | null)[];
  timeframe: string; available: boolean; timestamp: string | null; stale: boolean;
  trend: string; trendline: string; structure: string; reason: string;
  pattern?: WMPattern | null;
  close?: number; support?: number; resistance?: number; breakout_level?: number;
  ema9?: number | null; ema20?: number | null; ema50?: number | null; ema200?: number | null;
  rsi?: number | null; macd?: number | null; macd_signal?: number | null; atr?: number | null;
  vwap?: number | null; volume?: number | null; relative_volume?: number | null;
  volume_status?: string; price_action?: string; gap_percent?: number | null;
  breakout?: boolean; breakdown?: boolean; pullback?: boolean; ema_status?: string;
  pivots: AnalysisPivot[]; support_line: AnalysisPivot[]; resistance_line: AnalysisPivot[];
  candles?: AnalysisCandle[];
}

export interface WMPattern {
  pattern: "W" | "M"; stage: string; score: number; quality: "STRONG PATTERN" | "VALID PATTERN" | "WATCH" | null;
  neckline: number | null; first_point: number | null; second_point: number | null;
  first_timestamp: string; second_timestamp: string;
  volume_confirmed: boolean; retest_confirmed: boolean; holds: boolean;
}

export interface TradingRow {
  grade?: string; direction?: "BUY" | "SELL"; setup?: string; bucket?: "BUY" | "SELL" | "WATCH";
  market_trend?: string; qualification_reasons?: string[]; invalidation_reason?: string | null;
  rank: number; symbol: string; company_name: string; sector: string; cmp: number | null;
  timestamp: string | null; signal_timestamp: string | null; data_label: string; signal_label: string;
  live: boolean; liquid: boolean; average_turnover: number; average_volume: number; spread_percent: number | null;
  timeframes: Record<string, TimeframeEvidence>; sector_trend: string; relative_strength_nifty: number | null;
  trend: string; trendline: string; support: number | null; resistance: number | null; breakout_level: number | null;
  entry_zone: number[] | null; stop_loss: number | null; target1: number | null; target2: number | null;
  risk_reward: number | null; volume_status: string; rsi: number | null; macd: number | null; ema_status: string;
  vwap: number | null; volume: number | null; relative_volume: number | null; score: number;
  score_breakdown: {component: string; points: number; maximum: number; reason: string}[];
  missing_confirmations: string[]; invalidation: number | null; risk_level: string; status: string; categories: string[]; reason: string;
  previous_day_high: number | null; previous_day_low: number | null; previous_day_close: number | null;
  today_open: number | null; today_high: number | null; today_low: number | null;
  opening_range_high: number | null; opening_range_low: number | null; opening_range_status: string;
}

export interface TradingMarket {
  indices: {name: string; symbol: string; daily: TimeframeEvidence; hourly: TimeframeEvidence; value: number | null; timestamp: string | null}[];
  status: string; breadth: number | null; breadth_status: string; source: string;
  data_label: string; realtime_available: boolean; market_open: boolean; refresh_seconds: number;
}

export interface TradingReport {
  processed?: number; scan_total?: number; eligible?: number; excluded?: number; stage?: string; coverage?: string;
  rows: TradingRow[]; market: TradingMarket | null; source: string; realtime_available: boolean;
  refresh_seconds: number; scan_timestamp: string | null; group: string; total: number; offset: number;
  analyzed: number; index_verified_at: string | null; error: string | null; refreshing: boolean;
  status: string; alert_status: string;
}

export interface TradingAlertOut {
  id: number; symbol: string; event: string; timestamp: string; price: number;
  details: {status: string; reason: string; entry_zone: number[] | null; stop_loss: number | null;
    target1: number | null; target2: number | null; risk_reward: number | null; vwap: number | null; relative_volume: number | null};
}

export interface SwingOverviewRow {
  symbol: string; company_name: string; group: "BULLISH" | "BEARISH" | "NEUTRAL" | "EXCLUDED";
  setup: string; close: number | null; timestamp: string | null; stale: boolean; liquid: boolean;
  daily_trend: string; weekly_trend: string; weekly_stale: boolean;
  support: SwingLevel; resistance: SwingLevel;
  rsi: number | null; relative_volume: number | null; average_turnover: number | null;
  reason: string; data_label: string; signal_label: string;
}

export interface SwingLevel {
  level: number | null; touches: number; distance_percent: number | null; strong: boolean;
}

export interface SwingOverviewReport extends TradingReport {
  overview_rows: SwingOverviewRow[]; processed: number; scan_total: number; stage: string;
}

export interface RiskInput {
  capital: number; risk_percent: number; allocation: number; entry: number; stop_loss: number; target1: number; side: "BUY" | "SELL";
}

export interface RiskSize {
  capital: number; risk_percent: number; risk_amount: number; quantity: number; capital_required: number;
  maximum_loss: number; potential_profit: number | null; risk_reward: number | null;
  available_capital: number; remaining_portfolio_risk: number; warning: string;
}

export interface PaperPositionOut {
  id: number; symbol: string; side: "BUY" | "SELL"; style: "SWING" | "INTRADAY"; quantity: number;
  entry: number; stop_loss: number; target1: number; target2: number | null; opened_at: string;
  closed_at: string | null; exit_price: number | null; realized_pnl: number | null; exit_reason: string;
}
