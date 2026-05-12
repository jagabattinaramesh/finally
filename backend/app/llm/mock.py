"""Deterministic mock LLM responses for LLM_MOCK=true.

Pattern-matches the user message and returns a ``ChatResponse`` with the
expected trade or watchlist change. Used by E2E tests and offline dev.
"""

from __future__ import annotations

import re

from .schema import ChatResponse, Trade, WatchlistChange

_BUY = re.compile(r"\bbuy\s+(\d+(?:\.\d+)?)\s+(?:shares?\s+of\s+)?([A-Za-z]{1,5})\b", re.I)
_SELL = re.compile(r"\bsell\s+(\d+(?:\.\d+)?)\s+(?:shares?\s+of\s+)?([A-Za-z]{1,5})\b", re.I)
_ADD = re.compile(r"\b(?:add|watch)\s+([A-Za-z]{1,5})\b(?!\s+shares?)", re.I)
_REMOVE = re.compile(r"\bremove\s+([A-Za-z]{1,5})\b", re.I)


def mock_response(user_message: str) -> ChatResponse:
    """Map a user message to a deterministic ChatResponse."""
    m = _BUY.search(user_message)
    if m:
        qty = float(m.group(1))
        ticker = m.group(2).upper()
        return ChatResponse(
            message=f"Buying {_fmt(qty)} shares of {ticker}.",
            trades=[Trade(ticker=ticker, side="buy", quantity=qty)],
        )

    m = _SELL.search(user_message)
    if m:
        qty = float(m.group(1))
        ticker = m.group(2).upper()
        return ChatResponse(
            message=f"Selling {_fmt(qty)} shares of {ticker}.",
            trades=[Trade(ticker=ticker, side="sell", quantity=qty)],
        )

    m = _ADD.search(user_message)
    if m:
        ticker = m.group(1).upper()
        return ChatResponse(
            message=f"Added {ticker} to your watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="add")],
        )

    m = _REMOVE.search(user_message)
    if m:
        ticker = m.group(1).upper()
        return ChatResponse(
            message=f"Removed {ticker} from your watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="remove")],
        )

    return ChatResponse(message="Mock LLM: I received your message.")


def _fmt(qty: float) -> str:
    """Render fractional quantities without trailing .0 on whole numbers."""
    return f"{int(qty)}" if qty == int(qty) else f"{qty}"
