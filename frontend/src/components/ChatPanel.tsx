"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronRight, Send, Sparkles } from "lucide-react";
import { Panel } from "./Panel";
import type { ChatActions, ChatMessage } from "@/lib/types";
import { fmtTime } from "@/lib/format";

type Props = {
  messages: ChatMessage[];
  busy: boolean;
  onSend: (text: string) => Promise<void>;
  open: boolean;
  onToggle: () => void;
};

export function ChatPanel({ messages, busy, onSend, open, onToggle }: Props) {
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const t = draft.trim();
    if (!t || busy) return;
    setDraft("");
    await onSend(t);
  }

  if (!open) {
    return (
      <button
        onClick={onToggle}
        data-testid="chat-toggle"
        aria-label="Open AI chat"
        className="fixed right-3 bottom-3 z-20 panel corners px-3 py-2 flex items-center gap-2 hover:border-accent-yellow"
      >
        <span className="c1" />
        <span className="c2" />
        <Sparkles size={14} className="text-accent-yellow" />
        <span className="panel-title">FinAlly Assistant</span>
        <ChevronRight size={14} className="text-text-muted rotate-180" />
      </button>
    );
  }

  return (
    <aside
      data-testid="chat-panel"
      className="panel corners flex flex-col h-full min-h-0"
    >
      <span className="c1" />
      <span className="c2" />
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-line">
        <div className="flex items-center gap-2">
          <Sparkles size={12} className="text-accent-yellow" />
          <span className="panel-title">FinAlly Assistant</span>
        </div>
        <button onClick={onToggle} className="text-text-dim hover:text-text-primary" aria-label="Collapse chat">
          <ChevronRight size={14} />
        </button>
      </header>

      <div ref={listRef} className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
        {messages.length === 0 ? (
          <div className="text-text-dim text-xs leading-relaxed">
            <span className="text-accent-yellow">&gt;</span> Ask about your portfolio, request a trade, or have me
            manage your watchlist. I respond with structured actions auto-executed against your simulated account.
          </div>
        ) : null}
        {messages.map((m) => (
          <MessageBubble key={m.id} m={m} />
        ))}
        {busy ? (
          <div className="text-text-dim text-xs tracking-widest">
            FINALLY THINKING<span className="dots" />
          </div>
        ) : null}
      </div>

      <form onSubmit={submit} className="border-t border-line p-2 flex items-center gap-2">
        <span className="text-accent-yellow text-xs">&gt;</span>
        <input
          data-testid="chat-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="ask, analyze, trade..."
          className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-dim focus:outline-none"
        />
        <button
          data-testid="chat-send"
          type="submit"
          disabled={busy || !draft.trim()}
          aria-label="Send message"
          className="border border-accent-blue/40 text-accent-blue p-1.5 hover:bg-accent-blue hover:text-white disabled:opacity-30 transition-colors"
        >
          <Send size={12} />
        </button>
      </form>
    </aside>
  );
}

function MessageBubble({ m }: { m: ChatMessage }) {
  const isUser = m.role === "user";
  return (
    <div
      data-testid={`chat-message-${m.role}`}
      className={`text-sm leading-relaxed ${isUser ? "text-text-primary" : "text-text-primary"}`}
    >
      <div className="flex items-center gap-2 mb-0.5">
        <span
          className={`panel-title ${isUser ? "text-accent-blue" : "text-accent-yellow"}`}
        >
          {isUser ? "YOU" : "FINALLY"}
        </span>
        <span className="text-2xs text-text-dim tabular">{fmtTime(m.created_at)}</span>
      </div>
      <div className={`pl-1 border-l ${isUser ? "border-accent-blue/30" : "border-accent-yellow/30"} pl-3`}>
        <p className="whitespace-pre-wrap">{m.content}</p>
        {m.actions ? <ActionList actions={m.actions} /> : null}
      </div>
    </div>
  );
}

function ActionList({ actions }: { actions: ChatActions }) {
  const items: string[] = [];
  actions.trades?.forEach((t) =>
    items.push(`${(t.status ?? "filled").toUpperCase()} · ${t.side.toUpperCase()} ${t.quantity} ${t.ticker}`),
  );
  actions.watchlist_changes?.forEach((w) =>
    items.push(`WATCH ${w.action.toUpperCase()} ${w.ticker}${w.status ? ` · ${w.status}` : ""}`),
  );
  if (items.length === 0) return null;
  return (
    <ul className="mt-2 space-y-1 text-2xs tracking-widest">
      {items.map((it, i) => (
        <li
          key={i}
          data-testid="chat-trade-confirmation"
          className="border border-accent-yellow/30 bg-accent-yellow/5 px-2 py-1 text-accent-yellow"
        >
          {it}
        </li>
      ))}
    </ul>
  );
}
