import { useEffect, useRef, useState } from "react";
import { createChart, type Time, type UTCTimestamp } from "lightweight-charts";
import type { TimeframeEvidence, TradingRow } from "../types";

export const formatValue = (value: number | null | undefined, digits = 2) =>
  value == null || !Number.isFinite(value) ? "Unavailable" : value.toLocaleString("en-IN", { maximumFractionDigits: digits });
export const formatStamp = (value: string | null | undefined) => value
  ? new Date(value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`).toLocaleString("en-IN", {timeZone: "Asia/Kolkata"}) + " IST" : "Unavailable";

function EvidenceChart({ evidence }: { evidence: TimeframeEvidence }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current || !evidence.candles?.length) return;
    const time = (value: string) => Math.floor(new Date(value).getTime() / 1000) as UTCTimestamp;
    const chart = createChart(container.current, {height: 360, width: container.current.clientWidth,
      layout: {background: {color: "#ffffff"}, textColor: "#24343a"},
      grid: {vertLines: {color: "#edf0f1"}, horzLines: {color: "#edf0f1"}},
      timeScale: {timeVisible: !["1W", "1D"].includes(evidence.timeframe)},
    });
    const candles = chart.addCandlestickSeries({upColor: "#13815d", downColor: "#c43d4b", wickUpColor: "#13815d", wickDownColor: "#c43d4b", borderVisible: false});
    candles.setData(evidence.candles.map(candle => ({...candle, time: time(candle.timestamp)})));
    const first = time(evidence.candles[0].timestamp);
    candles.setMarkers(evidence.pivots.filter(point => time(point.timestamp) >= first).map(point => ({time: time(point.timestamp) as Time,
      position: point.kind === "high" ? "aboveBar" : "belowBar", shape: "circle", text: point.label,
      color: point.kind === "high" ? "#b42343" : "#087e69"})));
    for (const [field, color] of [["ema20", "#2463bd"], ["ema50", "#c17b12"], ["ema200", "#585e66"]] as const) {
      const line = chart.addLineSeries({color, lineWidth: 1, title: field.toUpperCase(), priceLineVisible: false});
      line.setData(evidence.candles.filter(candle => candle[field] != null).map(candle => ({time: time(candle.timestamp), value: candle[field]!})));
    }
    for (const [points, color] of [[evidence.support_line, "#087e69"], [evidence.resistance_line, "#b42343"]] as const) {
      if (points.length !== 2 || points.some(point => time(point.timestamp) < first)) continue;
      chart.addLineSeries({color, lineWidth: 2, priceLineVisible: false, lastValueVisible: false})
        .setData(points.map(point => ({time: time(point.timestamp), value: point.value})));
    }
    chart.timeScale().fitContent();
    const observer = new ResizeObserver(entries => chart.applyOptions({width: entries[0].contentRect.width}));
    observer.observe(container.current);
    return () => { observer.disconnect(); chart.remove(); };
  }, [evidence]);
  return <div className="evidence-chart" ref={container} aria-label={`${evidence.timeframe} price and trendline chart`} />;
}

export default function TradingEvidence({ row }: { row: TradingRow }) {
  const [timeframe, setTimeframe] = useState("1D");
  const evidence = row.timeframes[timeframe];
  return <section className="evidence-section">
    <div className="desk-heading"><h2>{row.symbol}</h2><strong>{row.status}</strong></div>
    <p className="source-strip">{row.signal_label} / {row.data_label} / Provider candle: {formatStamp(row.signal_timestamp)}</p>
    <dl className="evidence-metrics">
      {[["Direction", row.direction], ["Setup", row.setup], ["Current price", formatValue(row.cmp)],
        ["Entry zone", row.entry_zone?.map(value => formatValue(value)).join(" - ") || "Not confirmed"],
        ["Stop loss", formatValue(row.stop_loss)], ["Target 1", formatValue(row.target1)], ["Target 2", formatValue(row.target2)],
        ["Risk/reward", row.risk_reward == null ? "Unavailable" : `1:${formatValue(row.risk_reward)}`],
        ["Market", row.market_trend], ["Sector", row.sector_trend]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || "Unavailable"}</dd></div>)}
    </dl>
    {row.status.startsWith("CONFIRMED") && <><h3>Why This Trade Qualifies</h3><ol className="confirmation-list">{row.qualification_reasons?.map(reason => <li key={reason}>{reason}</li>)}</ol></>}
    <h3>Entry Confirmation</h3>
    {row.missing_confirmations.length ? <ul className="confirmation-list">{row.missing_confirmations.map(reason => <li key={reason}>{reason}</li>)}</ul> : <p>No required confirmations missing.</p>}
    <div className="desk-tabs" role="tablist" aria-label="Analysis timeframe">
      {Object.keys(row.timeframes).map(key => <button role="tab" aria-selected={timeframe === key} key={key} onClick={() => setTimeframe(key)}>{key}</button>)}
    </div>
    {evidence.available ? <>
      <p className={evidence.stale ? "safety-banner" : "source-strip"}>{evidence.stale ? "STALE CANDLES / " : "CALCULATED INDICATOR / "}{formatStamp(evidence.timestamp)}</p>
      <EvidenceChart evidence={evidence} />
      <dl className="evidence-metrics">
        {[["Trend", evidence.trend_strength || evidence.trend], ["Structure", evidence.structure], ["Trendline", evidence.trendline],
          ["Break of structure", evidence.break_of_structure], ["Change of character", evidence.change_of_character],
          ["Liquidity sweep", evidence.liquidity_sweep],
          ["W/M Pattern", evidence.pattern ? `${evidence.pattern.stage} (${evidence.pattern.score}/100, ${evidence.pattern.quality})` : "No qualifying pattern"],
          ["Pattern neckline", evidence.pattern ? formatValue(evidence.pattern.neckline) : null],
          ["False break", evidence.false_breakout ? "FALSE BREAKOUT" : evidence.false_breakdown ? "FALSE BREAKDOWN" : "NONE"],
          ["Retest", evidence.breakout_retest ? "BULLISH" : evidence.breakdown_retest ? "BEARISH" : "UNCONFIRMED"],
          ["Pivot demand zone", evidence.demand_zone?.map(value => formatValue(value)).join(" - ")],
          ["Pivot supply zone", evidence.supply_zone?.map(value => formatValue(value)).join(" - ")],
          ["Support", formatValue(evidence.support)], ["Resistance", formatValue(evidence.resistance)],
          ["Breakout", evidence.breakout ? "YES" : "NO"], ["Breakdown", evidence.breakdown ? "YES" : "NO"],
          ["Pullback", evidence.pullback ? "YES" : "NO"], ["Price action", evidence.price_action],
          ["Gap %", formatValue(evidence.gap_percent)], ["Volume", formatValue(evidence.volume, 0)],
          ["Relative volume", formatValue(evidence.relative_volume)], ["EMA 9", formatValue(evidence.ema9)],
          ["EMA 20", formatValue(evidence.ema20)], ["EMA 50", formatValue(evidence.ema50)], ["EMA 200", formatValue(evidence.ema200)],
          ["RSI 14", formatValue(evidence.rsi)], ["MACD", formatValue(evidence.macd)], ["MACD signal", formatValue(evidence.macd_signal)],
          ["VWAP", formatValue(evidence.vwap)], ["ATR", formatValue(evidence.atr)],
          ["RS vs NIFTY (20d, pp)", formatValue(row.relative_strength_nifty)], ["Sector trend", row.sector_trend],
          ["Avg turnover (INR)", formatValue(row.average_turnover, 0)], ["Avg volume", formatValue(row.average_volume, 0)],
          ["Bid/ask spread %", formatValue(row.spread_percent)],
        ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || "Unavailable"}</dd></div>)}
      </dl>
    </> : <p className="safety-banner">{evidence.reason}</p>}
    <h3>Intraday Levels</h3>
    <dl className="evidence-metrics">
      {[["Previous high", row.previous_day_high], ["Previous low", row.previous_day_low], ["Previous close", row.previous_day_close],
        ["Today open", row.today_open], ["Today high", row.today_high], ["Today low", row.today_low],
        ["Opening range high", row.opening_range_high], ["Opening range low", row.opening_range_low]].map(([label, value]) =>
        <div key={label as string}><dt>{label}</dt><dd>{formatValue(value as number | null)}</dd></div>)}
    </dl>
    <h3>Setup Score: {row.score}/100 / {row.grade}</h3>
    <p className="source-strip">Evidence score, not a probability of profit.</p>
    <div className="score-breakdown">{row.score_breakdown.map(item => <div key={item.component}>
      <span>{item.component}</span><meter min={0} max={item.maximum} value={item.points} aria-label={item.component} />
      <strong>{item.points}/{item.maximum}</strong><span>{item.reason}</span>
    </div>)}</div>
    <p><strong>Potential invalidation:</strong> {formatValue(row.invalidation)} / <strong>Risk:</strong> {row.risk_level}</p>
    {row.invalidation_reason && <p>{row.invalidation_reason}</p>}
  </section>;
}