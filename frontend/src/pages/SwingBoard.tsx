import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ArrowDownRight, ArrowUpRight, Search, X } from "lucide-react";
import { fetchStocks, fetchSwingOverview, fetchTradingReport } from "../api/client";
import type { StockOut, SwingOverviewReport, SwingOverviewRow, TradingRow } from "../types";
import TradingEvidence, { formatStamp, formatValue } from "../components/TradingEvidence";

export default function SwingBoard() {
  const { symbol } = useParams();
  const [group, setGroup] = useState(symbol ? "SELECTED" : "NIFTY 50");
  const [selection, setSelection] = useState(symbol || "");
  const [draft, setDraft] = useState(symbol || "");
  const [report, setReport] = useState<SwingOverviewReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [auto, setAuto] = useState(true);
  const [search, setSearch] = useState("");
  const [catalogue, setCatalogue] = useState<StockOut[]>([]);
  const [catalogueLoading, setCatalogueLoading] = useState(true);
  const [catalogueError, setCatalogueError] = useState<string | null>(null);
  const [strongOnly, setStrongOnly] = useState(false);
  const [focused, setFocused] = useState(symbol || "");
  const [detail, setDetail] = useState<TradingRow | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [clock, setClock] = useState(Date.now());

  useEffect(() => {
    if (symbol) { setGroup("SELECTED"); setSelection(symbol); setDraft(symbol); setFocused(symbol); }
  }, [symbol]);
  useEffect(() => {
    let active = true;
    fetchStocks().then(stocks => { if (active) setCatalogue(stocks); })
      .catch(() => { if (active) setCatalogueError("NSE symbol search unavailable"); })
      .finally(() => { if (active) setCatalogueLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    let controller: AbortController | undefined;
    setReport(null); setError(null);
    async function load(initial = false) {
      if (!active) return;
      if (document.hidden && !initial) { timer = window.setTimeout(() => void load(), 2000); return; }
      controller = new AbortController();
      let delay = 15000;
      let running = false;
      try {
        const result = await fetchSwingOverview(group, selection, controller.signal);
        if (!active) return;
        setReport(result); setError(null);
        running = result.refreshing;
        delay = running ? 2000 : result.refresh_seconds * 1000;
      } catch (err) { if (active) setError(err instanceof Error ? err.message : "Swing scan unavailable"); }
      if (active && (auto || running)) timer = window.setTimeout(() => void load(), delay);
    }
    void load(true);
    return () => { active = false; controller?.abort(); window.clearTimeout(timer); };
  }, [group, selection, auto]);
  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    let controller: AbortController | undefined;
    setDetail(null); setDetailError(null); setDetailLoading(Boolean(focused));
    if (!focused) return;
    async function load(initial = false) {
      if (!active) return;
      if (document.hidden && !initial) { timer = window.setTimeout(() => void load(), 2000); return; }
      controller = new AbortController();
      try {
        const result = await fetchTradingReport("swing", "SELECTED", focused, 0, controller.signal);
        if (!active) return;
        setDetail(result.rows[0] || null); setDetailError(result.error); setDetailLoading(result.refreshing);
        if (result.refreshing || auto) timer = window.setTimeout(() => void load(), result.refreshing ? 2000 : result.refresh_seconds * 1000);
      } catch (err) {
        if (active) { setDetailError(String(err)); setDetailLoading(false); if (auto) timer = window.setTimeout(() => void load(), 15000); }
      }
    }
    void load(true);
    return () => { active = false; controller?.abort(); window.clearTimeout(timer); };
  }, [focused, auto]);
  useEffect(() => { const timer = window.setInterval(() => setClock(Date.now()), 1000); return () => window.clearInterval(timer); }, []);

  const filter = search.toLowerCase().replace(/[^a-z0-9&_.-]+/g, " ").trim();
  function matches(stock: {symbol: string; company_name: string}) {
    const text = `${stock.symbol} ${stock.company_name}`.toLowerCase();
    const words = text.split(/[^a-z0-9&_.-]+/);
    return !filter || text.includes(filter) || filter.split(/\s+/).every(token => words.some(word => word.startsWith(token) || (word.length >= 3 && token.startsWith(word))));
  }
  const rows = (report?.overview_rows || []).filter(matches);
  const searchResults = filter ? catalogue.filter(matches) : [];
  const groups = [
    {key: "BULLISH", title: "Bullish", subtitle: "Potential Buy Setups", Icon: ArrowUpRight},
    {key: "BEARISH", title: "Bearish", subtitle: "Potential Sell / Exit Setups", Icon: ArrowDownRight},
  ] as const;
  const detailStale = !detail?.timestamp || clock - new Date(detail.timestamp).getTime() > 120000 || Boolean(detailError);
  const safeDetail = detail && detailStale ? {...detail, status: "NO CLEAR SETUP", data_label: "STALE / UNAVAILABLE", entry_zone: null, stop_loss: null, target1: null, target2: null, invalidation: null, missing_confirmations: [...detail.missing_confirmations, "Fresh price and analysis required before entry"]} : detail;
  const sorted = (items: SwingOverviewRow[], bearish: boolean) => [...items].sort((first, second) => {
    const firstLevel = bearish ? first.resistance : first.support;
    const secondLevel = bearish ? second.resistance : second.support;
    return Number(secondLevel.strong) - Number(firstLevel.strong) || secondLevel.touches - firstLevel.touches || (firstLevel.distance_percent ?? Infinity) - (secondLevel.distance_percent ?? Infinity) || first.symbol.localeCompare(second.symbol);
  });
  function stockButton(row: SwingOverviewRow) {
    return <button className="stock-link" aria-label={`Analyze ${row.symbol}`} onClick={() => setFocused(row.symbol)}>{row.symbol}</button>;
  }

  return <div className="trading-desk swing-board">
    <div className="desk-heading"><div><h1>Swing Trading</h1><p className="source-strip">NSE / WHOLE-INDEX SCREEN / COMPLETED DAILY &amp; WEEKLY CANDLES</p></div>
      <label className="refresh-control"><input type="checkbox" checked={auto} onChange={event => setAuto(event.target.checked)} />Auto update</label></div>
    <div className="desk-controls">
      <label>Universe<select value={group} onChange={event => { setGroup(event.target.value); setFocused(""); }}>
        <option>NIFTY 50</option><option>NIFTY 100</option><option>NIFTY 500</option><option value="SELECTED">Selected NSE stocks</option>
      </select></label>
      {group === "SELECTED" && <form onSubmit={event => { event.preventDefault(); setSelection(draft); }}><label>Symbols<input aria-label="Selected NSE symbols" value={draft} onChange={event => setDraft(event.target.value.toUpperCase())} placeholder="RELIANCE,TCS" /></label>
        <button className="icon-button" title="Scan selected symbols" aria-label="Scan selected symbols"><Search size={18} /></button></form>}
      <label className="swing-search">Stock search<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search NSE symbols" /></label>
      <label className="strong-filter"><input type="checkbox" checked={strongOnly} onChange={event => setStrongOnly(event.target.checked)} />Strong nearby levels only</label>
    </div>
    {filter && <section className="swing-other" aria-label="NSE symbol search results">
      <h2>NSE symbols ({searchResults.length})</h2>
      {catalogueLoading ? <p role="status">Loading NSE symbols...</p> : catalogueError ? <p role="alert">{catalogueError}</p> : searchResults.length === 0 ? <p>No matching active NSE symbols.</p> : <>
        <div className="table-scroll"><table className="candidates-table"><thead><tr><th>Symbol</th><th>Analysis</th></tr></thead><tbody>
          {searchResults.slice(0, 20).map(stock => <tr key={stock.symbol}><td><button className="stock-link" aria-label={`Scan ${stock.symbol}`} onClick={() => { setGroup("SELECTED"); setSelection(stock.symbol); setDraft(stock.symbol); setFocused(stock.symbol); setSearch(""); setStrongOnly(false); }}>{stock.symbol}</button></td>
            <td>{report?.overview_rows.find(row => row.symbol === stock.symbol)?.group || "Not in current scan"}</td></tr>)}
        </tbody></table></div>
        {searchResults.length > 20 && <p className="source-strip">20 of {searchResults.length} matching symbols</p>}
      </>}
    </section>}
    {(error || report?.error) && <div className="error-banner" role="alert">{error || report?.error}</div>}
    <div className="swing-progress" role="status"><div><strong>{report?.refreshing ? report.stage === "QUEUED" ? "Scan queued" : "Scanning index" : report ? "Scan complete" : "Connecting"}</strong>
      <span>{report?.processed || 0} / {report?.scan_total || report?.total || 0} stocks processed</span></div>
      <progress aria-label="Index scan progress" max={Math.max(1, report?.scan_total || 1)} value={report?.processed || 0} />
      <span className="source-strip">{report?.source || "Provider pending"} / {formatStamp(report?.scan_timestamp)} / 15-minute overview refresh</span>
    </div>
    <p className="source-strip">POTENTIAL SETUPS / Trend and level evidence only. Entry, stop and targets require fresh multi-timeframe confirmation.</p>
    <div className="swing-groups">{groups.map(({key, title, subtitle, Icon}) => {
      const members = sorted(rows.filter(row => row.group === key && (!strongOnly || (key === "BULLISH" ? row.support.strong : row.resistance.strong))), key === "BEARISH");
      return <section key={key} className={`swing-group swing-${key.toLowerCase()}`}>
        <div className="swing-group-heading"><div><h2><Icon size={20} />{title} <span>{members.length}</span></h2><p>{subtitle}</p></div></div>
        <div className="table-scroll"><table className="candidates-table swing-table"><thead><tr><th>Stock</th><th>Daily Close</th><th>{key === "BULLISH" ? "Support" : "Resistance"}</th><th>Evidence</th><th>Weekly</th></tr></thead>
          <tbody>{members.map(row => { const level = key === "BULLISH" ? row.support : row.resistance; return <tr key={row.symbol} className={focused === row.symbol ? "selected-row" : ""}>
            <td>{stockButton(row)}</td><td>{formatValue(row.close)}<small>{row.timestamp?.slice(0, 10) || "Unavailable"}</small></td>
            <td>{formatValue(level.level)}<small>{formatValue(level.distance_percent)}% away</small></td>
            <td><strong className={level.strong ? "level-strong" : ""}>{level.strong ? key === "BULLISH" ? "BUY CANDIDATE" : "SELL / EXIT CANDIDATE" : level.level === null ? "NO CONFIRMED LEVEL" : level.touches < 2 ? "SINGLE PIVOT" : "AWAITING RETEST"}</strong><small>{level.touches} confirmed pivots</small></td>
            <td>{row.weekly_stale ? "STALE" : row.weekly_trend}</td></tr>; })}
          {members.length === 0 && <tr><td colSpan={5}>{report?.refreshing ? "No matching stocks in completed batches yet." : "No matching setups."}</td></tr>}</tbody></table></div>
      </section>;
    })}</div>
    <details className="swing-other"><summary>Neutral / No Clear Setup ({rows.filter(row => row.group === "NEUTRAL").length})</summary>
      <div className="table-scroll"><table className="candidates-table"><thead><tr><th>Stock</th><th>Daily Close</th><th>Support</th><th>Resistance</th><th>Reason</th></tr></thead><tbody>
        {rows.filter(row => row.group === "NEUTRAL").map(row => <tr key={row.symbol}><td>{stockButton(row)}</td><td>{formatValue(row.close)}</td><td>{formatValue(row.support.level)}</td><td>{formatValue(row.resistance.level)}</td><td>{row.reason}</td></tr>)}
      </tbody></table></div></details>
    <details className="swing-other"><summary>Excluded / Unavailable ({rows.filter(row => row.group === "EXCLUDED").length})</summary>
      <ul className="confirmation-list">{rows.filter(row => row.group === "EXCLUDED").map(row => <li key={row.symbol}>{row.symbol}: {row.reason}</li>)}</ul></details>
    {focused && <aside className="swing-detail-panel" role="dialog" aria-modal="false" aria-label={`${focused} detailed analysis`}>
      <div className="desk-heading"><h2>{focused} / Entry Confirmation</h2><button className="icon-button" title="Close analysis" aria-label="Close analysis" onClick={() => setFocused("")}><X size={18} /></button></div>
      {detailLoading && <p role="status">Fetching detailed timeframes for {focused}...</p>}{detailError && <p className="error-banner" role="alert">{detailError}</p>}
      {safeDetail && <><dl className="evidence-metrics">
        <div><dt>Entry zone</dt><dd>{safeDetail.entry_zone?.map(value => formatValue(value)).join(" - ") || "Not confirmed"}</dd></div>
        <div><dt>Stop loss</dt><dd>{formatValue(safeDetail.stop_loss)}</dd></div><div><dt>Target 1</dt><dd>{formatValue(safeDetail.target1)}</dd></div><div><dt>Target 2</dt><dd>{formatValue(safeDetail.target2)}</dd></div>
      </dl><TradingEvidence row={safeDetail} /></>}
      {!safeDetail && !detailLoading && !detailError && <p>Detailed data unavailable.</p>}
    </aside>}
  </div>;
}