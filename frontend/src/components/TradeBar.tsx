"use client";

import { useState } from "react";
import { Panel } from "./Panel";
import { usePrices } from "@/lib/prices";
import { fmtUsd } from "@/lib/format";

type Props = {
  defaultTicker?: string | null;
  onSubmit: (ticker: string, side: "buy" | "sell", quantity: number) => Promise<{ ok: boolean; error?: string }>;
};

export function TradeBar({ defaultTicker, onSubmit }: Props) {
  const [ticker, setTicker] = useState(defaultTicker ?? "");
  const [qty, setQty] = useState("10");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const { prices } = usePrices();

  const t = (ticker || defaultTicker || "").toUpperCase();
  const price = t ? prices[t]?.price : undefined;
  const quantity = Number(qty);
  const estimate = price !== undefined && Number.isFinite(quantity) ? price * quantity : undefined;

  async function fire(side: "buy" | "sell") {
    setMsg(null);
    if (!t || !Number.isFinite(quantity) || quantity <= 0) {
      setMsg({ kind: "err", text: "enter ticker and positive quantity" });
      return;
    }
    setBusy(true);
    try {
      const r = await onSubmit(t, side, quantity);
      if (r.ok) setMsg({ kind: "ok", text: `${side.toUpperCase()} ${quantity} ${t} filled` });
      else setMsg({ kind: "err", text: r.error ?? "order rejected" });
    } catch (e) {
      setMsg({ kind: "err", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Order Entry" right={<span className="text-2xs text-text-dim">market · instant</span>}>
      <div className="flex flex-wrap items-center gap-2 p-3">
        <label className="flex items-center gap-2">
          <span className="panel-title">SYM</span>
          <input
            data-testid="trade-ticker"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder={defaultTicker ?? "AAPL"}
            className="bg-bg-deep border border-line text-sm tracking-wider uppercase text-text-primary px-2 py-1.5 w-24 focus:outline-none focus:border-accent-blue"
          />
        </label>
        <label className="flex items-center gap-2">
          <span className="panel-title">QTY</span>
          <input
            data-testid="trade-quantity"
            type="number"
            min="0"
            step="0.01"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            className="bg-bg-deep border border-line text-sm tabular text-text-primary px-2 py-1.5 w-24 focus:outline-none focus:border-accent-blue"
          />
        </label>
        <span className="text-2xs text-text-dim ml-2 tabular">
          {price !== undefined ? <>last {fmtUsd(price)}</> : "no quote"}
          {estimate !== undefined ? <> · est {fmtUsd(estimate)}</> : null}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <button
            data-testid="trade-buy"
            disabled={busy}
            onClick={() => fire("buy")}
            className="px-4 py-1.5 text-xs font-display tracking-[0.18em] uppercase bg-accent-purple/20 border border-accent-purple text-accent-purple hover:bg-accent-purple hover:text-white transition-colors disabled:opacity-50"
          >
            Buy
          </button>
          <button
            data-testid="trade-sell"
            disabled={busy}
            onClick={() => fire("sell")}
            className="px-4 py-1.5 text-xs font-display tracking-[0.18em] uppercase bg-tick-down/10 border border-tick-down/60 text-tick-down hover:bg-tick-down hover:text-white transition-colors disabled:opacity-50"
          >
            Sell
          </button>
        </div>
      </div>
      {msg ? (
        <div
          data-testid="trade-msg"
          className={`px-3 py-1.5 text-2xs tracking-widest border-t border-line ${
            msg.kind === "ok" ? "text-tick-up" : "text-tick-down"
          }`}
        >
          {msg.text.toUpperCase()}
        </div>
      ) : null}
    </Panel>
  );
}
