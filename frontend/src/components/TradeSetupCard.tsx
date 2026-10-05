import type { ScanResultOut } from "../types";

interface Props {
  result: ScanResultOut;
}

export default function TradeSetupCard({ result }: Props) {
  const hasTrade = result.setup_type !== "none" && result.entry != null;

  return (
    <section className="card trade-setup-card">
      <h2>Trade Setup</h2>
      <p className="setup-type-label">
        Setup: <span className={`setup-pill setup-${result.setup_type}`}>{result.setup_type}</span>
      </p>

      {hasTrade ? (
        <div className="trade-setup-grid">
          <div>
            <span className="metric-label">Possible Entry</span>
            <span className="metric-value">{result.entry?.toFixed(2)}</span>
          </div>
          <div>
            <span className="metric-label">Stop Loss</span>
            <span className="metric-value">{result.stop_loss?.toFixed(2)}</span>
          </div>
          <div>
            <span className="metric-label">Target 1</span>
            <span className="metric-value">{result.target1?.toFixed(2)}</span>
          </div>
          <div>
            <span className="metric-label">Target 2</span>
            <span className="metric-value">{result.target2?.toFixed(2)}</span>
          </div>
          <div>
            <span className="metric-label">Risk / Reward</span>
            <span className="metric-value">1:{result.risk_reward?.toFixed(2)}</span>
          </div>
        </div>
      ) : (
        <p className="empty-state">
          No qualifying trade idea today - either no breakout/pullback setup was confirmed, or the
          risk/reward ratio did not meet the minimum acceptable threshold.
        </p>
      )}
      <p className="disclaimer">This is a screening output, not financial advice or a trade recommendation.</p>
    </section>
  );
}
