"""Shared fixtures for API tests.

Each test gets a fresh SQLite DB and a stub MarketSource so trades execute
deterministically without spinning up the simulator background task.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import ensure_initialized
from app.deps import get_db, get_market
from app.market import MarketSource
from app.market.models import PriceTick


class StubMarket(MarketSource):
    """In-memory market source with hand-set prices. No background task."""

    def __init__(self, prices: dict[str, float] | None = None) -> None:
        self._prices: dict[str, PriceTick] = {}
        if prices:
            for t, p in prices.items():
                self.set_price(t, p)

    def set_price(self, ticker: str, price: float, prev_close: float | None = None) -> None:
        ticker = ticker.upper()
        prev = self._prices.get(ticker)
        prev_price = prev.price if prev else (prev_close if prev_close is not None else price)
        pc = prev_close if prev_close is not None else (prev.prev_close if prev else price)
        self._prices[ticker] = PriceTick(
            ticker=ticker, price=price, prev_price=prev_price, prev_close=pc, timestamp=0.0
        )

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def set_tickers(self, tickers: list[str]) -> None:
        for t in tickers:
            t = t.upper()
            if t not in self._prices:
                self.set_price(t, 100.0)

    def latest(self, ticker: str) -> PriceTick | None:
        return self._prices.get(ticker.upper())

    async def subscribe(self) -> AsyncIterator[PriceTick]:  # type: ignore[override]
        # Not used by route tests.
        if False:
            yield  # pragma: no cover


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "finally.db"
    conn = ensure_initialized(p)
    conn.close()
    return p


@pytest.fixture
def market() -> StubMarket:
    return StubMarket({
        "AAPL": 200.0, "GOOGL": 150.0, "MSFT": 400.0, "AMZN": 180.0, "TSLA": 250.0,
        "NVDA": 900.0, "META": 480.0, "JPM": 200.0, "V": 280.0, "NFLX": 600.0,
    })


@pytest.fixture
def client(db_path: Path, market: StubMarket) -> TestClient:
    """Build a TestClient that bypasses the real lifespan.

    We avoid the live simulator and snapshot loop and inject our deps so each
    test owns its DB and price set.
    """
    from fastapi import FastAPI

    from app.routes import health, portfolio, stream, watchlist

    app = FastAPI()
    app.include_router(health.router, prefix="/api")
    app.include_router(portfolio.router, prefix="/api")
    app.include_router(watchlist.router, prefix="/api")
    app.include_router(stream.router, prefix="/api")
    app.state.db_path = str(db_path)
    app.state.market = market
    app.dependency_overrides[get_market] = lambda: market
    return TestClient(app)
