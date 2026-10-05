import { useEffect, useRef } from "react";
import { createChart, type IChartApi } from "lightweight-charts";
import type { CandleOut } from "../types";

interface Props {
  candles: CandleOut[];
}

export default function RsiChart({ candles }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height: 160,
      layout: { background: { color: "#ffffff" }, textColor: "#1f2937" },
      grid: { vertLines: { color: "#eef1f5" }, horzLines: { color: "#eef1f5" } },
      timeScale: { visible: true, borderColor: "#d1d5db" },
      rightPriceScale: { borderColor: "#d1d5db" },
    });
    chartRef.current = chart;

    const rsiSeries = chart.addLineSeries({ color: "#7c3aed", lineWidth: 2, title: "RSI 14" });
    rsiSeries.setData(candles.filter((c) => c.rsi14 != null).map((c) => ({ time: c.date, value: c.rsi14 as number })));
    rsiSeries.createPriceLine({ price: 70, color: "#dc2626", lineStyle: 2, lineWidth: 1, title: "70" });
    rsiSeries.createPriceLine({ price: 30, color: "#16a34a", lineStyle: 2, lineWidth: 1, title: "30" });

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
      <h3 className="chart-title">RSI (14)</h3>
      <div ref={containerRef} className="chart-container" />
    </div>
  );
}
