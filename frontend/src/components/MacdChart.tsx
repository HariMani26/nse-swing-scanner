import { useEffect, useRef } from "react";
import { createChart, type IChartApi } from "lightweight-charts";
import type { CandleOut } from "../types";

interface Props {
  candles: CandleOut[];
}

export default function MacdChart({ candles }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height: 180,
      layout: { background: { color: "#ffffff" }, textColor: "#1f2937" },
      grid: { vertLines: { color: "#eef1f5" }, horzLines: { color: "#eef1f5" } },
      timeScale: { visible: true, borderColor: "#d1d5db" },
      rightPriceScale: { borderColor: "#d1d5db" },
    });
    chartRef.current = chart;

    const histSeries = chart.addHistogramSeries({ color: "#9ca3af" });
    histSeries.setData(
      candles
        .filter((c) => c.macd_hist != null)
        .map((c) => ({
          time: c.date,
          value: c.macd_hist as number,
          color: (c.macd_hist as number) >= 0 ? "rgba(22,163,74,0.6)" : "rgba(220,38,38,0.6)",
        }))
    );

    const macdSeries = chart.addLineSeries({ color: "#2563eb", lineWidth: 2, title: "MACD" });
    macdSeries.setData(candles.filter((c) => c.macd != null).map((c) => ({ time: c.date, value: c.macd as number })));

    const signalSeries = chart.addLineSeries({ color: "#f59e0b", lineWidth: 2, title: "Signal" });
    signalSeries.setData(
      candles.filter((c) => c.macd_signal != null).map((c) => ({ time: c.date, value: c.macd_signal as number }))
    );

    chart.timeScale().fitContent();

    const resize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", resize);
    resize();

    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
    };
  }, [candles]);

  return (
    <div>
      <h3 className="chart-title">MACD (12, 26, 9)</h3>
      <div ref={containerRef} className="chart-container" />
    </div>
  );
}
