"""Portfolio business logic: trade execution and valuation.

These helpers operate on a sqlite3.Connection plus a MarketSource so the
same code is reused by REST trades and LLM-driven trades.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import (
    DEFAULT_USER_ID,
    delete_position,
    get_position,
    get_user,
    insert_snapshot,
    insert_trade,
    list_positions,
    update_cash,
    upsert_position,
)
from app.market import MarketSource


class TradeError(ValueError):
    """Raised for any user-correctable trade failure (bad input, insufficient funds)."""


def _current_price(market: MarketSource, ticker: str) -> float | None:
    tick = market.latest(ticker)
    return tick.price if tick else None


def execute_trade(
    conn: sqlite3.Connection,
    market: MarketSource,
    ticker: str,
    side: str,
    quantity: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    """Execute a market order at the current price.

    Updates cash, upserts the position (weighted average cost), records a
    trade row, then writes a portfolio snapshot. Returns the executed trade
    plus the new cash balance.
    """
    side = side.lower()
    if side not in ("buy", "sell"):
        raise TradeError("side must be 'buy' or 'sell'")
    if quantity <= 0:
        raise TradeError("quantity must be positive")

    ticker = ticker.upper()
    price = _current_price(market, ticker)
    if price is None:
        raise TradeError(f"no live price available for {ticker}")

    user = get_user(conn, user_id)
    if user is None:
        raise TradeError("user profile not found")
    cash: float = user["cash_balance"]
    notional = price * quantity

    pos = get_position(conn, ticker, user_id)

    if side == "buy":
        if notional > cash + 1e-9:
            raise TradeError(
                f"insufficient cash: need ${notional:.2f}, have ${cash:.2f}"
            )
        new_cash = cash - notional
        if pos:
            old_qty = pos["quantity"]
            old_avg = pos["avg_cost"]
            new_qty = old_qty + quantity
            new_avg = (old_qty * old_avg + quantity * price) / new_qty
            upsert_position(conn, ticker, new_qty, new_avg, user_id)
        else:
            upsert_position(conn, ticker, quantity, price, user_id)
    else:  # sell
        if pos is None or pos["quantity"] < quantity - 1e-9:
            owned = pos["quantity"] if pos else 0.0
            raise TradeError(
                f"insufficient shares: want to sell {quantity} {ticker}, own {owned}"
            )
        new_cash = cash + notional
        new_qty = pos["quantity"] - quantity
        if new_qty <= 1e-9:
            delete_position(conn, ticker, user_id)
        else:
            upsert_position(conn, ticker, new_qty, pos["avg_cost"], user_id)

    update_cash(conn, new_cash, user_id)
    trade = insert_trade(conn, ticker, side, quantity, price, user_id)

    total_value = snapshot_total_value(conn, market, user_id)
    insert_snapshot(conn, total_value, user_id)

    return {"trade": trade, "cash_balance": new_cash, "total_value": total_value}


def snapshot_total_value(
    conn: sqlite3.Connection,
    market: MarketSource,
    user_id: str = DEFAULT_USER_ID,
) -> float:
    """Compute total portfolio value = cash + sum(qty * current_price)."""
    user = get_user(conn, user_id)
    cash: float = user["cash_balance"] if user else 0.0
    total = cash
    for pos in list_positions(conn, user_id):
        price = _current_price(market, pos["ticker"]) or pos["avg_cost"]
        total += pos["quantity"] * price
    return round(total, 2)


def build_portfolio(
    conn: sqlite3.Connection,
    market: MarketSource,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    """Build the /api/portfolio response: cash, positions with P&L, totals."""
    user = get_user(conn, user_id)
    cash: float = user["cash_balance"] if user else 0.0
    positions_out: list[dict[str, Any]] = []
    positions_value = 0.0
    for pos in list_positions(conn, user_id):
        ticker = pos["ticker"]
        qty = pos["quantity"]
        avg = pos["avg_cost"]
        price = _current_price(market, ticker) or avg
        market_value = qty * price
        cost_basis = qty * avg
        unrealized = market_value - cost_basis
        change_pct = (unrealized / cost_basis * 100.0) if cost_basis else 0.0
        positions_value += market_value
        positions_out.append({
            "ticker": ticker,
            "quantity": qty,
            "avg_cost": round(avg, 4),
            "current_price": round(price, 4),
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized, 2),
            "change_pct": round(change_pct, 4),
        })
    total_value = round(cash + positions_value, 2)
    return {
        "cash_balance": round(cash, 2),
        "positions": positions_out,
        "positions_value": round(positions_value, 2),
        "total_value": total_value,
    }
