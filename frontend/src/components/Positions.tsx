"use client";

import { Panel } from "./Panel";
import { usePrices } from "@/lib/prices";
import { fmtUsd, fmtPct, fmtQty } from "@/lib/format";
import type { Position } from "@/lib/types";

export function deriveLive(p: Position, livePrice: number | undefined): Position {
  const px = livePrice ?? p.current_price;
  const mv = px * p.quantity;
  const cost = p.avg_cost * p.quantity;
  const pl = mv - cost;
  const plPct = cost === 0 ? 0 : pl / cost;
  return { ...p, current_price: px, market_value: mv, unrealized_pl: pl, unrealized_pl_pct: plPct };
}

export function Positions({ positions, onSelect }: { positions: Position[]; onSelect?: (t: string) => void }) {
  const { prices } = usePrices();
  return (
    <Panel
      title="Positions"
      badge={<span className="text-2xs text-text-dim">{positions.length}</span>}
      bodyClassName="overflow-x-auto"
    >
      <table className="w-full text-xs tabular" data-testid="positions-table">
        <thead className="text-text-dim text-2xs tracking-widest">
          <tr className="border-b border-line">
            <th className="text-left px-3 py-2 font-normal">SYM</th>
            <th className="text-right px-3 py-2 font-normal">QTY</th>
            <th className="text-right px-3 py-2 font-normal">AVG</th>
            <th className="text-right px-3 py-2 font-normal">LAST</th>
            <th className="text-right px-3 py-2 font-normal">MKT VAL</th>
            <th className="text-right px-3 py-2 font-normal">P&L</th>
            <th className="text-right px-3 py-2 font-normal">%</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => {
            const live = deriveLive(p, prices[p.ticker]?.price);
            const positive = live.unrealized_pl >= 0;
            return (
              <tr
                key={p.ticker}
                data-testid={`position-row-${p.ticker}`}
                data-ticker={p.ticker}
                onClick={() => onSelect?.(p.ticker)}
                className="border-b border-line/40 hover:bg-white/[0.02] cursor-pointer"
              >
                <td className="px-3 py-2 font-display tracking-wider text-text-primary">{p.ticker}</td>
                <td className="px-3 py-2 text-right">{fmtQty(p.quantity)}</td>
                <td className="px-3 py-2 text-right text-text-muted">{fmtUsd(p.avg_cost)}</td>
                <td className="px-3 py-2 text-right text-text-primary">{fmtUsd(live.current_price)}</td>
                <td className="px-3 py-2 text-right">{fmtUsd(live.market_value)}</td>
                <td className={`px-3 py-2 text-right ${positive ? "text-tick-up" : "text-tick-down"}`}>
                  {fmtUsd(live.unrealized_pl, { signed: true })}
                </td>
                <td className={`px-3 py-2 text-right ${positive ? "text-tick-up" : "text-tick-down"}`}>
                  {fmtPct(live.unrealized_pl_pct)}
                </td>
              </tr>
            );
          })}
          {positions.length === 0 ? (
            <tr>
              <td colSpan={7} className="text-center text-text-dim px-3 py-6">
                no open positions. submit an order below.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </Panel>
  );
}
