"use client";

import { fmtUsd, fmtPct } from "@/lib/format";
import { StatusDot } from "./StatusDot";
import type { ConnStatus } from "@/lib/types";

type Props = {
  totalValue: number;
  cash: number;
  pl: number;
  plPct: number;
  status: ConnStatus;
  ticks: number;
};

export function Header({ totalValue, cash, pl, plPct, status, ticks }: Props) {
  const positive = pl >= 0;
  return (
    <header className="relative z-10 border-b border-line bg-bg-deep/80 backdrop-blur">
      <div className="flex items-stretch">
        <div className="flex items-center gap-3 px-5 py-2.5 border-r border-line">
          <div className="flex flex-col leading-tight">
            <span className="font-display tracking-[0.32em] text-accent-yellow text-xs">FIN /// ALLY</span>
            <span className="text-2xs text-text-dim tracking-widest">AI TRADING WORKSTATION</span>
          </div>
        </div>

        <Stat label="EQUITY" mono>
          <span data-testid="total-value" className="text-text-primary text-base font-medium tabular">
            {fmtUsd(totalValue)}
          </span>
        </Stat>
        <Stat label="P&L (UNREAL)">
          <span className={`text-base font-medium tabular ${positive ? "text-tick-up" : "text-tick-down"}`}>
            {fmtUsd(pl, { signed: true })} <span className="text-2xs ml-1 opacity-80">{fmtPct(plPct)}</span>
          </span>
        </Stat>
        <Stat label="CASH">
          <span data-testid="cash-balance" className="text-text-primary text-base tabular">
            {fmtUsd(cash)}
          </span>
        </Stat>

        <div className="ml-auto flex items-center gap-5 px-5">
          <div className="flex items-center gap-2 text-2xs text-text-dim">
            <span className="kbd">TICKS</span>
            <span className="tabular text-text-muted">{ticks.toString().padStart(6, "0")}</span>
          </div>
          <StatusDot status={status} />
        </div>
      </div>
      <div className="h-[2px] stripes" />
    </header>
  );
}

function Stat({ label, children, mono }: { label: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className={`px-5 py-2 border-r border-line flex flex-col gap-0.5 ${mono ? "" : ""}`}>
      <span className="panel-title">{label}</span>
      {children}
    </div>
  );
}
