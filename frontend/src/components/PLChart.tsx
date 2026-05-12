"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi, LineData, UTCTimestamp } from "lightweight-charts";
import { Panel } from "./Panel";
import type { PortfolioSnapshot } from "@/lib/types";
import { fmtUsd, fmtPct } from "@/lib/format";

export function PLChart({ snapshots }: { snapshots: PortfolioSnapshot[] }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8b95a5",
        fontFamily: "JetBrains Mono, monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(31, 38, 48, 0.35)" },
        horzLines: { color: "rgba(31, 38, 48, 0.35)" },
      },
      rightPriceScale: { borderColor: "#1f2630" },
      timeScale: { borderColor: "#1f2630", timeVisible: true, secondsVisible: false },
      autoSize: true,
    });
    const series = chart.addAreaSeries({
      lineColor: "#ecad0a",
      topColor: "rgba(236, 173, 10, 0.30)",
      bottomColor: "rgba(236, 173, 10, 0)",
      lineWidth: 2,
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
    if (!series) return;
    const data: LineData[] = snapshots.map((s) => ({
      time: Math.floor(s.ts / 1000) as UTCTimestamp,
      value: s.total_value,
    }));
    series.setData(data);
  }, [snapshots]);

  const first = snapshots[0]?.total_value;
  const last = snapshots[snapshots.length - 1]?.total_value;
  const delta = first !== undefined && last !== undefined ? last - first : 0;
  const deltaPct = first ? delta / first : 0;
  const positive = delta >= 0;

  return (
    <Panel
      title="Equity Curve"
      right={
        snapshots.length > 1 ? (
          <span className={`tabular text-xs ${positive ? "text-tick-up" : "text-tick-down"}`}>
            {fmtUsd(delta, { signed: true })} ({fmtPct(deltaPct)})
          </span>
        ) : null
      }
      bodyClassName="relative min-h-[180px]"
      corners
    >
      <div
        ref={ref}
        className="absolute inset-0"
        data-testid="pnl-chart"
        data-points={snapshots.length}
      />
      {snapshots.length < 2 ? (
        <div className="absolute inset-0 flex items-center justify-center text-text-dim text-xs tracking-widest">
          COLLECTING<span className="dots" />
        </div>
      ) : null}
    </Panel>
  );
}
