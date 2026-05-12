"""FastAPI application entry point.

Lifespan responsibilities:
1. Initialize the SQLite database (schema + seeds).
2. Build the market source (simulator or Massive) and start it with the
   current watchlist tickers.
3. Run a background task that writes portfolio_snapshots every 30s.
4. Stop the market source and snapshot task on shutdown.

Routes are mounted under /api/* and the frontend static export is mounted
at / when FRONTEND_DIST exists.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import (
    connect,
    ensure_initialized,
    insert_snapshot,
    list_watchlist,
)
from app.market import build_market_source
from app.portfolio import snapshot_total_value
from app.routes import health, portfolio, stream, watchlist

SNAPSHOT_INTERVAL_S = 30.0


async def _snapshot_loop(app: FastAPI) -> None:
    """Write a portfolio_snapshot every 30s while the app runs."""
    while True:
        try:
            await asyncio.sleep(SNAPSHOT_INTERVAL_S)
            conn = connect(app.state.db_path)
            try:
                total = snapshot_total_value(conn, app.state.market)
                insert_snapshot(conn, total)
            finally:
                conn.close()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Don't let a transient DB or market hiccup kill the loop.
            await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_path = os.environ.get("DB_PATH") or None

    conn = ensure_initialized(app.state.db_path)
    try:
        tickers = [r["ticker"] for r in list_watchlist(conn)]
    finally:
        conn.close()

    market = build_market_source()
    await market.set_tickers(tickers)
    await market.start()
    app.state.market = market

    snapshot_task = asyncio.create_task(_snapshot_loop(app))

    try:
        yield
    finally:
        snapshot_task.cancel()
        try:
            await snapshot_task
        except (asyncio.CancelledError, Exception):
            pass
        await market.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)

app.include_router(health.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")
app.include_router(stream.router, prefix="/api")

# Optional chat router (owned by llm-engineer). Mount if importable.
try:
    from app.routes import chat as _chat  # type: ignore[attr-defined]
    app.include_router(_chat.router, prefix="/api")
except Exception:
    pass


_frontend_dist = Path(os.environ.get("FRONTEND_DIST", "frontend/out"))
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
