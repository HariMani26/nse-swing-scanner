import { useEffect, useState } from "react";
import { Save, X, Check } from "lucide-react";
import { fetchPaperPositions, sizePosition, tradingRequest } from "../api/client";
import type { PaperPositionOut, RiskInput, RiskSize } from "../types";
import { formatStamp, formatValue } from "../components/TradingEvidence";

const DEFAULTS: RiskInput = {capital: 300000, risk_percent: 0.5, allocation: 300000, entry: 0, stop_loss: 0, target1: 0, side: "BUY"};

export default function PaperJournal({ view }: { view: "risk" | "positions" | "history" }) {
  const [input, setInput] = useState<RiskInput>(() => {
    try { const saved = JSON.parse(localStorage.getItem("trading-risk") || "null"); return saved ? {...DEFAULTS, capital: saved.capital, risk_percent: saved.risk_percent, allocation: saved.allocation} : DEFAULTS; }
    catch { return DEFAULTS; }
  });
  const [sizing, setSizing] = useState<RiskSize | null>(null);
  const [symbol, setSymbol] = useState("");
  const [style, setStyle] = useState("SWING");
  const [quantity, setQuantity] = useState(1);
  const [target2, setTarget2] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [correlationAcknowledged, setCorrelationAcknowledged] = useState(false);
  const [positions, setPositions] = useState<PaperPositionOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [riskError, setRiskError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [closing, setClosing] = useState<number | null>(null);
  const [exitPrice, setExitPrice] = useState("");
  const [exitReason, setExitReason] = useState("Manual paper exit");
  const [revision, setRevision] = useState(0);
  const update = (field: keyof RiskInput, value: string) => setInput(current => ({...current, [field]: field === "side" ? value : Number(value)}));
  useEffect(() => {
    let active = true;
    setError(null);
    fetchPaperPositions(view === "history").then(rows => { if (active) setPositions(rows); }).catch(err => { if (active) setError(String(err)); });
    return () => { active = false; };
  }, [view, revision]);
  useEffect(() => {
    const controller = new AbortController();
    setSizing(null); setRiskError(null);
    if (input.entry <= 0 || input.stop_loss <= 0 || input.target1 <= 0) return;
    const timer = window.setTimeout(() => {
      sizePosition(input, controller.signal).then(value => { setSizing(value); setRiskError(null); })
        .catch(err => { if (!controller.signal.aborted) setRiskError(String(err)); });
    }, 250);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [input, revision]);
  async function savePosition(event: React.FormEvent) {
    event.preventDefault(); setError(null); setNotice(null); setBusy(true);
    try {
      await tradingRequest("/positions", {...input, symbol, style, quantity, target2: target2 ? Number(target2) : null, acknowledge_paper: acknowledged, acknowledge_correlation: correlationAcknowledged});
      setNotice("Paper position recorded. No broker order placed."); setRevision(value => value + 1); setAcknowledged(false); setCorrelationAcknowledged(false);
    } catch (err) { setError(String(err)); } finally { setBusy(false); }
  }
  async function closePosition(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      await tradingRequest(`/positions/${closing}/close`, {exit_price: Number(exitPrice), reason: exitReason});
      setClosing(null); setRevision(value => value + 1); setNotice("Paper exit recorded.");
    } catch (err) { setError(String(err)); } finally { setBusy(false); }
  }
  const pnl = positions.reduce((sum, position) => sum + (position.realized_pnl || 0), 0);
  return <div className="trading-desk"><div className="desk-heading"><h1>{view === "risk" ? "Risk Management" : view === "positions" ? "Open Positions" : "Trade Journal"}</h1>
    <strong className="paper-label">PAPER ONLY</strong></div>
    <div className="safety-banner"><strong>No broker orders or automatic execution</strong><span>Stops can slip. Fees, taxes and gaps are excluded from planned risk and P&amp;L.</span></div>
    {error && <p className="error-banner" role="alert">{error}</p>}{notice && <p role="status" className="notice-banner">{notice}</p>}
    {view !== "history" && <>
      <h2>Position Sizing</h2>
      <form className="risk-form" onSubmit={savePosition}>
        <div className="risk-inputs">
          {[["capital", "Capital (INR)"], ["risk_percent", "Risk per trade (%)"], ["allocation", "Allocation ceiling (INR)"], ["entry", "Entry (INR)"], ["stop_loss", "Stop loss (INR)"], ["target1", "Target 1 (INR)"]].map(([field, label]) =>
            <label key={field}>{label}<input type="number" step={field === "risk_percent" ? "0.1" : "0.01"} min={field === "risk_percent" ? "0.1" : "0.01"} max={field === "risk_percent" ? "1" : undefined} required value={input[field as keyof RiskInput] || ""} onChange={event => update(field as keyof RiskInput, event.target.value)} /></label>)}
          <label>Direction<select value={input.side} onChange={event => update("side", event.target.value)}><option value="BUY">BUY / LONG</option><option value="SELL">SELL / INTRADAY SHORT</option></select></label>
          <button type="button" className="save-defaults" onClick={() => { try { localStorage.setItem("trading-risk", JSON.stringify(input)); setNotice("Risk preferences saved on this device."); } catch { setError("Local preferences storage unavailable"); } }}><Save size={17} />Save Risk Preferences</button>
        </div>
        {riskError && <p className="error-banner" role="alert">{riskError}</p>}
        <dl className="evidence-metrics sizing-results">
          {[["Risk budget (INR)", sizing?.risk_amount], ["Max quantity", sizing?.quantity], ["Capital required (INR)", sizing?.capital_required],
            ["Planned max loss (INR)", sizing?.maximum_loss], ["Potential profit (INR)", sizing?.potential_profit], ["Reward / Risk", sizing?.risk_reward],
            ["Unreserved cash (INR)", sizing?.available_capital], ["Remaining portfolio risk (INR)", sizing?.remaining_portfolio_risk]].map(([label, value]) =>
            <div key={label as string}><dt>{label}</dt><dd>{formatValue(value as number | undefined)}</dd></div>)}
        </dl>
        <p className="source-strip">Maximum 3 positions. Risk capped at 1% per trade and 2% across open paper positions.</p>
        {view === "positions" && <section className="paper-entry"><h2>Manual Paper Entry</h2><div className="risk-inputs">
          <label>NSE Symbol<input required value={symbol} maxLength={32} onChange={event => setSymbol(event.target.value.toUpperCase())} /></label>
          <label>Style<select value={style} onChange={event => setStyle(event.target.value)}><option>SWING</option><option>INTRADAY</option></select></label>
          <label>Quantity<input type="number" required min="1" max={sizing?.quantity || 0} value={quantity} onChange={event => setQuantity(Number(event.target.value))} /></label>
          <label>Target 2 (optional)<input type="number" step="0.01" min="0.01" value={target2} onChange={event => setTarget2(event.target.value)} /></label>
        </div><label className="paper-ack"><input type="checkbox" required checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} />I acknowledge this is a manual paper record, not a live order or recommendation.</label>
          {positions.length > 0 && <label className="paper-ack"><input type="checkbox" checked={correlationAcknowledged} onChange={event => setCorrelationAcknowledged(event.target.checked)} />I acknowledge same-sector or unknown sector concentration risk.</label>}
          <button className="primary-button" type="submit" disabled={busy || positions.length >= 3 || !sizing || quantity > sizing.quantity || (sizing.risk_reward || 0) < 2 || !acknowledged}><Save size={17} />Record Paper Entry</button>
        </section>}
      </form>
    </>}
    {view !== "risk" && <section className="journal-table"><div className="desk-heading"><h2>{view === "history" ? "Closed Paper Trades" : "Open Paper Ledger"}</h2>
      {view === "history" && <strong>Gross realized P&amp;L: INR {formatValue(pnl)}</strong>}</div>
      <div className="table-scroll"><table className="candidates-table"><thead><tr>
        {["Stock", "Style", "Side", "Quantity", "Entry", "Stop", "T1", "T2", "Opened", ...(view === "history" ? ["Exit", "Gross P&L", "Closed", "Reason"] : ["Action"])].map(label => <th key={label}>{label}</th>)}
      </tr></thead><tbody>{positions.map(position => <tr key={position.id}><td>{position.symbol}</td><td>{position.style}</td><td>{position.side}</td><td>{position.quantity}</td>
        <td>{formatValue(position.entry)}</td><td>{formatValue(position.stop_loss)}</td><td>{formatValue(position.target1)}</td><td>{formatValue(position.target2)}</td><td>{formatStamp(position.opened_at)}</td>
        {view === "history" ? <><td>{formatValue(position.exit_price)}</td><td>{formatValue(position.realized_pnl)}</td><td>{formatStamp(position.closed_at)}</td><td>{position.exit_reason}</td></> :
          <td><button type="button" className="icon-button" title="Record paper exit" aria-label={`Record paper exit for ${position.symbol}`} onClick={() => { setClosing(position.id); setExitPrice(""); }}><X size={17} /></button></td>}
      </tr>)}{positions.length === 0 && <tr><td colSpan={13}>No {view === "history" ? "closed" : "open"} paper positions.</td></tr>}</tbody></table></div>
    </section>}
    {closing !== null && <div className="dialog-backdrop"><section className="exit-dialog" role="dialog" aria-modal="true" aria-labelledby="exit-title"><div className="desk-heading"><h2 id="exit-title">Record Paper Exit</h2>
      <button type="button" className="icon-button" onClick={() => setClosing(null)} aria-label="Cancel paper exit" title="Cancel"><X size={18} /></button></div>
      <form onSubmit={closePosition}><label>Exit price (INR)<input autoFocus required type="number" step="0.01" min="0.01" value={exitPrice} onChange={event => setExitPrice(event.target.value)} /></label>
        <label>Reason<input required maxLength={255} value={exitReason} onChange={event => setExitReason(event.target.value)} /></label>
        <button type="submit" className="primary-button" disabled={busy}><Check size={17} />Confirm Paper Exit</button></form>
    </section></div>}
  </div>;
}