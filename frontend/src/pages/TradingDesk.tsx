import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Search, Bell } from "lucide-react";
import { fetchStocks, fetchTradingAlerts, fetchQualifiedReport } from "../api/client";
import type { StockOut, TradingAlertOut, TradingReport } from "../types";
import TradingEvidence, { formatStamp, formatValue } from "../components/TradingEvidence";

const SWING = ["STRONG BUY", "BREAKOUT BUY", "PULLBACK BUY", "REVERSAL BUY", "STRONG SELL", "BREAKDOWN SELL", "EXIT", "NO TRADE"];
const INTRADAY = ["STRONG BUY", "STRONG SELL", "OPENING RANGE BREAKOUT", "OPENING RANGE BREAKDOWN", "PREVIOUS DAY HIGH BREAKOUT", "PREVIOUS DAY LOW BREAKDOWN", "VWAP BREAKOUT", "VWAP BREAKDOWN", "BREAKOUT + RETEST", "BREAKDOWN + RETEST", "TREND PULLBACK", "BEARISH TREND PULLBACK", "HIGH VOLUME MOMENTUM", "HIGH VOLUME SELLING", "WATCHLIST", "NO TRADE"];

export default function TradingDesk({ mode, live = false }: { mode: "swing" | "intraday"; live?: boolean }) {
  const { symbol } = useParams();
  const [group, setGroup] = useState(symbol ? "SELECTED" : "ALL NSE");
  const [selection, setSelection] = useState(symbol || "");
  const [draft, setDraft] = useState(symbol || "");
  const [stocks, setStocks] = useState<StockOut[]>([]);
  const [report, setReport] = useState<TradingReport | null>(null);
  const [alerts, setAlerts] = useState<TradingAlertOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState("ALL");
  const [focused, setFocused] = useState(symbol || "");
  const [auto, setAuto] = useState(true);
  const [clock, setClock] = useState(Date.now());

  useEffect(() => { fetchStocks().then(setStocks).catch(() => {}); }, []);
  useEffect(() => {
    if (symbol) { setGroup("SELECTED"); setSelection(symbol); setDraft(symbol); setFocused(symbol); }
  }, [symbol]);
  useEffect(() => { setCategory("ALL"); }, [mode, live]);
  useEffect(() => { const timer = window.setInterval(() => setClock(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    let controller: AbortController | null = null;
    setReport(null);
    setError(null);
    async function load(initial = false) {
      if (!active) return;
      if (document.hidden && !initial) { timer = window.setTimeout(() => void load(), 2000); return; }
      controller = new AbortController();
      let delay = 60000;
      let running = false;
      try {
        const data = await fetchQualifiedReport(mode, group, selection, controller.signal);
        if (!active) return;
        setReport(data); setError(null);
        delay = data.refreshing ? 2000 : Math.max(1, data.refresh_seconds) * 1000;
        running = data.refreshing;
        const events = await fetchTradingAlerts(controller.signal);
        if (active) setAlerts(events);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Market data unavailable");
      }
      if (active && (auto || running)) timer = window.setTimeout(() => void load(), delay);
    }
    void load(true);
    return () => { active = false; controller?.abort(); window.clearTimeout(timer); };
  }, [mode, group, selection, auto, live]);
  const rows = (report?.rows || []).map(row => {
    const stale = !row.timestamp || clock - new Date(row.timestamp).getTime() > 120000;
    return stale || error ? {...row, status: "REAL-TIME DATA UNAVAILABLE",
      data_label: "STALE / UNAVAILABLE", signal_label: "POTENTIAL SETUP", entry_zone: null, stop_loss: null, target1: null, target2: null, invalidation: null,
      invalidation_reason: null, missing_confirmations: [...new Set([...row.missing_confirmations, "Fresh price and analysis required before entry"])],
      categories: ["WATCHLIST"]} : row;
  });
  const visible = rows.filter(row => row.score >= 65 && (category === "ALL" || row.categories.includes(category)));
  const detail = rows.find(row => row.symbol === focused) || (rows.length === 1 ? rows[0] : null);
  const categories = mode === "swing" ? SWING : INTRADAY;

  return <div className="trading-desk">
    <div className="desk-heading"><div><h1>{live ? "Live Market Scanner" : mode === "swing" ? "Swing Scanner" : "Intraday Scanner"}</h1>
      <p className="source-strip">NSE INDIA / {report?.source || "Provider pending"} / {report?.realtime_available ? "LIVE DATA CAPABLE" : "DELAYED DATA"}</p></div>
      <label className="refresh-control"><input type="checkbox" checked={auto} onChange={event => setAuto(event.target.checked)} />Auto update</label>
    </div>
    {!report?.realtime_available && <div className="safety-banner"><strong>REAL-TIME DATA UNAVAILABLE</strong><span>Confirmed entries and live alerts unavailable.</span></div>}
    {report?.market && <section className="scanner-market" aria-label="Market filter">
      <div className="desk-heading"><h2>Market: {report.market.status}</h2><Link to="/market">Market detail</Link></div>
      <dl className="evidence-metrics">{report.market.indices.map(index => <div key={index.name}><dt>{index.name}</dt><dd>{formatValue(index.value)}<small>{index.daily.stale ? "STALE" : index.daily.trend}</small></dd></div>)}</dl>
      <p className="source-strip">{report.market.breadth_status}</p>
    </section>}
    <div className="desk-controls">
      <label>Universe<select value={group} onChange={event => { setGroup(event.target.value); setFocused(""); }}>
        <option value="ALL NSE">All online NSE equities</option><option>NIFTY 50</option><option>NIFTY 100</option><option>NIFTY 500</option><option value="SELECTED">Selected NSE stocks</option>
      </select></label>
      {group === "SELECTED" && <form onSubmit={event => { event.preventDefault(); setSelection(draft); }}>
        <label>Symbols<input list="online-symbols" value={draft} onChange={event => setDraft(event.target.value.toUpperCase())} placeholder="RELIANCE,TCS" aria-label="Stocks to analyze" /></label>
        <button className="icon-button" type="submit" title="Analyze selected stocks" aria-label="Analyze selected stocks"><Search size={18} /></button>
        <datalist id="online-symbols">{stocks.map(stock => <option key={stock.symbol} value={stock.symbol}>{stock.company_name}</option>)}</datalist>
      </form>}
      <span className="source-strip">{report?.total || 0} stocks / {report?.eligible || 0} liquid candidates / {report?.excluded || 0} excluded</span>
    </div>
    {(error || report?.error) && <div className="error-banner" role="alert">{error || report?.error}</div>}
    <div className="desk-tabs" role="tablist" aria-label="Setup category">
      {["ALL", ...categories].map(tab => <button role="tab" aria-selected={category === tab} key={tab} onClick={() => setCategory(tab)}>{tab}</button>)}
    </div>
    <div className="scan-status" role="status"><span>{report?.refreshing ? report.stage || "SCANNING" : report?.status || "CONNECTING"}</span>
      <span>{report?.processed || 0} / {report?.scan_total || report?.total || 0} processed / {formatStamp(report?.scan_timestamp)}</span></div>
    {report?.refreshing && <progress className="scanner-progress" aria-label="Universe scan progress" max={Math.max(1, report.scan_total || 1)} value={report.processed || 0} />}
    {category === "EXIT" ? <p><Link to="/positions">Review open positions and record exits</Link></p> : (["BUY", "SELL", "WATCH"] as const).map(bucket => {
      const members = visible.filter(row => (row.status.startsWith("CONFIRMED") ? row.direction : "WATCH") === bucket).slice(0, 5);
      return <section className={`scanner-results results-${bucket.toLowerCase()}`} key={bucket} aria-label={`Top 5 ${bucket}`}>
      <h2>Top 5 {bucket} <span>{members.length}</span></h2>
      <div className="table-scroll desk-table-wrap"><table className="candidates-table desk-table"><thead><tr>
      {["Rank", "Stock", "Sector", "CMP (INR)", "Status", "Setup", "Score", "Weekly", "Daily", "1H", "15M", "5M", "Trendline", "Support", "Resistance", "Breakout", "Entry Zone", "Stop Loss", "T1", "T2", "R:R", "VWAP", "RSI", "MACD", "EMA", "Volume", "Risk", "Timestamp", "Reason"].map(label => <th key={label}>{label}</th>)}
    </tr></thead><tbody>{members.map(row => <tr key={row.symbol} className={focused === row.symbol ? "selected-row" : ""}>
      <td>{row.rank}</td><td><button className="stock-link" onClick={() => setFocused(row.symbol)}>{row.symbol}</button></td><td>{row.sector}</td>
      <td>{formatValue(row.cmp)}<small>{row.data_label}</small></td><td className="status-cell">{row.status}</td><td>{row.setup || row.categories.join(", ")}</td><td>{row.score}/100<small>{row.grade}</small></td>
      {["1W", "1D", "1H", "15M", "5M"].map(key => <td key={key}>{row.timeframes[key].stale ? "STALE" : row.timeframes[key].trend}</td>)}
      <td>{row.trendline}</td><td>{formatValue(row.support)}</td><td>{formatValue(row.resistance)}</td><td>{formatValue(row.breakout_level)}</td>
      <td>{row.entry_zone?.map(value => formatValue(value)).join(" - ") || "Not confirmed"}</td><td>{formatValue(row.stop_loss)}</td><td>{formatValue(row.target1)}</td><td>{formatValue(row.target2)}</td>
      <td>{row.risk_reward == null ? "Unavailable" : `1:${formatValue(row.risk_reward)}`}</td><td>{formatValue(row.vwap)}</td><td>{formatValue(row.rsi)}</td><td>{formatValue(row.macd)}</td>
      <td>{row.ema_status}</td><td>{row.volume_status}<small>{formatValue(row.volume, 0)}</small></td><td>{row.risk_level}</td><td>{formatStamp(row.timestamp)}</td><td className="reason-cell">{row.reason}</td>
    </tr>)}{members.length === 0 && <tr><td colSpan={29}>{report?.refreshing ? "Scan in progress" : bucket === "WATCH" ? "NO QUALIFIED WATCH CANDIDATES" : "NO VALID TRADE SETUP"}</td></tr>}</tbody></table></div></section>;
    })}
    {detail && <TradingEvidence row={detail} />}
    <section className="alert-section"><h2><Bell size={19} /> Alert Log</h2><p className="source-strip">{report?.alert_status || "Live alerts require a verified real-time provider."}</p>
      {alerts.length === 0 ? <p className="empty-state">No verified live alerts.</p> : <ol className="alert-list">{alerts.map(alert => <li key={alert.id}>
        <strong>{alert.symbol} / {alert.event}</strong><span>{formatValue(alert.price)} / {formatStamp(alert.timestamp)}</span>
        <p>{alert.details.reason}</p><p>Entry {alert.details.entry_zone?.join(" - ") || "Not confirmed"} / SL {formatValue(alert.details.stop_loss)} / T1 {formatValue(alert.details.target1)} / T2 {formatValue(alert.details.target2)} / R:R {formatValue(alert.details.risk_reward)}</p>
      </li>)}</ol>}
    </section>
  </div>;
}