"""Fixtures for LLM tests.

Reuses the StubMarket from tests/api/conftest.py to keep trade execution
deterministic. Each test runs with LLM_MOCK=true.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import ensure_initialized
from app.deps import get_db, get_market
from app.market import MarketSource
from app.market.models import PriceTick


class StubMarket(MarketSource):
    def __init__(self, prices: dict[str, float] | None = None) -> None:
        self._prices: dict[str, PriceTick] = {}
        self._tickers: list[str] = []
        if prices:
            for t, p in prices.items():
                self.set_price(t, p)

    def set_price(self, ticker: str, price: float) -> None:
        ticker = ticker.upper()
        prev = self._prices.get(ticker)
        prev_price = prev.price if prev else price
        prev_close = prev.prev_close if prev else price
        self._prices[ticker] = PriceTick(
            ticker=ticker, price=price, prev_price=prev_price, prev_close=prev_close, timestamp=0.0
        )

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def set_tickers(self, tickers: list[str]) -> None:
        self._tickers = [t.upper() for t in tickers]
        for t in self._tickers:
            if t not in self._prices:
                self.set_price(t, 100.0)

    def latest(self, ticker: str) -> PriceTick | None:
        return self._prices.get(ticker.upper())

    async def subscribe(self) -> AsyncIterator[PriceTick]:  # type: ignore[override]
        if False:
            yield  # pragma: no cover


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    p = tmp_path / "finally.db"
    conn = ensure_initialized(p)
    conn.close()
    return p


@pytest.fixture
def market() -> StubMarket:
    return StubMarket({
        "AAPL": 200.0, "GOOGL": 150.0, "MSFT": 400.0, "PYPL": 70.0, "TSLA": 250.0,
    })


@pytest.fixture
def client(db_path: Path, market: StubMarket) -> TestClient:
    from fastapi import FastAPI
    from app.routes import chat, portfolio, watchlist

    app = FastAPI()
    app.include_router(chat.router, prefix="/api")
    app.include_router(portfolio.router, prefix="/api")
    app.include_router(watchlist.router, prefix="/api")
    app.state.db_path = str(db_path)
    app.state.market = market
    app.dependency_overrides[get_market] = lambda: market
    return TestClient(app)
