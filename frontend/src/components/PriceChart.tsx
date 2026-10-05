import { useEffect, useRef } from "react";
import { createChart, type IChartApi } from "lightweight-charts";
import type { CandleOut, DailyAnalysisOut } from "../types";

interface Props {
  candles: CandleOut[];
  analysis?: DailyAnalysisOut;
}

export default function PriceChart({ candles, analysis }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height: 380,
      layout: { background: { color: "#ffffff" }, textColor: "#1f2937" },
      grid: { vertLines: { color: "#eef1f5" }, horzLines: { color: "#eef1f5" } },
      timeScale: { timeVisible: false, borderColor: "#d1d5db" },
      rightPriceScale: { borderColor: "#d1d5db" },
    });
    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#16a34a",
      downColor: "#dc2626",
      borderVisible: false,
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
    });
    candleSeries.setData(
      candles.map((c) => ({ time: c.date, open: c.open, high: c.high, low: c.low, close: c.close }))
    );

    if (analysis) {
      candleSeries.setMarkers(analysis.pivots.map((point) => ({
        time: point.date,
        position: point.kind === "high" ? "aboveBar" : "belowBar",
        color: point.kind === "high" ? "#be123c" : "#047857",
        shape: "circle",
        text: point.label,
      })));
      for (const [points, color, title] of [
        [analysis.support_line, "#047857", "Swing lows"],
        [analysis.resistance_line, "#be123c", "Swing highs"],
      ] as const) {
        if (points.length < 2) continue;
        const line = chart.addLineSeries({ color, lineWidth: 2, title,
          priceLineVisible: false, lastValueVisible: false });
        line.setData(points.map((point) => ({ time: point.date, value: point.value })));
      }
    }

    const ema20Series = chart.addLineSeries({ color: "#2563eb", lineWidth: 2, title: "EMA20" });
    ema20Series.setData(
      candles.filter((c) => c.ema20 != null).map((c) => ({ time: c.date, value: c.ema20 as number }))
    );

    const ema50Series = chart.addLineSeries({ color: "#f59e0b", lineWidth: 2, title: "EMA50" });
    ema50Series.setData(
      candles.filter((c) => c.ema50 != null).map((c) => ({ time: c.date, value: c.ema50 as number }))
    );

    const volumeSeries = chart.addHistogramSeries({
      color: "#9ca3af",
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
    volumeSeries.setData(
      candles.map((c) => ({
        time: c.date,
        value: c.volume,
        color: c.close >= c.open ? "rgba(22,163,74,0.5)" : "rgba(220,38,38,0.5)",
      }))
    );

    chart.timeScale().fitContent();

    const resize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", resize);
    resize();

    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
    };
  }, [candles, analysis]);

  return <div ref={containerRef} className="chart-container" />;
}
