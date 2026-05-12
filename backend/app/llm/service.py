"""Chat orchestration: load context, call LLM, auto-execute, persist."""

from __future__ import annotations

import os
import sqlite3
from typing import Any

from fastapi import Request

from app.db import (
    DEFAULT_USER_ID,
    add_watchlist,
    insert_chat_message,
    remove_watchlist,
)
from app.market import MarketSource
from app.portfolio import TradeError, execute_trade

from .client import call_llm
from .mock import mock_response
from .prompt import build_messages
from .schema import ChatResponse


def _is_mock() -> bool:
    return os.environ.get("LLM_MOCK", "").lower() == "true"


async def process_message(
    conn: sqlite3.Connection,
    market: MarketSource,
    user_message: str,
    request: Request | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    """Handle one user chat turn.

    Flow:
      1. Persist the user message.
      2. Call the LLM (real or mock) with system prompt + portfolio + history.
      3. Auto-execute each requested trade; collect successes + errors.
      4. Auto-apply watchlist changes; resync the market source's tickers.
      5. Persist the assistant message with an ``actions`` payload.
      6. Return the combined response for the route to serialise.
    """
    insert_chat_message(conn, "user", user_message, user_id=user_id)

    if _is_mock():
        chat: ChatResponse = mock_response(user_message)
    else:
        messages = build_messages(conn, market, user_message, user_id=user_id)
        chat = call_llm(messages)

    executed_trades: list[dict[str, Any]] = []
    errors: list[str] = []

    for trade in chat.trades:
        try:
            result = execute_trade(
                conn, market, trade.ticker, trade.side, trade.quantity, user_id=user_id
            )
            executed_trades.append(result["trade"])
        except TradeError as e:
            errors.append(f"{trade.side} {trade.quantity} {trade.ticker}: {e}")

    applied_watchlist: list[dict[str, str]] = []
    watchlist_changed = False
    for change in chat.watchlist_changes:
        ticker = change.ticker.upper()
        if change.action == "add":
            add_watchlist(conn, ticker, user_id=user_id)
            applied_watchlist.append({"ticker": ticker, "action": "add"})
            watchlist_changed = True
        else:
            removed = remove_watchlist(conn, ticker, user_id=user_id)
            if removed:
                applied_watchlist.append({"ticker": ticker, "action": "remove"})
                watchlist_changed = True
            else:
                errors.append(f"remove {ticker}: not in watchlist")

    if watchlist_changed and request is not None:
        await _resync_market(request, conn)

    actions = {
        "executed_trades": executed_trades,
        "watchlist_changes": applied_watchlist,
        "errors": errors,
    }
    insert_chat_message(conn, "assistant", chat.message, actions=actions, user_id=user_id)

    return {
        "message": chat.message,
        "trades": [t.model_dump() for t in chat.trades],
        "watchlist_changes": [c.model_dump() for c in chat.watchlist_changes],
        "executed_trades": executed_trades,
        "applied_watchlist_changes": applied_watchlist,
        "errors": errors,
    }


async def _resync_market(request: Request, conn: sqlite3.Connection) -> None:
    """After watchlist mutations, push the new ticker set to the market source."""
    from app.db import list_watchlist
    market: MarketSource = request.app.state.market
    tickers = [r["ticker"] for r in list_watchlist(conn)]
    await market.set_tickers(tickers)
