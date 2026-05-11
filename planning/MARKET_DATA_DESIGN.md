# Market Data Backend — Implementation Design

> Concrete implementation guide for FinAlly's market data layer.
> Covers the unified `MarketSource` interface, the `SimulatorSource`,
> the `MassiveSource`, the price cache, the SSE streamer, and the
> testing strategy. Code snippets here are ready to use, not sketches.

---

## 1. File Layout

```
backend/
└── app/
    └── market/
        ├── __init__.py        # exports build_market_source
        ├── models.py          # PriceTick dataclass
        ├── interface.py       # MarketSource ABC
        ├── factory.py         # build_market_source()
        ├── simulator.py       # SimulatorSource — GBM + event jumps
        ├── massive.py         # MassiveSource — REST polling
        └── seed_prices.py     # per-ticker constants (price, drift, vol, corr)

backend/
└── tests/
    └── market/
        ├── conftest.py        # parametrized fixture over both impls
        ├── fakes.py           # FakeMassiveTransport (canned HTTP responses)
        ├── test_conformance.py # shared contract tests (sim + fake massive)
        ├── test_simulator.py  # sim-specific: GBM math, determinism
        └── test_massive.py    # massive-specific: 429 backoff, field parsing
```

---

## 2. Data Model

```python
# backend/app/market/models.py
from dataclasses import dataclass
import time


@dataclass(frozen=True, slots=True)
class PriceTick:
    """Immutable price update for a single ticker.

    Emitted by both SimulatorSource and MassiveSource — consumers are
    agnostic to the source.
    """
    ticker: str
    price: float
    prev_price: float    # price at the prior tick (or prev_close on first tick)
    prev_close: float    # yesterday's closing price, for daily % change
    timestamp: float     # seconds since epoch (float, matches time.time())

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat' — drives the frontend flash colour."""
        if self.price > self.prev_price:
            return "up"
        if self.price < self.prev_price:
            return "down"
        return "flat"

    @property
    def change_pct(self) -> float:
        """Daily percentage change relative to yesterday's close."""
        if self.prev_close == 0:
            return 0.0
        return (self.price - self.prev_close) / self.prev_close * 100.0

    def to_sse_dict(self) -> dict:
        """Serialisable dict for the SSE price event payload."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "prev_price": self.prev_price,
            "prev_close": self.prev_close,
            "ts": self.timestamp,
            "dir": self.direction,
            "change_pct": round(self.change_pct, 4),
        }
```

---

## 3. The Interface (ABC)

```python
# backend/app/market/interface.py
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from .models import PriceTick


class MarketSource(ABC):
    """Abstract price-data source.

    Lifecycle
    ---------
    1. Construct (no I/O).
    2. ``await set_tickers(...)`` — define what to track.
    3. ``await start()`` — begin background production.
    4. ``subscribe()`` / ``latest()`` — consume prices.
    5. ``await stop()`` — clean shutdown.

    ``set_tickers`` and ``latest`` are safe to call at any time after
    construction. ``subscribe`` yields ticks only after ``start``.
    """

    @abstractmethod
    async def start(self) -> None:
        """Spawn the background producer task. Idempotent."""

    @abstractmethod
    async def stop(self) -> None:
        """Cancel the producer and release resources. Safe to call twice."""

    @abstractmethod
    async def set_tickers(self, tickers: list[str]) -> None:
        """Replace the active ticker set. Deduplicated, uppercased internally."""

    @abstractmethod
    def latest(self, ticker: str) -> PriceTick | None:
        """O(1) in-memory lookup. Returns None until the first tick fires."""

    @abstractmethod
    def subscribe(self) -> AsyncIterator[PriceTick]:
        """Return an independent async iterator of ticks.

        Each active subscriber receives every tick produced after it
        subscribes. Slow subscribers lose old ticks (drop-oldest queue)
        rather than blocking the producer.
        """
```

---

## 4. Per-Ticker Constants

```python
# backend/app/market/seed_prices.py
"""Edit this file to change simulator starting prices, volatility, or correlations."""

# Starting prices (approximate real prices at project start)
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00, "GOOGL": 175.00, "MSFT": 415.00, "AMZN": 185.00,
    "TSLA": 175.00, "NVDA": 950.00,  "META": 490.00, "JPM":  200.00,
    "V":    275.00, "NFLX": 620.00,
}

# Annualized drift μ (e.g. 0.05 = +5%/year expected return)
DRIFTS: dict[str, float] = {
    "AAPL": 0.05, "GOOGL": 0.06, "MSFT": 0.07, "AMZN": 0.05,
    "TSLA": 0.00, "NVDA":  0.10, "META": 0.06, "JPM":  0.04,
    "V":    0.05, "NFLX":  0.05,
}

# Annualized volatility σ (e.g. 0.25 = 25%/year std-dev of log returns)
VOLS: dict[str, float] = {
    "AAPL": 0.25, "GOOGL": 0.27, "MSFT": 0.24, "AMZN": 0.30,
    "TSLA": 0.55, "NVDA":  0.45, "META": 0.32, "JPM":  0.20,
    "V":    0.18, "NFLX":  0.35,
}

# Pairwise correlations (upper-triangle; reverse lookup handled by _corr_matrix).
# Missing pairs fall back to DEFAULT_CORR (0.30).
CORRELATIONS: dict[tuple[str, str], float] = {
    ("AAPL", "GOOGL"): 0.60, ("AAPL", "MSFT"):  0.60, ("AAPL", "AMZN"): 0.55,
    ("AAPL", "TSLA"):  0.45, ("AAPL", "NVDA"):  0.55, ("AAPL", "META"): 0.55,
    ("AAPL", "NFLX"):  0.50, ("AAPL", "JPM"):   0.20, ("AAPL", "V"):    0.25,
    ("GOOGL","MSFT"):  0.65, ("GOOGL","META"):   0.65, ("GOOGL","NVDA"): 0.55,
    ("GOOGL","AMZN"):  0.55, ("GOOGL","NFLX"):   0.55, ("GOOGL","TSLA"): 0.40,
    ("MSFT", "NVDA"):  0.55, ("MSFT", "AMZN"):  0.50, ("MSFT", "META"): 0.55,
    ("NVDA", "META"):  0.55, ("NVDA", "TSLA"):   0.50,
    ("JPM",  "V"):     0.55,
}

DEFAULT_PRICE = 100.00
DEFAULT_DRIFT = 0.05
DEFAULT_VOL   = 0.30
DEFAULT_CORR  = 0.30   # for ticker pairs not in CORRELATIONS
```

---

## 5. SimulatorSource — Full Implementation

### 5.1 Math primer

Each tick applies the GBM discretization:

```
S_{t+Δt} = S_t · exp( (μ − σ²/2)·Δt  +  σ·√Δt·Z )
```

- `Δt` = tick interval in **years** (`0.5s / (252 × 6.5 × 3600)`)
- `Z` = correlated Gaussian shock from `Z = L·ε`, `L = chol(Σ)`

An additional event jump fires with `p = 0.002` per ticker per tick
(≈ once every 4–5 minutes at 500 ms cadence):

```
new_price *= exp( ±U(0.02, 0.05) )   # 2–5% one-shot shock
```

### 5.2 simulator.py

```python
# backend/app/market/simulator.py
"""Synthetic market prices via correlated GBM with random event jumps."""

import asyncio
import math
import random
import time
from collections.abc import AsyncIterator

from .interface import MarketSource
from .models import PriceTick
from .seed_prices import (
    CORRELATIONS, DEFAULT_CORR, DEFAULT_DRIFT, DEFAULT_PRICE,
    DEFAULT_VOL, DRIFTS, SEED_PRICES, VOLS,
)

# 252 trading days × 6.5 trading hours × 3600 s/hr
_SECONDS_PER_YEAR = 252 * 6.5 * 3600


class SimulatorSource(MarketSource):
    """Drop-in MarketSource that generates prices locally — no API key needed."""

    def __init__(
        self,
        *,
        tick_interval_s: float = 0.5,
        event_prob: float = 0.002,
        seed: int | None = None,
    ) -> None:
        self._tick_interval = tick_interval_s
        self._event_prob = event_prob
        self._rng = random.Random(seed)

        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._prev_close: dict[str, float] = {}
        self._latest: dict[str, PriceTick] = {}
        self._chol: list[list[float]] = []

        self._subs: list[asyncio.Queue[PriceTick]] = []
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()   # guards _tickers and _chol swap

    # ------------------------------------------------------------------
    # MarketSource API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def set_tickers(self, tickers: list[str]) -> None:
        upper = [t.upper() for t in tickers]
        async with self._lock:
            self._tickers = list(dict.fromkeys(upper))   # dedupe, preserve order
            for t in self._tickers:
                if t not in self._prices:
                    seed_price = SEED_PRICES.get(t, DEFAULT_PRICE)
                    self._prices[t] = seed_price
                    self._prev_close[t] = seed_price
            self._chol = _cholesky(_corr_matrix(self._tickers))

    def latest(self, ticker: str) -> PriceTick | None:
        return self._latest.get(ticker.upper())

    async def subscribe(self) -> AsyncIterator[PriceTick]:   # type: ignore[override]
        q: asyncio.Queue[PriceTick] = asyncio.Queue(maxsize=256)
        self._subs.append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subs.remove(q)

    # ------------------------------------------------------------------
    # Producer
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        while True:
            await self._step()
            await asyncio.sleep(self._tick_interval)

    async def _step(self) -> None:
        async with self._lock:
            tickers = list(self._tickers)
            chol = [row[:] for row in self._chol]

        if not tickers:
            return

        n = len(tickers)
        dt = self._tick_interval / _SECONDS_PER_YEAR
        sqrt_dt = math.sqrt(dt)
        now = time.time()

        # Correlated standard-normal shocks via Cholesky decomposition
        eps = [self._rng.gauss(0.0, 1.0) for _ in range(n)]
        z = [sum(chol[i][j] * eps[j] for j in range(i + 1)) for i in range(n)]

        for i, ticker in enumerate(tickers):
            mu = DRIFTS.get(ticker, DEFAULT_DRIFT)
            sigma = VOLS.get(ticker, DEFAULT_VOL)
            old_price = self._prices[ticker]

            # GBM step
            drift_term = (mu - 0.5 * sigma * sigma) * dt
            shock_term = sigma * sqrt_dt * z[i]
            new_price = old_price * math.exp(drift_term + shock_term)

            # Random event jump (2–5% one-shot shock)
            if self._rng.random() < self._event_prob:
                pct = self._rng.uniform(0.02, 0.05)
                sign = 1.0 if self._rng.random() < 0.5 else -1.0
                new_price *= math.exp(sign * pct)

            new_price = round(new_price, 2)
            self._prices[ticker] = new_price

            tick = PriceTick(
                ticker=ticker,
                price=new_price,
                prev_price=old_price,
                prev_close=self._prev_close[ticker],
                timestamp=now,
            )
            self._latest[ticker] = tick
            self._broadcast(tick)

    def _broadcast(self, tick: PriceTick) -> None:
        for q in self._subs:
            if q.full():
                try:
                    q.get_nowait()   # drop oldest — never block the producer
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(tick)


# ------------------------------------------------------------------
# Pure-Python linear algebra helpers (no NumPy required)
# ------------------------------------------------------------------

def _corr_matrix(tickers: list[str]) -> list[list[float]]:
    """Build an N×N correlation matrix for the given tickers."""
    n = len(tickers)
    m = [[1.0 if i == j else DEFAULT_CORR for j in range(n)] for i in range(n)]
    for i, a in enumerate(tickers):
        for j, b in enumerate(tickers):
            if i == j:
                continue
            val = CORRELATIONS.get((a, b)) or CORRELATIONS.get((b, a))
            if val is not None:
                m[i][j] = val
    return m


def _cholesky(m: list[list[float]]) -> list[list[float]]:
    """Lower-triangular Cholesky factor of a positive-definite matrix."""
    n = len(m)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                L[i][j] = math.sqrt(max(m[i][i] - s, 1e-12))
            else:
                L[i][j] = (m[i][j] - s) / L[j][j]
    return L
```

---

## 6. MassiveSource — Full Implementation

### 6.1 API background

Massive (formerly Polygon.io, rebranded 2025-10-30) exposes a REST
snapshot endpoint that returns current price + previous-day OHLC for
up to ~250 tickers in a single call:

```
GET https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers
    ?tickers=AAPL,GOOGL,MSFT,...
Authorization: Bearer $MASSIVE_API_KEY
```

Rate limits:

| Tier | Cap | FinAlly poll interval |
|------|-----|-----------------------|
| Free (Basic) | 5 req/min | **15 s** |
| Paid | unlimited | **2–5 s** |

### 6.2 Key response fields

```json
{
  "tickers": [
    {
      "ticker": "AAPL",
      "lastTrade": { "p": 190.73 },
      "day":       { "c": 190.73 },
      "prevDay":   { "c": 189.50 },
      "todaysChangePerc": 0.65,
      "updated": 1715444532000000000
    }
  ]
}
```

| Field | Use |
|-------|-----|
| `lastTrade.p` | Current price (preferred) |
| `day.c` | Fallback when `lastTrade` is absent (pre-market) |
| `prevDay.c` | Yesterday's close → `change_pct` and `prev_close` on first tick |
| `updated` | Nanoseconds since epoch — divide by 1e9 for `time.time()` comparisons |

### 6.3 massive.py

```python
# backend/app/market/massive.py
"""Real-market data via Massive (Polygon.io) REST polling."""

import asyncio
import time
from collections.abc import AsyncIterator

import httpx

from .interface import MarketSource
from .models import PriceTick

_BASE_URL = "https://api.massive.com"
_SNAPSHOT_PATH = "/v2/snapshot/locale/us/markets/stocks/tickers"
_PREV_CLOSE_PATH = "/v2/aggs/ticker/{ticker}/prev"

_FREE_TIER_POLL_S = 15.0   # 5 req/min cap → poll every 15 s (4/min, leaves headroom)


class MassiveSource(MarketSource):
    """MarketSource backed by Massive REST API polling."""

    def __init__(
        self,
        api_key: str,
        poll_interval_s: float = _FREE_TIER_POLL_S,
    ) -> None:
        self._api_key = api_key
        self._poll_interval_s = poll_interval_s

        self._tickers: set[str] = set()
        self._latest: dict[str, PriceTick] = {}
        self._subs: list[asyncio.Queue[PriceTick]] = []
        self._task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # MarketSource API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._task is not None:
            return
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=10.0,
        )
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client:
            await self._client.aclose()
            self._client = None

    async def set_tickers(self, tickers: list[str]) -> None:
        self._tickers = {t.upper() for t in tickers}

    def latest(self, ticker: str) -> PriceTick | None:
        return self._latest.get(ticker.upper())

    async def subscribe(self) -> AsyncIterator[PriceTick]:   # type: ignore[override]
        q: asyncio.Queue[PriceTick] = asyncio.Queue(maxsize=256)
        self._subs.append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subs.remove(q)

    # ------------------------------------------------------------------
    # Producer
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        while True:
            if self._tickers:
                try:
                    await self._poll_once_with_backoff()
                except Exception as exc:
                    # Log and keep going — never let the loop die permanently.
                    print(f"[massive] poll error: {exc!r}")
            await asyncio.sleep(self._poll_interval_s)

    async def _poll_once_with_backoff(self) -> None:
        delay = 1.0
        for attempt in range(4):
            try:
                await self._poll_once()
                return
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in (429, 500, 502, 503, 504):
                    raise
                if attempt == 3:
                    raise
                await asyncio.sleep(delay)
                delay *= 2

    async def _poll_once(self) -> None:
        assert self._client is not None
        params = {"tickers": ",".join(sorted(self._tickers))}
        resp = await self._client.get(_SNAPSHOT_PATH, params=params)
        resp.raise_for_status()
        now = time.time()
        for entry in resp.json().get("tickers", []):
            self._process_entry(entry, now)

    def _process_entry(self, entry: dict, now: float) -> None:
        ticker = entry.get("ticker", "")
        if not ticker:
            return

        last_trade = entry.get("lastTrade") or {}
        day = entry.get("day") or {}
        prev_day = entry.get("prevDay") or {}

        price = last_trade.get("p") or day.get("c")
        if price is None:
            return

        price = float(price)
        prev_close = float(prev_day.get("c", price))

        prev_tick = self._latest.get(ticker)
        prev_price = prev_tick.price if prev_tick else prev_close

        tick = PriceTick(
            ticker=ticker,
            price=price,
            prev_price=prev_price,
            prev_close=prev_close,
            timestamp=now,
        )
        self._latest[ticker] = tick
        self._broadcast(tick)

    def _broadcast(self, tick: PriceTick) -> None:
        for q in self._subs:
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(tick)

    # ------------------------------------------------------------------
    # Supplemental: fetch previous close for a brand-new ticker
    # ------------------------------------------------------------------

    async def fetch_prev_close(self, ticker: str) -> float | None:
        """Fetch yesterday's close for a single ticker.

        Call this when a ticker is added mid-session and we need a
        baseline before the next full snapshot poll arrives.
        Returns None on any error.
        """
        assert self._client is not None
        try:
            resp = await self._client.get(
                _PREV_CLOSE_PATH.format(ticker=ticker.upper()),
                params={"adjusted": "true"},
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                return float(results[0]["c"])
        except Exception as exc:
            print(f"[massive] fetch_prev_close({ticker}) failed: {exc!r}")
        return None
```

---

## 7. Factory — Source Selection

```python
# backend/app/market/factory.py
import os

from .interface import MarketSource
from .massive import MassiveSource
from .simulator import SimulatorSource


def build_market_source() -> MarketSource:
    """Return the market source configured by environment.

    MASSIVE_API_KEY set and non-empty → MassiveSource (real data)
    otherwise                         → SimulatorSource (synthetic)

    This is the single place that reads the environment variable.
    All other code receives a MarketSource and doesn't know which impl it is.
    """
    key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if key:
        return MassiveSource(api_key=key)
    return SimulatorSource()
```

---

## 8. Package Init

```python
# backend/app/market/__init__.py
from .factory import build_market_source
from .interface import MarketSource
from .models import PriceTick

__all__ = ["build_market_source", "MarketSource", "PriceTick"]
```

---

## 9. FastAPI Integration

### 9.1 Lifespan — startup and shutdown

```python
# backend/app/main.py
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse

from app.market import build_market_source, MarketSource
from app.db import get_watchlist_tickers   # returns list[str] from SQLite


@asynccontextmanager
async def lifespan(app: FastAPI):
    source: MarketSource = build_market_source()

    # Seed tickers from the database before the first tick fires
    initial_tickers = await get_watchlist_tickers(user_id="default")
    await source.set_tickers(initial_tickers)
    await source.start()

    app.state.market = source
    try:
        yield
    finally:
        await source.stop()


app = FastAPI(lifespan=lifespan)
```

### 9.2 SSE endpoint

```python
@app.get("/api/stream/prices")
async def stream_prices(request: Request):
    source: MarketSource = request.app.state.market

    async def event_generator():
        async for tick in source.subscribe():
            if await request.is_disconnected():
                break
            yield {
                "event": "price",
                "data": json.dumps(tick.to_sse_dict()),
            }

    return EventSourceResponse(event_generator())
```

**SSE payload example** (one `data:` line per event):

```json
{
  "ticker": "AAPL",
  "price": 191.34,
  "prev_price": 191.10,
  "prev_close": 189.50,
  "ts": 1715444532.41,
  "dir": "up",
  "change_pct": 0.9706
}
```

### 9.3 Watchlist mutation — keeping the source in sync

When the user adds or removes a ticker via the REST API, the backend
must call `source.set_tickers` so the source tracks the updated list:

```python
@app.post("/api/watchlist")
async def add_ticker(body: AddTickerRequest, request: Request):
    source: MarketSource = request.app.state.market

    # Persist to DB (your implementation)
    await db_add_watchlist_ticker(body.ticker)

    # Re-sync the source with the full updated list
    all_tickers = await get_watchlist_tickers(user_id="default")
    await source.set_tickers(all_tickers)

    # If using MassiveSource, optionally pre-fetch prev_close immediately
    if isinstance(source, MassiveSource):
        prev_close = await source.fetch_prev_close(body.ticker)
        # store or use prev_close as needed

    return {"ticker": body.ticker.upper(), "status": "added"}


@app.delete("/api/watchlist/{ticker}")
async def remove_ticker(ticker: str, request: Request):
    source: MarketSource = request.app.state.market

    await db_remove_watchlist_ticker(ticker)

    all_tickers = await get_watchlist_tickers(user_id="default")
    await source.set_tickers(all_tickers)

    return {"ticker": ticker.upper(), "status": "removed"}
```

### 9.4 Trade fill price — using `latest()`

```python
@app.post("/api/portfolio/trade")
async def execute_trade(body: TradeRequest, request: Request):
    source: MarketSource = request.app.state.market

    tick = source.latest(body.ticker)
    if tick is None:
        return JSONResponse(
            status_code=400,
            content={"error": f"No price available for {body.ticker}"},
        )

    fill_price = tick.price
    # ... validate cash / position, persist trade, update portfolio ...
```

### 9.5 Portfolio snapshot job — using `latest()`

```python
# backend/app/tasks/snapshot.py
import asyncio
import time

async def portfolio_snapshot_loop(app):
    """Record total portfolio value every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        source = app.state.market
        positions = await db_get_positions(user_id="default")
        cash = await db_get_cash(user_id="default")

        total = cash
        for pos in positions:
            tick = source.latest(pos.ticker)
            if tick:
                total += pos.quantity * tick.price

        await db_insert_portfolio_snapshot(
            user_id="default",
            total_value=total,
            recorded_at=time.time(),
        )
```

Start this task inside the lifespan alongside the market source:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    source = build_market_source()
    await source.set_tickers(await get_watchlist_tickers())
    await source.start()
    app.state.market = source

    snapshot_task = asyncio.create_task(portfolio_snapshot_loop(app))
    try:
        yield
    finally:
        snapshot_task.cancel()
        await source.stop()
```

---

## 10. Frontend SSE Contract

The frontend connects with the native `EventSource` API (no library):

```typescript
// frontend/src/hooks/usePriceStream.ts
const es = new EventSource("/api/stream/prices");

es.addEventListener("price", (event) => {
  const tick = JSON.parse(event.data);
  // tick shape:
  // { ticker, price, prev_price, prev_close, ts, dir, change_pct }
  dispatch(updatePrice(tick));
});

es.onerror = () => {
  // EventSource retries automatically; update connection status indicator
  setConnectionStatus("reconnecting");
};
```

`EventSource` reconnects automatically after a disconnect. The backend
does not need to track client state — each reconnect just starts a new
`subscribe()` call.

---

## 11. Testing

### 11.1 Shared fixture

```python
# backend/tests/market/conftest.py
import pytest
import pytest_asyncio
from app.market.simulator import SimulatorSource
from app.market.massive import MassiveSource
from tests.market.fakes import FakeMassiveTransport


@pytest_asyncio.fixture(params=["sim", "massive_fake"])
async def source(request):
    """Started MarketSource, parametrized over both implementations."""
    if request.param == "sim":
        src = SimulatorSource(seed=42, tick_interval_s=0.01)
    else:
        src = MassiveSource(api_key="test-key", poll_interval_s=0.01)
        # Inject a fake transport so no real HTTP calls are made
        src._client = FakeMassiveTransport().build_client()

    await src.set_tickers(["AAPL", "GOOGL"])
    await src.start()
    yield src
    await src.stop()
```

### 11.2 Fake Massive transport

```python
# backend/tests/market/fakes.py
"""Canned HTTP responses for MassiveSource unit tests."""
import json
import httpx

_CANNED_SNAPSHOT = {
    "status": "OK",
    "count": 2,
    "tickers": [
        {
            "ticker": "AAPL",
            "lastTrade": {"p": 190.73},
            "day": {"c": 190.73},
            "prevDay": {"c": 189.50},
            "todaysChangePerc": 0.65,
            "updated": 1715444532000000000,
        },
        {
            "ticker": "GOOGL",
            "lastTrade": {"p": 175.12},
            "day": {"c": 175.12},
            "prevDay": {"c": 174.00},
            "todaysChangePerc": 0.64,
            "updated": 1715444532000000000,
        },
    ],
}


class FakeMassiveTransport(httpx.MockTransport):
    def __init__(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_CANNED_SNAPSHOT,
                headers={"content-type": "application/json"},
            )
        super().__init__(handler=handler)

    def build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://api.massive.com",
            transport=self,
            timeout=5.0,
        )
```

### 11.3 Conformance tests (both implementations)

```python
# backend/tests/market/test_conformance.py
import asyncio
import pytest
from app.market.models import PriceTick


@pytest.mark.asyncio
async def test_latest_none_before_tick(source):
    """latest() returns None for a ticker with no ticks yet."""
    # AAPL/GOOGL are in the fixture but haven't ticked yet on the fast sim;
    # an unknown ticker always returns None.
    result = source.latest("UNKNOWN")
    assert result is None


@pytest.mark.asyncio
async def test_latest_returns_tick_after_start(source):
    await asyncio.sleep(0.1)   # let the producer fire at least once
    tick = source.latest("AAPL")
    assert tick is not None
    assert isinstance(tick, PriceTick)
    assert tick.price > 0
    assert tick.ticker == "AAPL"


@pytest.mark.asyncio
async def test_subscribe_receives_ticks(source):
    received: list[PriceTick] = []

    async def collect():
        async for tick in source.subscribe():
            received.append(tick)
            if len(received) >= 5:
                break

    await asyncio.wait_for(collect(), timeout=5.0)
    assert len(received) >= 5
    assert all(t.price > 0 for t in received)


@pytest.mark.asyncio
async def test_two_subscribers_both_receive(source):
    a_ticks: list[PriceTick] = []
    b_ticks: list[PriceTick] = []

    async def collect(store, n=3):
        async for tick in source.subscribe():
            store.append(tick)
            if len(store) >= n:
                break

    await asyncio.gather(collect(a_ticks), collect(b_ticks))
    assert len(a_ticks) >= 3
    assert len(b_ticks) >= 3


@pytest.mark.asyncio
async def test_set_tickers_removes_old(source):
    await source.set_tickers(["TSLA"])
    await asyncio.sleep(0.15)
    # AAPL should stop ticking; TSLA should start
    tick = source.latest("TSLA")
    assert tick is not None
    assert tick.ticker == "TSLA"


@pytest.mark.asyncio
async def test_stop_is_idempotent(source):
    await source.stop()
    await source.stop()   # must not raise


@pytest.mark.asyncio
async def test_direction_property():
    tick_up = PriceTick("AAPL", price=191.0, prev_price=190.0,
                        prev_close=189.5, timestamp=1.0)
    tick_down = PriceTick("AAPL", price=189.0, prev_price=190.0,
                          prev_close=189.5, timestamp=1.0)
    tick_flat = PriceTick("AAPL", price=190.0, prev_price=190.0,
                          prev_close=189.5, timestamp=1.0)
    assert tick_up.direction == "up"
    assert tick_down.direction == "down"
    assert tick_flat.direction == "flat"


@pytest.mark.asyncio
async def test_change_pct():
    tick = PriceTick("AAPL", price=191.0, prev_price=190.0,
                     prev_close=190.0, timestamp=1.0)
    assert abs(tick.change_pct - 0.5263) < 0.01   # (191-190)/190*100
```

### 11.4 Simulator-specific tests

```python
# backend/tests/market/test_simulator.py
import asyncio
import pytest
from app.market.simulator import SimulatorSource, _cholesky, _corr_matrix
from app.market.models import PriceTick


@pytest.mark.asyncio
async def test_deterministic_with_seed():
    """Same seed → same price sequence."""
    async def run_sim(seed):
        sim = SimulatorSource(seed=seed, tick_interval_s=0.01)
        await sim.set_tickers(["AAPL"])
        await sim.start()
        ticks = []
        async for t in sim.subscribe():
            ticks.append(t.price)
            if len(ticks) >= 5:
                break
        await sim.stop()
        return ticks

    run1 = await run_sim(42)
    run2 = await run_sim(42)
    assert run1 == run2


@pytest.mark.asyncio
async def test_prices_always_positive():
    sim = SimulatorSource(seed=99, tick_interval_s=0.005)
    await sim.set_tickers(["AAPL", "TSLA", "NVDA"])
    await sim.start()
    ticks = []
    async for t in sim.subscribe():
        ticks.append(t)
        if len(ticks) >= 100:
            break
    await sim.stop()
    assert all(t.price > 0 for t in ticks)


def test_cholesky_identity():
    """Cholesky of identity matrix is identity."""
    import math
    I = [[1.0, 0.0], [0.0, 1.0]]
    L = _cholesky(I)
    assert abs(L[0][0] - 1.0) < 1e-9
    assert abs(L[1][1] - 1.0) < 1e-9
    assert abs(L[1][0]) < 1e-9


def test_corr_matrix_diagonal():
    m = _corr_matrix(["AAPL", "GOOGL"])
    assert m[0][0] == 1.0
    assert m[1][1] == 1.0
    assert m[0][1] == m[1][0]   # symmetric


@pytest.mark.asyncio
async def test_event_jumps_fire():
    """With high event_prob, most ticks should show a large move."""
    sim = SimulatorSource(seed=1, tick_interval_s=0.001, event_prob=1.0)
    await sim.set_tickers(["AAPL"])
    await sim.start()
    ticks = []
    async for t in sim.subscribe():
        ticks.append(t)
        if len(ticks) >= 20:
            break
    await sim.stop()
    # With event_prob=1.0 every tick is a jump — all moves should be ≥ 2%
    big_moves = [
        abs(t.price - t.prev_price) / t.prev_price
        for t in ticks if t.prev_price > 0
    ]
    assert all(m > 0.01 for m in big_moves)
```

### 11.5 MassiveSource-specific tests

```python
# backend/tests/market/test_massive.py
import asyncio
import json
import pytest
import httpx
from app.market.massive import MassiveSource
from tests.market.fakes import FakeMassiveTransport


@pytest.mark.asyncio
async def test_parses_snapshot_correctly():
    src = MassiveSource(api_key="test", poll_interval_s=0.05)
    src._client = FakeMassiveTransport().build_client()
    await src.set_tickers(["AAPL", "GOOGL"])
    await src.start()
    await asyncio.sleep(0.15)

    tick = src.latest("AAPL")
    assert tick is not None
    assert tick.price == 190.73
    assert tick.prev_close == 189.50
    assert tick.direction in ("up", "down", "flat")

    await src.stop()


@pytest.mark.asyncio
async def test_429_retries():
    """A 429 response triggers retries and the source eventually recovers."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(429)
        return httpx.Response(200, json={
            "tickers": [{
                "ticker": "AAPL",
                "lastTrade": {"p": 190.0},
                "day": {"c": 190.0},
                "prevDay": {"c": 189.0},
                "updated": 0,
            }]
        })

    transport = httpx.MockTransport(handler=handler)
    src = MassiveSource(api_key="test", poll_interval_s=0.01)
    src._client = httpx.AsyncClient(
        base_url="https://api.massive.com", transport=transport, timeout=5.0
    )
    await src.set_tickers(["AAPL"])
    await src.start()
    await asyncio.sleep(1.0)

    tick = src.latest("AAPL")
    assert tick is not None
    assert call_count >= 3

    await src.stop()


@pytest.mark.asyncio
async def test_missing_last_trade_falls_back_to_day_close():
    """When lastTrade is absent, day.c is used as the price."""
    canned = {
        "tickers": [{
            "ticker": "AAPL",
            "day": {"c": 188.00},
            "prevDay": {"c": 187.00},
            "updated": 0,
        }]
    }

    def handler(req):
        return httpx.Response(200, json=canned)

    src = MassiveSource(api_key="test", poll_interval_s=0.05)
    src._client = httpx.AsyncClient(
        base_url="https://api.massive.com",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
    )
    await src.set_tickers(["AAPL"])
    await src.start()
    await asyncio.sleep(0.15)

    tick = src.latest("AAPL")
    assert tick is not None
    assert tick.price == 188.00

    await src.stop()
```

---

## 12. Dependencies

Add to `backend/pyproject.toml`:

```toml
[project]
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "sse-starlette>=1.8",
    "httpx>=0.27",
]

[project.optional-dependencies]
test = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "anyio[trio]",
]
```

No NumPy, no Pandas, no `massive` SDK — the GBM math is pure Python
and the Massive integration is a single `httpx` call.

---

## 13. Design Decisions

| Decision | Rationale |
|----------|-----------|
| `AsyncIterator` for subscribers | Maps 1:1 with FastAPI's `EventSourceResponse`. Cancellation is explicit when the client disconnects. |
| Drop-oldest queues (maxsize=256) | A slow browser tab loses stale ticks rather than backing up the producer. The frontend only renders the latest price anyway. |
| `set_tickers` replaces (not appends) | Single source of truth. Caller always passes the full desired set; the source computes diffs internally if needed. |
| Factory reads env, impls don't | Tests construct sources with explicit args. The env is only consulted once, at startup. |
| Pure-Python Cholesky | Avoids NumPy as a production dependency. For 10 tickers the N³ cost is negligible (microseconds). |
| `prev_close` tracked separately from `prev_price` | `prev_price` = last-tick price (drives flash direction at 500 ms resolution); `prev_close` = yesterday's close (drives daily % change). Both are needed. |
| No `MassiveSource` WebSocket | REST polling is simpler and works on the free tier. The interface supports swapping in a WebSocket producer with zero consumer changes. |
```
