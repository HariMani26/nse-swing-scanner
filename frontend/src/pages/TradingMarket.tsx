import { useEffect, useState } from "react";
import { fetchTradingMarket } from "../api/client";
import type { TradingMarket as Market } from "../types";
import { formatStamp, formatValue } from "../components/TradingEvidence";

export default function TradingMarket() {
  const [market, setMarket] = useState<Market | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    const controller = new AbortController();
    async function load(initial = false) {
      if (!active) return;
      if (document.hidden && !initial) { timer = window.setTimeout(() => void load(), 5000); return; }
      try { const result = await fetchTradingMarket(controller.signal); if (active) { setMarket(result); setError(null); } }
      catch (err) { if (active) setError(err instanceof Error ? err.message : "Market unavailable"); }
      if (active) timer = window.setTimeout(() => void load(), 60000);
    }
    void load(true);
    return () => { active = false; controller.abort(); window.clearTimeout(timer); };
  }, []);
  return <div className="trading-desk"><div className="desk-heading"><h1>Market Overview</h1><strong>{error ? "NO CLEAR SETUP" : market?.status || "CONNECTING"}</strong></div>
    <p className="source-strip">CALCULATED INDICATORS / COMPLETED CANDLES / {market?.source || "Provider pending"}</p>
    {error && <p className="error-banner" role="alert">{error}</p>}
    <div className="safety-banner"><strong>{market?.realtime_available ? "Real-time provider connected" : "REAL-TIME DATA UNAVAILABLE"}</strong>
      <span>{market?.market_open ? "Regular weekday session window" : "Outside regular weekday session window"}. Exchange holiday calendar unavailable.</span></div>
    <div className="table-scroll"><table className="candidates-table market-table"><thead><tr>
      {["Index", "Last Completed Daily Close", "Daily Trend", "Hourly Trend", "Support", "Resistance", "RSI", "ATR", "Daily Candle"].map(label => <th key={label}>{label}</th>)}
    </tr></thead><tbody>{market?.indices.map(index => <tr key={index.symbol}><td><strong>{index.name}</strong></td><td>{formatValue(index.value)}</td>
      <td>{error || index.daily.stale ? "STALE / UNAVAILABLE" : index.daily.trend}</td><td>{error || index.hourly.stale ? "STALE / UNAVAILABLE" : index.hourly.trend}</td>
      <td>{formatValue(index.daily.support)}</td><td>{formatValue(index.daily.resistance)}</td><td>{formatValue(index.daily.rsi)}</td><td>{formatValue(index.daily.atr)}</td><td>{formatStamp(index.timestamp)}</td>
    </tr>)}{!market && <tr><td colSpan={9}>Fetching provider index history...</td></tr>}</tbody></table></div>
    <dl className="evidence-metrics market-capabilities">
      <div><dt>Market breadth</dt><dd>{market?.breadth_status || "Unavailable"}</dd></div>
      <div><dt>Sector benchmarks</dt><dd>Yahoo sector proxies in stock evidence</dd></div>
      <div><dt>NSE catalogue</dt><dd>Online Upstox JSON / no CSV</dd></div>
      <div><dt>BSE</dt><dd>Not connected</dd></div>
      <div><dt>Real-time ticks</dt><dd>{market?.realtime_available ? "Provider supported" : "Not supported by Yahoo"}</dd></div>
      <div><dt>Execution</dt><dd>Paper journal only / no broker orders</dd></div>
    </dl>
  </div>;
}