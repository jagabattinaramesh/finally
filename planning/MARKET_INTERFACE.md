# Market Data Interface

> Unified abstraction for stock price data inside FinAlly. The backend
> talks **only** to this interface. The concrete implementation is chosen
> at startup based on the `MASSIVE_API_KEY` environment variable:
>
> - `MASSIVE_API_KEY` set + non-empty → `MassiveSource` (real data, see
>   `MASSIVE_API.md`)
> - otherwise → `SimulatorSource` (synthetic prices, see
>   `MARKET_SIMULATOR.md`)
>
> Everything downstream — the SSE streamer, the price cache, the trade
> engine, the portfolio snapshot job — is **agnostic to the source**.

---

## 1. Goals

1. **One interface, two implementations.** Swap real ↔ simulator
   without touching any consumer code.
2. **Push, not pull, downstream.** Consumers subscribe to an async
   stream of price ticks rather than polling.
3. **Simple types.** Plain dataclasses, no SQLAlchemy / Pydantic models
   bleeding into the market layer.
4. **Small surface.** Five methods total. If a method isn't on this
   list, the layer doesn't need it.

Non-goals: order books, level-2 quotes, options chains, fundamentals,
historical bars beyond previous close.

---

## 2. Data types

```python
# backend/app/market/models.py
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PriceTick:
    """A single price update for one ticker."""

    ticker: str
    price: float
    prev_price: float        # the previous tick's price (or prev_close on first tick)
    prev_close: float        # yesterday's close — used for daily % change
    timestamp: float         # seconds since epoch (float)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat' — convenience for the frontend flash."""
        if self.price > self.prev_price:
            return "up"
        if self.price < self.prev_price:
            return "down"
        return "flat"

    @property
    def change_pct(self) -> float:
        if self.prev_close == 0:
            return 0.0
        return (self.price - self.prev_close) / self.prev_close * 100.0
```

Why nanoseconds-since-epoch isn't used: the rest of the backend (SQLite
`executed_at`, SSE payloads, charts) all use seconds. Converting once at
the boundary is simpler than threading a different unit through every
consumer.

---

## 3. The interface

```python
# backend/app/market/interface.py
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from .models import PriceTick


class MarketSource(ABC):
    """Abstract source of stock price data.

    Lifecycle: ``await start()`` once, ``subscribe()`` as many times as
    needed, ``await stop()`` on shutdown. ``set_tickers`` may be called
    at any time after ``start`` to change what the source tracks.
    """

    @abstractmethod
    async def start(self) -> None:
        """Begin producing ticks in the background."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop background work and release resources."""

    @abstractmethod
    async def set_tickers(self, tickers: list[str]) -> None:
        """Replace the active ticker set (idempotent, deduped)."""

    @abstractmethod
    def latest(self, ticker: str) -> PriceTick | None:
        """Return the most recent tick for ``ticker``, or ``None``."""

    @abstractmethod
    def subscribe(self) -> AsyncIterator[PriceTick]:
        """Yield ticks as they are produced. Multiple subscribers OK."""
```

### Method-by-method contract

| Method | Semantics |
|--------|-----------|
| `start()` | Idempotent. Spawns the background producer task. Must be awaited before `subscribe()` yields anything. |
| `stop()` | Cancels the producer, drains queues, closes any HTTP clients. Safe to call multiple times. |
| `set_tickers(t)` | Source begins tracking exactly the tickers in `t`. Removed tickers stop ticking. New tickers tick on the next cycle. |
| `latest(t)` | O(1) read from an in-memory map. Returns `None` until the first tick for that ticker has been produced. |
| `subscribe()` | Returns an independent `AsyncIterator`. Each subscriber gets every tick produced after it subscribes; slow consumers must not block the producer (implementations use bounded queues with drop-oldest). |

### Why an async iterator, not a callback registry?

- Plays naturally with FastAPI's `EventSourceResponse` (one
  `async for tick in source.subscribe():` per connection).
- Cancellation is explicit — `async for` ends when the client
  disconnects.
- No mutex juggling for adding/removing listeners.

---

## 4. Factory + selection

```python
# backend/app/market/factory.py
import os

from .interface import MarketSource
from .massive import MassiveSource
from .simulator import SimulatorSource


def build_market_source() -> MarketSource:
    """Return the configured market data source.

    Selection rule (single source of truth):
        MASSIVE_API_KEY is set and non-empty -> MassiveSource
        otherwise                            -> SimulatorSource
    """
    key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if key:
        return MassiveSource(api_key=key)
    return SimulatorSource()
```

The factory is the **only** place that reads the environment. Tests
construct sources directly with explicit arguments.

---

## 5. Wiring into FastAPI

```python
# backend/app/main.py  (sketch)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sse_starlette import EventSourceResponse

from app.market.factory import build_market_source
from app.market.interface import MarketSource


@asynccontextmanager
async def lifespan(app: FastAPI):
    source: MarketSource = build_market_source()
    await source.set_tickers(load_watchlist_tickers())
    await source.start()
    app.state.market = source
    try:
        yield
    finally:
        await source.stop()


app = FastAPI(lifespan=lifespan)


@app.get("/api/stream/prices")
async def stream_prices(request: Request):
    source: MarketSource = request.app.state.market

    async def event_gen():
        async for tick in source.subscribe():
            if await request.is_disconnected():
                break
            yield {
                "event": "price",
                "data": json.dumps({
                    "ticker": tick.ticker,
                    "price": tick.price,
                    "prev_price": tick.prev_price,
                    "prev_close": tick.prev_close,
                    "ts": tick.timestamp,
                    "dir": tick.direction,
                    "change_pct": tick.change_pct,
                }),
            }

    return EventSourceResponse(event_gen())
```

Other consumers (trade engine looking up fill price, portfolio snapshot
job summing position values) call `source.latest(ticker)` — no need to
subscribe.

---

## 6. Implementation outline — `MassiveSource`

Detailed endpoint reference: see `MASSIVE_API.md`.

```python
# backend/app/market/massive.py  (sketch)
import asyncio
import time

import httpx

from .interface import MarketSource
from .models import PriceTick


POLL_INTERVAL_S = 15.0   # free tier: 5/min cap, 15s leaves headroom


class MassiveSource(MarketSource):
    def __init__(self, api_key: str, poll_interval_s: float = POLL_INTERVAL_S):
        self._api_key = api_key
        self._poll_interval_s = poll_interval_s
        self._tickers: set[str] = set()
        self._latest: dict[str, PriceTick] = {}
        self._subs: list[asyncio.Queue[PriceTick]] = []
        self._task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._client = httpx.AsyncClient(
            base_url="https://api.massive.com",
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

    async def subscribe(self):
        q: asyncio.Queue[PriceTick] = asyncio.Queue(maxsize=256)
        self._subs.append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subs.remove(q)

    # --- internals -----------------------------------------------------

    async def _poll_loop(self) -> None:
        while True:
            try:
                if self._tickers:
                    await self._poll_once()
            except Exception as e:
                # log and keep going — never let the poll loop die
                print(f"[massive] poll error: {e}")
            await asyncio.sleep(self._poll_interval_s)

    async def _poll_once(self) -> None:
        params = {"tickers": ",".join(sorted(self._tickers))}
        resp = await self._client.get(
            "/v2/snapshot/locale/us/markets/stocks/tickers", params=params
        )
        resp.raise_for_status()
        now = time.time()
        for entry in resp.json().get("tickers", []):
            self._emit_from_entry(entry, now)

    def _emit_from_entry(self, entry: dict, now: float) -> None:
        ticker = entry["ticker"]
        last_trade = entry.get("lastTrade") or {}
        day = entry.get("day") or {}
        prev_day = entry.get("prevDay") or {}
        price = last_trade.get("p") or day.get("c")
        if price is None:
            return
        prev = self._latest.get(ticker)
        tick = PriceTick(
            ticker=ticker,
            price=float(price),
            prev_price=prev.price if prev else float(prev_day.get("c", price)),
            prev_close=float(prev_day.get("c", price)),
            timestamp=now,
        )
        self._latest[ticker] = tick
        for q in self._subs:
            if q.full():
                try:
                    q.get_nowait()  # drop oldest
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(tick)
```

Notes on this sketch:

- **One poll → many ticks.** Each REST call produces N ticks (one per
  ticker), all emitted back-to-back.
- **Rate-limit handling.** A 429 caught in `_poll_loop` triggers a
  longer sleep (handled by the backoff helper from `MASSIVE_API.md`);
  the loop self-recovers.
- **Drop-oldest queues.** A subscriber that falls behind loses old
  ticks rather than backing up the producer. Acceptable: the frontend
  only renders the latest price anyway.

---

## 7. Implementation outline — `SimulatorSource`

Full design in `MARKET_SIMULATOR.md`. From the interface's perspective
the only difference is the producer: instead of HTTP polling, an async
loop ticks every ~500 ms and computes GBM updates per ticker. Same
`PriceTick`, same `subscribe()`, same `latest()`.

---

## 8. Testing strategy

Both implementations must pass the same conformance suite.

```python
# backend/tests/market/conftest.py
import pytest


@pytest.fixture(params=["sim", "massive_fake"])
async def source(request):
    """Yields a started MarketSource, parametrized over both impls."""
    if request.param == "sim":
        from app.market.simulator import SimulatorSource
        src = SimulatorSource(seed=42, tick_interval_s=0.01)
    else:
        from app.market.massive import MassiveSource
        from tests.market.fakes import FakeMassiveTransport
        src = MassiveSource(api_key="test", poll_interval_s=0.01)
        src._client_transport = FakeMassiveTransport()  # injection seam
    await src.set_tickers(["AAPL", "GOOGL"])
    await src.start()
    yield src
    await src.stop()
```

Conformance tests (a non-exhaustive sketch):

- `latest()` returns `None` before any tick has fired.
- After `start()` and a brief wait, `latest("AAPL")` is non-`None`.
- Two concurrent subscribers each receive at least N ticks.
- `set_tickers(["TSLA"])` stops producing ticks for AAPL and starts
  producing ticks for TSLA within one cycle.
- `stop()` is idempotent and clean (no warnings about pending tasks).

For the real `MassiveSource`, the `FakeMassiveTransport` replays canned
JSON responses captured from a real free-tier call, so the test suite
runs without network and without burning the rate limit.

---

## 9. Open questions / future work

- **Multi-user.** When we add real users, `set_tickers` becomes the
  **union of all users' watchlists**. The cache key (`ticker`) stays
  flat; user filtering happens in the SSE layer.
- **WebSocket upgrade.** If we move to a paid tier, swap polling for
  Massive's WebSocket stream — same interface, no consumer changes.
- **Market hours.** Currently the simulator runs 24/7. We may want to
  flatten ticks (zero volatility) outside RTH for a more realistic feel.
