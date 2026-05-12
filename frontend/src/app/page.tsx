"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { PriceProvider, usePrices } from "@/lib/prices";
import { api } from "@/lib/api";
import type { ChatMessage, Portfolio, PortfolioSnapshot, WatchlistEntry } from "@/lib/types";
import { Header } from "@/components/Header";
import { Watchlist } from "@/components/Watchlist";
import { MainChart } from "@/components/MainChart";
import { Heatmap } from "@/components/Heatmap";
import { PLChart } from "@/components/PLChart";
import { Positions, deriveLive } from "@/components/Positions";
import { TradeBar } from "@/components/TradeBar";
import { ChatPanel } from "@/components/ChatPanel";

export default function Page() {
  return (
    <PriceProvider>
      <Workstation />
    </PriceProvider>
  );
}

function Workstation() {
  const { prices, status, ticks } = usePrices();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [snapshots, setSnapshots] = useState<PortfolioSnapshot[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatBusy, setChatBusy] = useState(false);
  const [chatOpen, setChatOpen] = useState(true);

  const refreshPortfolio = useCallback(async () => {
    try {
      setPortfolio(await api.portfolio());
    } catch {
      /* backend may not be up yet */
    }
  }, []);

  const refreshWatchlist = useCallback(async () => {
    try {
      const items = await api.watchlist();
      setWatchlist(items);
      setSelected((prev) => prev ?? items[0]?.ticker ?? null);
    } catch {
      /* swallow */
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      const snaps = await api.history();
      setSnapshots(snaps);
    } catch {
      /* swallow */
    }
  }, []);

  useEffect(() => {
    refreshPortfolio();
    refreshWatchlist();
    refreshHistory();
    const i = setInterval(() => {
      refreshPortfolio();
      refreshHistory();
    }, 8000);
    return () => clearInterval(i);
  }, [refreshPortfolio, refreshWatchlist, refreshHistory]);

  const livePositions = useMemo(() => {
    if (!portfolio) return [];
    return portfolio.positions.map((p) => deriveLive(p, prices[p.ticker]?.price));
  }, [portfolio, prices]);

  const liveTotals = useMemo(() => {
    if (!portfolio) return { total: 0, pl: 0, plPct: 0, cash: 0 };
    const mvSum = livePositions.reduce((s, p) => s + p.market_value, 0);
    const plSum = livePositions.reduce((s, p) => s + p.unrealized_pl, 0);
    const cost = livePositions.reduce((s, p) => s + p.avg_cost * p.quantity, 0);
    return {
      total: mvSum + portfolio.cash_balance,
      pl: plSum,
      plPct: cost === 0 ? 0 : plSum / cost,
      cash: portfolio.cash_balance,
    };
  }, [livePositions, portfolio]);

  const onTrade = useCallback(
    async (ticker: string, side: "buy" | "sell", quantity: number) => {
      const r = await api.trade(ticker, side, quantity).catch((e) => ({ ok: false as const, error: (e as Error).message }));
      if (r.ok) {
        await refreshPortfolio();
        await refreshHistory();
      }
      return r;
    },
    [refreshPortfolio, refreshHistory],
  );

  const onAddWatch = useCallback(
    async (ticker: string) => {
      await api.addWatch(ticker).catch(() => {});
      await refreshWatchlist();
    },
    [refreshWatchlist],
  );

  const onRemoveWatch = useCallback(
    async (ticker: string) => {
      await api.removeWatch(ticker).catch(() => {});
      await refreshWatchlist();
      if (selected === ticker) setSelected(null);
    },
    [refreshWatchlist, selected],
  );

  const onSendChat = useCallback(
    async (text: string) => {
      const userMsg: ChatMessage = {
        id: `local-${Date.now()}`,
        role: "user",
        content: text,
        created_at: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setChatBusy(true);
      try {
        const r = await api.chat(text);
        const assistant: ChatMessage = {
          ...r.message,
          actions: r.actions ?? r.message.actions ?? null,
        };
        setMessages((prev) => [...prev, assistant]);
        await refreshPortfolio();
        await refreshWatchlist();
      } catch (e) {
        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: `connection error: ${(e as Error).message}`,
            created_at: Date.now(),
          },
        ]);
      } finally {
        setChatBusy(false);
      }
    },
    [refreshPortfolio, refreshWatchlist],
  );

  return (
    <div className="min-h-screen flex flex-col relative z-[2]">
      <Header
        totalValue={liveTotals.total}
        cash={liveTotals.cash}
        pl={liveTotals.pl}
        plPct={liveTotals.plPct}
        status={status}
        ticks={ticks}
      />

      <main
        className={`flex-1 grid gap-3 p-3 grid-cols-12 ${
          chatOpen ? "lg:grid-cols-[280px_1fr_360px]" : "lg:grid-cols-[280px_1fr]"
        } auto-rows-min`}
      >
        {/* LEFT COLUMN */}
        <div className="col-span-12 lg:col-span-1 lg:row-span-2 flex flex-col gap-3 min-w-0 lg:min-w-[280px]">
          <Watchlist
            items={watchlist}
            selected={selected}
            onSelect={setSelected}
            onAdd={onAddWatch}
            onRemove={onRemoveWatch}
          />
          <Heatmap positions={livePositions} />
        </div>

        {/* CENTER COLUMN */}
        <div className="col-span-12 lg:col-span-1 flex flex-col gap-3 min-w-0">
          <div className="grid grid-rows-[minmax(320px,1fr)_minmax(200px,auto)] gap-3">
            <MainChart ticker={selected} />
            <PLChart snapshots={snapshots} />
          </div>
          <Positions positions={livePositions} onSelect={setSelected} />
          <TradeBar defaultTicker={selected} onSubmit={onTrade} />
        </div>

        {/* RIGHT COLUMN */}
        {chatOpen ? (
          <div className="col-span-12 lg:col-span-1 lg:row-span-2 min-h-[480px] lg:h-[calc(100vh-96px)] lg:sticky lg:top-3">
            <ChatPanel
              messages={messages}
              busy={chatBusy}
              onSend={onSendChat}
              open={chatOpen}
              onToggle={() => setChatOpen(false)}
            />
          </div>
        ) : (
          <ChatPanel
            messages={messages}
            busy={chatBusy}
            onSend={onSendChat}
            open={false}
            onToggle={() => setChatOpen(true)}
          />
        )}
      </main>

      <footer className="border-t border-line px-3 py-1.5 text-2xs text-text-dim flex items-center justify-between">
        <span>FINALLY · SIMULATED ACCOUNT · MARKET ORDERS · INSTANT FILL</span>
        <span className="tabular">{new Date().getUTCFullYear()} · BUILT BY AGENTS</span>
      </footer>
    </div>
  );
}
