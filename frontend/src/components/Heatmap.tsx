"use client";

import { useMemo } from "react";
import { hierarchy, treemap } from "d3-hierarchy";
import { Panel } from "./Panel";
import type { Position } from "@/lib/types";
import { fmtPct } from "@/lib/format";

type Props = { positions: Position[]; width?: number; height?: number };

function pnlColor(pct: number) {
  const clamped = Math.max(-0.1, Math.min(0.1, pct));
  const intensity = Math.abs(clamped) / 0.1;
  if (clamped >= 0) {
    const a = 0.18 + intensity * 0.5;
    return `rgba(38, 208, 124, ${a.toFixed(2)})`;
  }
  const a = 0.18 + intensity * 0.5;
  return `rgba(239, 77, 104, ${a.toFixed(2)})`;
}

export function Heatmap({ positions, height = 260 }: Props) {
  const layout = useMemo(() => {
    if (positions.length === 0) return null;
    const root = hierarchy({
      name: "root",
      children: positions.map((p) => ({ ...p, value: Math.max(p.market_value, 0.0001) })),
    } as { name: string; children: (Position & { value: number })[] }).sum((d) => (d as { value?: number }).value ?? 0);
    return treemap<typeof root extends { data: infer D } ? D : never>()
      .size([100, 100])
      .paddingInner(1)
      .round(false)(root as never);
  }, [positions]);

  return (
    <Panel title="Portfolio Heatmap" badge={<span className="text-2xs text-text-dim">{positions.length}</span>} corners>
      <div className="relative" style={{ height }} data-testid="portfolio-heatmap">
        {!layout ? (
          <div className="h-full flex items-center justify-center text-text-dim text-xs tracking-widest">
            NO POSITIONS
          </div>
        ) : (
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (layout as any).leaves().map((leaf: any) => {
            const p = leaf.data as Position;
            const w = leaf.x1 - leaf.x0;
            const h = leaf.y1 - leaf.y0;
            const small = w < 14 || h < 12;
            return (
              <div
                key={p.ticker}
                data-testid={`heat-${p.ticker}`}
                data-ticker={p.ticker}
                className="absolute border border-bg-deep flex flex-col items-center justify-center overflow-hidden"
                style={{
                  left: `${leaf.x0}%`,
                  top: `${leaf.y0}%`,
                  width: `${w}%`,
                  height: `${h}%`,
                  background: pnlColor(p.unrealized_pl_pct),
                }}
              >
                {!small ? (
                  <>
                    <span className="font-display font-medium text-text-primary text-xs tracking-wider">
                      {p.ticker}
                    </span>
                    <span className="text-2xs tabular text-text-primary/90">{fmtPct(p.unrealized_pl_pct)}</span>
                  </>
                ) : (
                  <span className="text-[8px] text-text-primary/80">{p.ticker}</span>
                )}
              </div>
            );
          })
        )}
      </div>
    </Panel>
  );
}
