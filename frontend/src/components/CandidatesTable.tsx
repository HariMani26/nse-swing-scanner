import { useNavigate } from "react-router-dom";
import type { ScanResultOut } from "../types";
import ScoreBadge from "./ScoreBadge";

interface Props {
  candidates: ScanResultOut[];
}

export default function CandidatesTable({ candidates }: Props) {
  const navigate = useNavigate();

  if (candidates.length === 0) {
    return <p className="empty-state">No candidates match the current filters. Try running a scan or relaxing filters.</p>;
  }

  return (
    <div className="table-scroll">
      <table className="candidates-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Symbol</th>
            <th>Score</th>
            <th>Price</th>
            <th>Change %</th>
            <th>RSI</th>
            <th>MACD</th>
            <th>EMA Trend</th>
            <th>Volume</th>
            <th>Setup</th>
            <th>Risk/Reward</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c, i) => {
            const volumeRatio = c.avg_volume20 > 0 ? c.volume / c.avg_volume20 : 0;
            const emaTrend = c.price > c.ema20 && c.ema20 > c.ema50 ? "Bullish" : c.price < c.ema20 && c.price < c.ema50 ? "Bearish" : "Mixed";
            return (
              <tr key={c.symbol} onClick={() => navigate(`/stocks/${c.symbol}`)} className="clickable-row">
                <td>{i + 1}</td>
                <td className="symbol-cell">{c.symbol}</td>
                <td>
                  <ScoreBadge score={c.total_score} label={c.status_label} />
                </td>
                <td>{c.price.toFixed(2)}</td>
                <td className={c.daily_change_pct >= 0 ? "change-positive" : "change-negative"}>
                  {c.daily_change_pct >= 0 ? "+" : ""}
                  {c.daily_change_pct.toFixed(2)}%
                </td>
                <td>{c.rsi14.toFixed(1)}</td>
                <td className={c.macd > c.macd_signal ? "change-positive" : "change-negative"}>
                  {c.macd > c.macd_signal ? "Bullish" : "Bearish"}
                </td>
                <td>{emaTrend}</td>
                <td>{volumeRatio.toFixed(2)}x</td>
                <td>
                  <span className={`setup-pill setup-${c.setup_type}`}>{c.setup_type}</span>
                </td>
                <td>{c.risk_reward ? `1:${c.risk_reward.toFixed(2)}` : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
