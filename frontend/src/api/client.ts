import type {
  CsvImportResult,
  CsvPreviewOut,
  DashboardFilters,
  DashboardOut,
  ScanRunOut,
  StockDetailOut,
  StockOut,
  StockQuoteOut,
  UniverseStatus,
  TradingReport, TradingMarket, TradingAlertOut, RiskInput, RiskSize, PaperPositionOut, SwingOverviewReport,
} from "../types";

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export async function tradingRequest<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return handleResponse<T>(await fetch(`${API_BASE_URL}/trading${path}`, {
    method: body === undefined ? "GET" : "POST", signal,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }));
}

export const fetchTradingReport = (mode: string, group: string, symbols: string, offset: number, signal?: AbortSignal) =>
  tradingRequest<TradingReport>(`/screen${buildQuery({mode, group, symbols, offset, limit: 5})}`, undefined, signal);
export const fetchQualifiedReport = (mode: string, group: string, symbols: string, signal?: AbortSignal) =>
  tradingRequest<TradingReport>(`/screen${buildQuery({mode, group, symbols, qualified: true})}`, undefined, signal);
export const fetchSwingOverview = (group: string, symbols: string, signal?: AbortSignal) =>
  tradingRequest<SwingOverviewReport>(`/screen${buildQuery({mode: "swing", group, symbols, full_universe: true})}`, undefined, signal);
export const fetchTradingMarket = (signal?: AbortSignal) => tradingRequest<TradingMarket>("/market", undefined, signal);
export const fetchTradingAlerts = (signal?: AbortSignal) => tradingRequest<TradingAlertOut[]>("/alerts", undefined, signal);
export const sizePosition = (input: RiskInput, signal?: AbortSignal) => tradingRequest<RiskSize>("/risk/size", input, signal);
export const fetchPaperPositions = (closed: boolean) => tradingRequest<PaperPositionOut[]>(`/positions?closed=${closed}`);

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

function buildQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export async function fetchDashboard(filters: DashboardFilters): Promise<DashboardOut> {
  const res = await fetch(`${API_BASE_URL}/dashboard${buildQuery(filters as Record<string, unknown>)}`);
  return handleResponse<DashboardOut>(res);
}

export async function runScan(): Promise<ScanRunOut> {
  const res = await fetch(`${API_BASE_URL}/scan/run`, { method: "POST" });
  return handleResponse<ScanRunOut>(res);
}

export async function fetchStocks(): Promise<StockOut[]> {
  const res = await fetch(`${API_BASE_URL}/stocks`);
  return handleResponse<StockOut[]>(res);
}

export async function fetchUniverseStatus(): Promise<UniverseStatus> {
  return handleResponse<UniverseStatus>(await fetch(`${API_BASE_URL}/stocks/universe/status`));
}

export async function refreshUniverse(): Promise<UniverseStatus> {
  return handleResponse<UniverseStatus>(await fetch(`${API_BASE_URL}/stocks/universe/refresh`, { method: "POST" }));
}

export async function addStock(symbol: string, companyName = "", sector = ""): Promise<StockOut> {
  const res = await fetch(`${API_BASE_URL}/stocks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, company_name: companyName, sector }),
  });
  return handleResponse<StockOut>(res);
}

export async function removeStock(symbol: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/stocks/${encodeURIComponent(symbol)}`, { method: "DELETE" });
  await handleResponse(res);
}

export async function fetchStockDetail(symbol: string, signal?: AbortSignal): Promise<StockDetailOut> {
  const res = await fetch(`${API_BASE_URL}/stocks/${encodeURIComponent(symbol)}/detail`, { signal });
  return handleResponse<StockDetailOut>(res);
}

export async function fetchStockQuote(symbol: string, signal?: AbortSignal): Promise<StockQuoteOut> {
  const res = await fetch(`${API_BASE_URL}/stocks/${encodeURIComponent(symbol)}/quote`, { signal });
  return handleResponse<StockQuoteOut>(res);
}

export async function previewCsv(file: File): Promise<CsvPreviewOut> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/csv/preview`, { method: "POST", body: formData });
  return handleResponse<CsvPreviewOut>(res);
}

export async function suggestMapping(columns: string[]): Promise<Record<string, string>> {
  const res = await fetch(`${API_BASE_URL}/csv/suggest-mapping${buildQuery({ columns: columns.join(",") })}`);
  return handleResponse<Record<string, string>>(res);
}

export async function importCsv(
  rows: Record<string, string>[],
  columnMapping: Record<string, string>,
  mode: "add" | "replace"
): Promise<CsvImportResult> {
  const res = await fetch(`${API_BASE_URL}/csv/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rows, column_mapping: columnMapping, mode }),
  });
  return handleResponse<CsvImportResult>(res);
}
