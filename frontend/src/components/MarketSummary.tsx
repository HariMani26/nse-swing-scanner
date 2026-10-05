import type { MarketContextOut } from "../types";

interface Props {
  market: MarketContextOut;
}

const TREND_CLASS: Record<string, string> = {
  bullish: "trend-bullish",
  neutral: "trend-neutral",
  bearish: "trend-bearish",
};

export default function MarketSummary({ market }: Props) {
  return (
    <section className="card market-summary">
      <div className="market-summary-row">
        <div className="market-metric">
          <span className="metric-label">NIFTY 50</span>
          <span className="metric-value">{market.nifty50_value.toFixed(2)}</span>
          <span className={market.nifty50_change_pct >= 0 ? "change-positive" : "change-negative"}>
            {market.nifty50_change_pct >= 0 ? "+" : ""}
            {market.nifty50_change_pct.toFixed(2)}%
          </span>
        </div>
        <div className="market-metric">
          <span className="metric-label">NIFTY 500</span>
          <span className="metric-value">{market.nifty500_value.toFixed(2)}</span>
          <span className={market.nifty500_change_pct >= 0 ? "change-positive" : "change-negative"}>
            {market.nifty500_change_pct >= 0 ? "+" : ""}
            {market.nifty500_change_pct.toFixed(2)}%
          </span>
        </div>
        <div className="market-metric">
          <span className="metric-label">Market Trend</span>
          <span className={`trend-pill ${TREND_CLASS[market.trend]}`}>{market.trend.toUpperCase()}</span>
        </div>
        <div className="market-metric">
          <span className="metric-label">Market Status</span>
          <span className={market.is_market_open ? "status-open" : "status-closed"}>
            {market.is_market_open ? "OPEN" : "CLOSED"}
          </span>
        </div>
      </div>
      <div className="data-source-note">
        Source: {market.source} {market.source === "mock" ? "(demo data - not real market data)" : "(delayed, free data)"} ·
        as of {new Date(market.fetched_at).toLocaleString()}
      </div>
    </section>
  );
}
