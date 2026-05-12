"""Watchlist REST endpoints."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.db import add_watchlist, list_watchlist, remove_watchlist
from app.deps import get_db, get_market
from app.market import MarketSource

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistAdd(BaseModel):
    ticker: str = Field(min_length=1)


def _enrich(market: MarketSource, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        tick = market.latest(r["ticker"])
        out.append({
            "ticker": r["ticker"],
            "added_at": r["added_at"],
            "price": tick.price if tick else None,
            "prev_close": tick.prev_close if tick else None,
            "change_pct": round(tick.change_pct, 4) if tick else None,
            "direction": tick.direction if tick else "flat",
        })
    return out


async def _sync_market_tickers(request: Request, conn: sqlite3.Connection) -> None:
    market: MarketSource = request.app.state.market
    tickers = [r["ticker"] for r in list_watchlist(conn)]
    await market.set_tickers(tickers)


@router.get("")
def get_watchlist(
    conn: sqlite3.Connection = Depends(get_db),
    market: MarketSource = Depends(get_market),
) -> list[dict[str, Any]]:
    return _enrich(market, list_watchlist(conn))


@router.post("")
async def post_watchlist(
    payload: WatchlistAdd,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
    market: MarketSource = Depends(get_market),
) -> dict[str, Any]:
    row = add_watchlist(conn, payload.ticker)
    await _sync_market_tickers(request, conn)
    return {
        "ticker": row["ticker"],
        "added_at": row["added_at"],
        "price": None,
        "prev_close": None,
        "change_pct": None,
        "direction": "flat",
    }


@router.delete("/{ticker}")
async def delete_ticker(
    ticker: str,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, str]:
    if not remove_watchlist(conn, ticker):
        raise HTTPException(status_code=404, detail=f"{ticker.upper()} not in watchlist")
    await _sync_market_tickers(request, conn)
    return {"ticker": ticker.upper(), "status": "removed"}
