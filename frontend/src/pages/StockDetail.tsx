import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchStockDetail, fetchStockQuote } from "../api/client";
import type { StockDetailOut, StockQuoteOut } from "../types";
import ScoreBadge from "../components/ScoreBadge";
import PriceChart from "../components/PriceChart";
import RsiChart from "../components/RsiChart";
import MacdChart from "../components/MacdChart";
import TradeSetupCard from "../components/TradeSetupCard";
import ReasonList from "../components/ReasonList";
import NewsList from "../components/NewsList";

export default function StockDetail() {
  const { symbol } = useParams<{ symbol: string }>();
  const [detail, setDetail] = useState<StockDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [quote, setQuote] = useState<StockQuoteOut | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    if (!symbol) return;
    setDetail(null);
    setQuote(null);
    setError(null);
    setQuoteError(null);
    setLoading(true);
  }, [symbol]);

  useEffect(() => {
    if (!symbol) return;
    const stockSymbol = symbol;
    let active = true;
    let pending = false;
    let controller: AbortController | null = null;
    async function refresh(initial = false) {
      if (pending || (!initial && document.hidden)) return;
      pending = true;
      controller = new AbortController();
      const timeout = window.setTimeout(() => controller?.abort(), 45000);
      await Promise.allSettled([
        fetchStockDetail(stockSymbol, controller.signal)
          .then((value) => {
            if (active) { setDetail(value); setError(null); }
          })
          .catch((err) => {
            if (active) setError(err instanceof Error ? err.message : "Daily analysis unavailable");
          })
          .finally(() => { if (active) setLoading(false); }),
        fetchStockQuote(stockSymbol, controller.signal)
          .then((value) => {
            if (active) { setQuote(value); setQuoteError(null); }
          })
          .catch(() => { if (active) setQuoteError("Quote refresh failed. Displayed price may be stale."); }),
      ]);
      window.clearTimeout(timeout);
      pending = false;
    }
    void refresh(true);
    const timer = autoRefresh ? window.setInterval(() => void refresh(), 60000) : undefined;
    const onVisible = () => { if (autoRefresh && !document.hidden) void refresh(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      active = false;
      controller?.abort();
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [symbol, autoRefresh]);

  if (loading) return <p>Loading...</p>;
  if (error && !detail) return <div className="error-banner">{error}</div>;
  if (!detail) return null;

  const { stock, latest_result, news, candles, daily_analysis: analysis } = detail;
  const money = (value: number | null) => value == null ? "Unavailable" : `INR ${value.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const stale = quote?.is_stale || Boolean(quoteError);

  return (
    <div className="stock-detail-page">
      <Link to="/" className="back-link">
        ← Back to dashboard
      </Link>

      <div className="stock-detail-header">
        <div>
          <h1>
            {stock.symbol} <span className="company-name">{stock.company_name}</span>
          </h1>
          {latest_result && (
            <p className="subtitle">
              Data as of {new Date(latest_result.data_timestamp).toLocaleString()} · Source:{" "}
              {latest_result.data_source} {latest_result.data_source === "mock" ? "(demo data)" : "(delayed, free data)"}
            </p>
          )}
        </div>
        {latest_result && <ScoreBadge score={latest_result.total_score} label={latest_result.status_label} />}
      </div>

      <section className="quote-band" aria-label="Latest stock quote">
        <div className="quote-heading">
          <h2>Latest Price</h2>
          <label className="refresh-control">
            <input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} />
            Auto-refresh (60s)
          </label>
        </div>
        <div className="quote-price-row">
          <strong className="quote-price">{quote ? money(quote.price) : "Loading quote..."}</strong>
          {quote?.change_pct != null && <span className={quote.change_pct >= 0 ? "change-positive" : "change-negative"}>
            {quote.change_pct > 0 ? "+" : ""}{quote.change_pct.toFixed(2)}%
          </span>}
          <span>{quote?.source || detail.data_source} / {detail.data_source === "mock" ? "DEMO" : "DELAYED"}</span>
          {quote && <span>{quote.market_open ? "Trading hours" : "Outside trading hours"}</span>}
        </div>
        <p className="subtitle">Quote candle: {quote?.timestamp ? new Date(quote.timestamp).toLocaleString() : "Unavailable"}</p>
        <p className="subtitle">Last successful fetch: {quote?.fetched_at ? new Date(quote.fetched_at).toLocaleString() : "Unavailable"}</p>
        {(stale || quote?.error || quoteError) && <p className="quote-warning" role="status">
          {quoteError || quote?.error || "Quote is stale; it may not reflect the current market."}
        </p>}
      </section>

      {error && <div className="error-banner">Daily analysis refresh failed. Previous analysis retained. {error}</div>}
      <section className="daily-analysis" aria-label="Daily trend analysis">
        <div className="quote-heading">
          <h2>Daily Trend</h2>
          <strong className={`daily-signal signal-${error ? "WAIT" : analysis.signal}`}>{error ? "WAIT" : analysis.signal}</strong>
        </div>
        <p><strong>{analysis.trend.toUpperCase()}</strong> / {analysis.as_of || "No completed candles"} / {detail.data_source === "mock" ? "DEMO" : "Daily close"}</p>
        <p>{error ? "Analysis refresh unavailable; no actionable signal." : analysis.reason}</p>
        <div className="technical-grid">
          <Metric label="Support" value={money(analysis.support)} />
          <Metric label="Resistance" value={money(analysis.resistance)} />
          <Metric label="Volume / prior 20d" value={analysis.volume_ratio == null ? "Unavailable" : `${analysis.volume_ratio.toFixed(2)}x`} />
          {!error && analysis.signal !== "WAIT" && <>
            <Metric label="Signal close" value={money(analysis.entry)} />
            <Metric label="Stop loss" value={money(analysis.stop_loss)} />
            <Metric label="2R target" value={money(analysis.target)} />
          </>}
        </div>
        <p className="data-source-note">Screening setup, not financial advice. SELL indicates bearish/exit conditions, not an order. Trading-hours status excludes exchange holidays.</p>
      </section>

      {candles.length > 0 ? <section className="daily-charts">
        <h2>Completed Daily Candles</h2>
        <PriceChart candles={candles} analysis={analysis} />
        <RsiChart candles={candles} />
        <MacdChart candles={candles} />
      </section> : <p className="empty-state">Daily market data unavailable from {detail.data_source}.</p>}

      {!latest_result && (
        <p className="empty-state">
          No saved scan result for this data provider.
        </p>
      )}

      {latest_result && (
        <>
          <section className="card technical-summary">
            <h2>Technical Summary</h2>
            <div className="technical-grid">
              <Metric label="Price" value={latest_result.price.toFixed(2)} />
              <Metric label="Daily change" value={`${latest_result.daily_change_pct.toFixed(2)}%`} />
              <Metric label="EMA20" value={latest_result.ema20.toFixed(2)} />
              <Metric label="EMA50" value={latest_result.ema50.toFixed(2)} />
              <Metric label="RSI14" value={latest_result.rsi14.toFixed(2)} />
              <Metric label="MACD" value={latest_result.macd.toFixed(2)} />
              <Metric label="Signal" value={latest_result.macd_signal.toFixed(2)} />
              <Metric label="Histogram" value={latest_result.macd_hist.toFixed(2)} />
              <Metric label="Volume" value={latest_result.volume.toLocaleString()} />
              <Metric label="Avg Volume (20d)" value={latest_result.avg_volume20.toLocaleString()} />
              <Metric label="ATR14" value={latest_result.atr14.toFixed(2)} />
              <Metric label="52-week high" value={latest_result.high_52w.toFixed(2)} />
              <Metric label="Distance from high" value={`${latest_result.distance_from_high_pct.toFixed(2)}%`} />
              <Metric label="Recent support" value={latest_result.recent_support.toFixed(2)} />
              <Metric label="Recent resistance" value={latest_result.recent_resistance.toFixed(2)} />
            </div>
          </section>

          <TradeSetupCard result={latest_result} />
          <ReasonList reasons={latest_result.reasons} warnings={latest_result.warnings} />
        </>
      )}

      <NewsList news={news} />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-block">
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
    </div>
  );
}
