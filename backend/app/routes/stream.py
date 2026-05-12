"""SSE price stream.

We snapshot the market source's in-memory price cache at ~500ms intervals
and push an event per ticker. This is simpler than per-subscriber queues
and gives every client the same view of the world.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.db import list_watchlist
from app.deps import get_db, get_market
from app.market import MarketSource

router = APIRouter(prefix="/stream", tags=["stream"])

TICK_INTERVAL_S = 0.5


@router.get("/prices")
async def stream_prices(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
    market: MarketSource = Depends(get_market),
):
    tickers = [r["ticker"] for r in list_watchlist(conn)]

    async def gen():
        last_ts: dict[str, float] = {}
        while True:
            if await request.is_disconnected():
                break
            for ticker in tickers:
                tick = market.latest(ticker)
                if tick is None:
                    continue
                if last_ts.get(ticker) == tick.timestamp:
                    continue
                last_ts[ticker] = tick.timestamp
                yield {"event": "price", "data": json.dumps(tick.to_sse_dict())}
            await asyncio.sleep(TICK_INTERVAL_S)

    return EventSourceResponse(gen())
