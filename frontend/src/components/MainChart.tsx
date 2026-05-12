"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi, LineData, UTCTimestamp } from "lightweight-charts";
import { Panel } from "./Panel";
import { usePrices } from "@/lib/prices";
import { fmtUsd, fmtPct } from "@/lib/format";

export function MainChart({ ticker }: { ticker: string | null }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const { prices } = usePrices();
  const state = ticker ? prices[ticker] : undefined;

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8b95a5",
        fontFamily: "JetBrains Mono, monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(31, 38, 48, 0.4)" },
        horzLines: { color: "rgba(31, 38, 48, 0.4)" },
      },
      rightPriceScale: { borderColor: "#1f2630", scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale: { borderColor: "#1f2630", timeVisible: true, secondsVisible: true },
      crosshair: { mode: 1 },
      autoSize: true,
    });
    const series = chart.addAreaSeries({
      lineColor: "#209dd7",
      topColor: "rgba(32, 157, 215, 0.30)",
      bottomColor: "rgba(32, 157, 215, 0)",
      lineWidth: 2,
      priceLineColor: "#ecad0a",
      priceLineStyle: 2,
    });
    chartRef.current = chart;
    seriesRef.current = series;
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series || !state) {
      series?.setData([]);
      return;
    }
    const data: LineData[] = state.series.map((p) => ({
      time: Math.floor(p.ts / 1000) as UTCTimestamp,
      value: p.price,
    }));
    series.setData(data);
  }, [state, ticker]);

  const change = state ? state.price - state.prev : 0;
  const changePct = state && state.prev ? change / state.prev : 0;
  const positive = change >= 0;

  return (
    <Panel
      title="Market View"
      badge={
        ticker ? (
          <span className="font-display tracking-wider text-text-primary ml-2">{ticker}</span>
        ) : (
          <span className="text-2xs text-text-dim">select a symbol</span>
        )
      }
      right={
        state ? (
          <div className="flex items-center gap-3 text-xs">
            <span className="text-text-primary tabular text-sm">{fmtUsd(state.price)}</span>
            <span className={`tabular ${positive ? "text-tick-up" : "text-tick-down"}`}>
              {fmtUsd(change, { signed: true })} ({fmtPct(changePct)})
            </span>
          </div>
        ) : null
      }
      className="flex flex-col"
      bodyClassName="relative flex-1 min-h-[280px]"
      corners
    >
      <div ref={containerRef} className="absolute inset-0" data-testid="main-chart" />
      {!ticker || !state ? (
        <div className="absolute inset-0 flex items-center justify-center text-text-dim text-xs tracking-widest">
          AWAITING DATA<span className="dots" />
        </div>
      ) : null}
    </Panel>
  );
}
