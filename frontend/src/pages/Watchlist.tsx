import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { addStock, fetchStocks, fetchUniverseStatus, refreshUniverse, removeStock } from "../api/client";
import type { StockOut, UniverseStatus } from "../types";

export default function Watchlist() {
  const [stocks, setStocks] = useState<StockOut[]>([]);
  const [symbol, setSymbol] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [sector, setSector] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<UniverseStatus | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const filtered = stocks.filter((stock) => `${stock.symbol} ${stock.company_name}`.toLowerCase().includes(search.trim().toLowerCase()));
  const pageCount = Math.max(1, Math.ceil(filtered.length / 50));
  const currentPage = Math.min(page, pageCount - 1);
  const visibleStocks = filtered.slice(currentPage * 50, (currentPage + 1) * 50);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setStocks(await fetchStocks());
      setStatus(await fetchUniverseStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSync() {
    setSyncing(true);
    setError(null);
    try {
      setStatus(await refreshUniverse());
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Online stock sync failed");
    } finally {
      setSyncing(false);
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!symbol.trim()) return;
    try {
      await addStock(symbol.trim().toUpperCase(), companyName.trim(), sector.trim());
      setSymbol("");
      setCompanyName("");
      setSector("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add stock");
    }
  }

  async function handleRemove(sym: string) {
    try {
      await removeStock(sym);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove stock");
    }
  }

  return (
    <div className="watchlist-page">
      <div className="quote-heading">
        <h1>NSE Stocks</h1>
        <button className="icon-button" type="button" title="Sync online NSE catalogue (limited to once per 5 minutes)"
          aria-label="Sync online NSE catalogue" disabled={syncing || loading} onClick={handleSync}>
          <RefreshCw size={18} className={syncing ? "sync-spinning" : ""} />
        </button>
      </div>
      <p className="subtitle">Source: Upstox public NSE catalogue (JSON) / Daily instrument list</p>
      <p className="subtitle">Last synced: {status?.last_synced_at ? new Date(status.last_synced_at).toLocaleString() : "Not yet synchronized"}</p>
      {error && <div className="error-banner">{error}</div>}
      {(status?.error || status?.is_stale) && <div className="quote-warning" role="status">
        {status.error || "Online stock catalogue is stale."}
      </div>}

      <section className="universe-section">
        <h2>Add a stock</h2>
        <form className="add-stock-form" onSubmit={handleAdd}>
          <input placeholder="Symbol (e.g. RELIANCE)" value={symbol} onChange={(e) => setSymbol(e.target.value)} required />
          <input placeholder="Company name (optional)" value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
          <input placeholder="Sector (optional)" value={sector} onChange={(e) => setSector(e.target.value)} />
          <button className="primary-button" type="submit">
            Add
          </button>
        </form>
      </section>

      <section className="universe-section">
        <h2>Current universe ({stocks.length})</h2>
        <div className="universe-toolbar">
          <input type="search" aria-label="Search stocks" placeholder="Search symbol or company" value={search}
            onChange={(event) => { setSearch(event.target.value); setPage(0); }} />
          <span>{filtered.length.toLocaleString()} stocks</span>
          <div className="pagination-controls">
            <button className="icon-button" aria-label="Previous page" title="Previous page" disabled={currentPage === 0}
              onClick={() => setPage(currentPage - 1)}><ChevronLeft size={18} /></button>
            <span>Page {currentPage + 1} / {pageCount}</span>
            <button className="icon-button" aria-label="Next page" title="Next page" disabled={currentPage + 1 >= pageCount}
              onClick={() => setPage(currentPage + 1)}><ChevronRight size={18} /></button>
          </div>
        </div>
        {loading ? (
          <p>Loading...</p>
        ) : (
          <div className="table-scroll">
            <table className="candidates-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Company</th>
                  <th>Sector</th>
                  <th>Source</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {visibleStocks.map((s) => (
                  <tr key={s.symbol}>
                    <td className="symbol-cell"><Link to={`/stocks/${encodeURIComponent(s.symbol)}`}>{s.symbol}</Link></td>
                    <td>{s.company_name || "—"}</td>
                    <td>{s.sector || "—"}</td>
                    <td>{s.source === "upstox_nse" ? "Upstox / NSE" : s.source}</td>
                    <td>
                      <button className="secondary-button" onClick={() => handleRemove(s.symbol)}>
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
                {visibleStocks.length === 0 && <tr><td colSpan={5}>No matching stocks.</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
