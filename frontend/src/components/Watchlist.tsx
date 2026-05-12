"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";
import { Panel } from "./Panel";
import { PriceFlash } from "./PriceFlash";
import { Sparkline } from "./Sparkline";
import { fmtPct } from "@/lib/format";
import { usePrices } from "@/lib/prices";
import type { WatchlistEntry } from "@/lib/types";

type Props = {
  items: WatchlistEntry[];
  selected: string | null;
  onSelect: (t: string) => void;
  onAdd: (t: string) => Promise<void>;
  onRemove: (t: string) => Promise<void>;
};

export function Watchlist({ items, selected, onSelect, onAdd, onRemove }: Props) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const { prices } = usePrices();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const t = draft.trim().toUpperCase();
    if (!t) return;
    setBusy(true);
    try {
      await onAdd(t);
      setDraft("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Watchlist"
      badge={<span className="text-2xs text-text-dim">{items.length}</span>}
      right={
        <form onSubmit={submit} className="flex items-center gap-1">
          <input
            data-testid="watchlist-add-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="+ TICKER"
            className="bg-bg-deep border border-line text-2xs uppercase tracking-widest text-text-primary px-2 py-1 w-24 focus:outline-none focus:border-accent-blue"
          />
          <button
            type="submit"
            disabled={busy}
            aria-label="Add ticker"
            data-testid="watchlist-add-button"
            className="border border-line p-1 hover:border-accent-yellow hover:text-accent-yellow text-text-muted"
          >
            <Plus size={12} />
          </button>
        </form>
      }
      bodyClassName="divide-y divide-line/60"
    >
      <div className="grid grid-cols-[64px_1fr_72px_92px_24px] px-3 py-1.5 text-2xs text-text-dim tracking-widest">
        <span>SYM</span>
        <span>LAST</span>
        <span className="text-right">CHG</span>
        <span className="text-right">TREND</span>
        <span />
      </div>
      <ul data-testid="watchlist" className="divide-y divide-line/60 max-h-[480px] overflow-auto">
        {items.map((it) => {
          const live = prices[it.ticker];
          const price = live?.price ?? it.price;
          const prev = it.prev_close || live?.prev || price;
          const chg = prev ? (price - prev) / prev : 0;
          const positive = chg >= 0;
          const series = live?.series ?? [];
          return (
            <li
              key={it.ticker}
              data-testid={`watchlist-row-${it.ticker}`}
              data-ticker={it.ticker}
              onClick={() => onSelect(it.ticker)}
              className={`grid grid-cols-[64px_1fr_72px_92px_24px] items-center px-3 py-2 cursor-pointer group transition-colors ${
                selected === it.ticker ? "bg-accent-blue/10 border-l-2 border-l-accent-blue -ml-0.5" : "hover:bg-white/[0.02]"
              }`}
            >
              <span className="font-display font-medium text-text-primary tracking-wider">{it.ticker}</span>
              <span data-testid={`price-${it.ticker}`}>
                <PriceFlash price={price} direction={live?.direction} className="text-text-primary text-sm" />
              </span>
              <span className={`text-right text-xs tabular ${positive ? "text-tick-up" : "text-tick-down"}`}>
                {fmtPct(chg)}
              </span>
              <span className="flex justify-end">
                <Sparkline data={series} positive={positive} />
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onRemove(it.ticker);
                }}
                aria-label={`Remove ${it.ticker}`}
                data-testid={`watchlist-remove-${it.ticker}`}
                className="opacity-0 group-hover:opacity-100 text-text-dim hover:text-tick-down"
              >
                <X size={12} />
              </button>
            </li>
          );
        })}
        {items.length === 0 ? (
          <li className="px-3 py-6 text-center text-text-dim text-xs">no symbols. add one above.</li>
        ) : null}
      </ul>
    </Panel>
  );
}
