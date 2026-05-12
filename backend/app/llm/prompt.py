"""Prompt assembly: system prompt, portfolio context, and chat history."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db import DEFAULT_USER_ID, list_chat_messages, list_watchlist
from app.market import MarketSource
from app.portfolio import build_portfolio

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant inside a simulated trading workstation.

You help the user:
- analyse their portfolio (composition, P&L, concentration, risk)
- discuss tickers on their watchlist
- execute trades on their behalf when asked, or proactively suggest them
- manage their watchlist (add or remove tickers)

Rules:
- Trades are market orders at the live price. No fees. Fractional shares allowed.
- Buys require sufficient cash. Sells require sufficient owned shares.
- Be concise, data-driven, and direct. Plain text only — no markdown headers.
- Always respond with valid JSON matching the required schema.
- Put trades in the `trades` array and watchlist changes in `watchlist_changes`.
- If the user just chats, return an empty `trades` list and an empty `watchlist_changes` list.
- Tickers must be uppercase.
"""

HISTORY_LIMIT = 10


def build_portfolio_context(
    conn: sqlite3.Connection,
    market: MarketSource,
    user_id: str = DEFAULT_USER_ID,
) -> str:
    """Render the user's portfolio + watchlist as a compact text block."""
    portfolio = build_portfolio(conn, market, user_id)
    watch_rows = list_watchlist(conn, user_id)
    watchlist: list[dict[str, Any]] = []
    for r in watch_rows:
        tick = market.latest(r["ticker"])
        watchlist.append({
            "ticker": r["ticker"],
            "price": round(tick.price, 4) if tick else None,
            "change_pct": round(tick.change_pct, 4) if tick else None,
        })
    block = {
        "cash_balance": portfolio["cash_balance"],
        "total_value": portfolio["total_value"],
        "positions": portfolio["positions"],
        "watchlist": watchlist,
    }
    return "PORTFOLIO CONTEXT:\n" + json.dumps(block, indent=2)


def build_messages(
    conn: sqlite3.Connection,
    market: MarketSource,
    user_message: str,
    user_id: str = DEFAULT_USER_ID,
    history_limit: int = HISTORY_LIMIT,
) -> list[dict[str, str]]:
    """Assemble the full message list for LiteLLM."""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": build_portfolio_context(conn, market, user_id)},
    ]
    for m in list_chat_messages(conn, limit=history_limit, user_id=user_id):
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages
