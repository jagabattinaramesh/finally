# Market Simulator

> The default market data source for FinAlly. Activates when
> `MASSIVE_API_KEY` is unset (see `MARKET_INTERFACE.md` for the
> selection rule). Generates believable, visually lively prices with
> zero external dependencies — the goal is a demo that *feels* like a
> trading terminal even with no API key.

---

## 1. Design goals

| Goal | Why |
|------|-----|
| Look real | Prices drift, occasionally jump, react together — not random walks. |
| Be cheap | Pure-Python math, one async task, ~500 ms cadence, fits a single Docker container. |
| Be reproducible | A fixed seed produces a fixed price sequence — essential for E2E tests. |
| Be agnostic | Implements `MarketSource` (see `MARKET_INTERFACE.md`). The SSE streamer cannot tell sim from real. |

Non-goals: trading hours, order book microstructure, after-hours gaps,
dividend / split events. The simulator runs continuously and produces
one mid-price per tick per ticker.

---

## 2. The math: correlated GBM with event jumps

### 2.1 Geometric Brownian Motion

Each ticker's price is updated every `Δt` seconds using the standard
GBM discretization:

```
S_{t+Δt} = S_t · exp( (μ − σ²/2) · Δt + σ · √Δt · Z )
```

where:

- `S_t` — current price
- `μ` — annualized drift (small per-ticker bias, e.g. 0.05 for +5%/yr)
- `σ` — annualized volatility (e.g. 0.25 for a typical large-cap stock)
- `Δt` — tick interval in **years** (`0.5 s` → `0.5 / (252·6.5·3600)`)
- `Z` — a standard normal draw, correlated across tickers (next section)

GBM has the property we want: prices can't go negative, and percentage
moves (not absolute moves) are normally distributed — exactly how real
prices behave.

### 2.2 Correlation between tickers

Real stocks move together. Tech stocks especially. To model this we
draw a *correlated* Gaussian vector each tick using a Cholesky factor.

```
Z = L · ε        where ε ~ N(0, I),  L = chol(Σ)
```

`Σ` is an `N × N` correlation matrix. For the 10 default tickers we use
a simple two-block structure:

```
                AAPL  GOOGL MSFT  AMZN  TSLA  NVDA  META  JPM   V     NFLX
       AAPL    1.00   0.60  0.60  0.55  0.45  0.55  0.55  0.20  0.25  0.50
       GOOGL   0.60   1.00  0.65  0.55  0.40  0.55  0.65  0.20  0.25  0.55
       MSFT    0.60   0.65  1.00  0.50  0.35  0.55  0.55  0.25  0.30  0.45
       AMZN    0.55   0.55  0.50  1.00  0.40  0.50  0.50  0.25  0.30  0.55
       TSLA    0.45   0.40  0.35  0.40  1.00  0.50  0.40  0.20  0.20  0.35
       NVDA    0.55   0.55  0.55  0.50  0.50  1.00  0.55  0.25  0.25  0.45
       META    0.55   0.65  0.55  0.50  0.40  0.55  1.00  0.20  0.25  0.55
       JPM     0.20   0.20  0.25  0.25  0.20  0.25  0.20  1.00  0.55  0.20
       V       0.25   0.25  0.30  0.30  0.20  0.25  0.25  0.55  1.00  0.25
       NFLX    0.50   0.55  0.45  0.55  0.35  0.45  0.55  0.20  0.25  1.00
```

(Big-tech bloc ~0.5–0.65; finance bloc JPM/V ~0.55; cross-bloc ~0.2.)

Tickers added at runtime that aren't in the matrix get a default
correlation of `0.3` with every existing ticker — a reasonable
"vaguely-equity" baseline.

### 2.3 Event jumps

GBM alone produces a soothing drift that is *too* calm. To get
demo-worthy excitement, on each tick every ticker has a tiny
probability of an **event** — a one-shot multiplicative shock layered
on top of the GBM step:

```
on each tick, with probability p_event ≈ 0.002 per ticker:
    jump = exp( ±U(0.02, 0.05) )       # 2–5% move, sign 50/50
    S ← S · jump
```

At a 500 ms tick rate and `p_event = 0.002`, a ticker fires an event
roughly **once every ~4–5 minutes** on average — frequent enough to be
noticeable, rare enough not to feel synthetic.

---

## 3. Seed prices

Seeded from approximate real prices as of the project start so the demo
looks plausible from the first frame:

| Ticker | Seed price | Annualized μ | Annualized σ |
|--------|-----------:|-------------:|-------------:|
| AAPL   | 190.00 | 0.05 | 0.25 |
| GOOGL  | 175.00 | 0.06 | 0.27 |
| MSFT   | 415.00 | 0.07 | 0.24 |
| AMZN   | 185.00 | 0.05 | 0.30 |
| TSLA   | 175.00 | 0.00 | 0.55 |
| NVDA   | 950.00 | 0.10 | 0.45 |
| META   | 490.00 | 0.06 | 0.32 |
| JPM    | 200.00 | 0.04 | 0.20 |
| V      | 275.00 | 0.05 | 0.18 |
| NFLX   | 620.00 | 0.05 | 0.35 |

Defaults for unknown tickers: `seed=100.00`, `μ=0.05`, `σ=0.30`.

Seed prices, drifts, and volatilities live in a single dict in
`seed_prices.py` so they're easy to tweak without touching the engine.

---

## 4. Code structure

```
backend/app/market/
├── interface.py        # MarketSource ABC (see MARKET_INTERFACE.md)
├── models.py           # PriceTick dataclass
├── factory.py          # build_market_source()
├── massive.py          # MassiveSource
├── simulator.py        # <-- this document
└── seed_prices.py      # SEED_PRICES, DRIFTS, VOLS, CORRELATIONS
```

### 4.1 `simulator.py` — full sketch

```python
"""Synthetic market data via correlated GBM with random event jumps."""

import asyncio
import math
import random
import time
from collections.abc import AsyncIterator

from .interface import MarketSource
from .models import PriceTick
from .seed_prices import (
    SEED_PRICES, DRIFTS, VOLS, CORRELATIONS,
    DEFAULT_PRICE, DEFAULT_DRIFT, DEFAULT_VOL, DEFAULT_CORR,
)


# Number of seconds in a trading year (252 days * 6.5 hrs * 3600 s).
SECONDS_PER_YEAR = 252 * 6.5 * 3600


class SimulatorSource(MarketSource):
    """Drop-in market source that generates prices locally."""

    def __init__(
        self,
        *,
        tick_interval_s: float = 0.5,
        event_prob: float = 0.002,
        seed: int | None = None,
    ):
        self._tick_interval = tick_interval_s
        self._event_prob = event_prob
        self._rng = random.Random(seed)
        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._prev_close: dict[str, float] = {}
        self._latest: dict[str, PriceTick] = {}
        self._chol: list[list[float]] = []   # Cholesky factor of corr matrix
        self._subs: list[asyncio.Queue[PriceTick]] = []
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()           # guards _tickers / _chol swap

    # --- MarketSource API -------------------------------------------

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
        tickers = [t.upper() for t in tickers]
        async with self._lock:
            self._tickers = list(dict.fromkeys(tickers))  # dedupe, keep order
            for t in self._tickers:
                if t not in self._prices:
                    seed = SEED_PRICES.get(t, DEFAULT_PRICE)
                    self._prices[t] = seed
                    self._prev_close[t] = seed
            self._chol = _cholesky(_corr_matrix(self._tickers))

    def latest(self, ticker: str) -> PriceTick | None:
        return self._latest.get(ticker.upper())

    async def subscribe(self) -> AsyncIterator[PriceTick]:
        q: asyncio.Queue[PriceTick] = asyncio.Queue(maxsize=256)
        self._subs.append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subs.remove(q)

    # --- producer ----------------------------------------------------

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

        # 1. Draw correlated standard-normal shocks.
        eps = [self._rng.gauss(0.0, 1.0) for _ in tickers]
        z = [sum(chol[i][j] * eps[j] for j in range(i + 1)) for i in range(len(tickers))]

        dt = self._tick_interval / SECONDS_PER_YEAR
        sqrt_dt = math.sqrt(dt)
        now = time.time()

        for i, ticker in enumerate(tickers):
            mu = DRIFTS.get(ticker, DEFAULT_DRIFT)
            sigma = VOLS.get(ticker, DEFAULT_VOL)
            old_price = self._prices[ticker]

            # 2. GBM step.
            drift_term = (mu - 0.5 * sigma * sigma) * dt
            shock_term = sigma * sqrt_dt * z[i]
            new_price = old_price * math.exp(drift_term + shock_term)

            # 3. Optional event jump.
            if self._rng.random() < self._event_prob:
                pct = self._rng.uniform(0.02, 0.05)
                direction = 1.0 if self._rng.random() < 0.5 else -1.0
                new_price *= math.exp(direction * pct)

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
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(tick)


# --- helpers ---------------------------------------------------------

def _corr_matrix(tickers: list[str]) -> list[list[float]]:
    n = len(tickers)
    m = [[1.0 if i == j else DEFAULT_CORR for j in range(n)] for i in range(n)]
    for i, a in enumerate(tickers):
        for j, b in enumerate(tickers):
            if i == j:
                continue
            v = CORRELATIONS.get((a, b)) or CORRELATIONS.get((b, a))
            if v is not None:
                m[i][j] = v
    return m


def _cholesky(m: list[list[float]]) -> list[list[float]]:
    """Lower-triangular Cholesky factor. Pure Python, no numpy needed."""
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

### 4.2 `seed_prices.py`

```python
"""Per-ticker simulator constants. Edit freely."""

SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00, "GOOGL": 175.00, "MSFT": 415.00, "AMZN": 185.00,
    "TSLA": 175.00, "NVDA": 950.00, "META": 490.00, "JPM": 200.00,
    "V":    275.00, "NFLX": 620.00,
}

DRIFTS: dict[str, float] = {
    "AAPL": 0.05, "GOOGL": 0.06, "MSFT": 0.07, "AMZN": 0.05,
    "TSLA": 0.00, "NVDA": 0.10, "META": 0.06, "JPM": 0.04,
    "V":    0.05, "NFLX": 0.05,
}

VOLS: dict[str, float] = {
    "AAPL": 0.25, "GOOGL": 0.27, "MSFT": 0.24, "AMZN": 0.30,
    "TSLA": 0.55, "NVDA": 0.45, "META": 0.32, "JPM": 0.20,
    "V":    0.18, "NFLX": 0.35,
}

CORRELATIONS: dict[tuple[str, str], float] = {
    ("AAPL", "GOOGL"): 0.60, ("AAPL", "MSFT"): 0.60, ("AAPL", "AMZN"): 0.55,
    ("AAPL", "TSLA"): 0.45, ("AAPL", "NVDA"): 0.55, ("AAPL", "META"): 0.55,
    ("AAPL", "NFLX"): 0.50, ("AAPL", "JPM"): 0.20, ("AAPL", "V"): 0.25,
    ("GOOGL", "MSFT"): 0.65, ("GOOGL", "META"): 0.65, ("GOOGL", "NVDA"): 0.55,
    ("GOOGL", "AMZN"): 0.55, ("GOOGL", "NFLX"): 0.55, ("GOOGL", "TSLA"): 0.40,
    ("MSFT", "NVDA"): 0.55, ("MSFT", "AMZN"): 0.50, ("MSFT", "META"): 0.55,
    ("NVDA", "META"): 0.55, ("NVDA", "TSLA"): 0.50,
    ("JPM", "V"): 0.55,
    # … add more as you see fit; missing pairs fall back to DEFAULT_CORR
}

DEFAULT_PRICE = 100.00
DEFAULT_DRIFT = 0.05
DEFAULT_VOL = 0.30
DEFAULT_CORR = 0.30
```

---

## 5. Tunable behavior

All knobs are constructor arguments on `SimulatorSource`. No env vars
involved — the simulator's behavior is owned by the code, not the
deployment.

| Knob | Default | Effect |
|------|--------:|--------|
| `tick_interval_s` | 0.5 | Cadence of `PriceTick` emission per ticker. |
| `event_prob` | 0.002 | Per-ticker, per-tick chance of a 2–5% jump (≈ 1 event / 4–5 min at default). |
| `seed` | `None` | Deterministic RNG when set; tests should always set this. |

Per-ticker `μ` and `σ` are edited in `seed_prices.py`.

---

## 6. Determinism & testing

When `seed` is provided:

- The RNG is a `random.Random(seed)` instance — entirely local, doesn't
  touch the global PRNG.
- For a fixed `(seed, tick_interval_s, tickers)` the sequence of
  emitted prices is byte-identical run to run.

This enables tight assertions:

```python
async def test_deterministic_sequence():
    sim = SimulatorSource(seed=1234, tick_interval_s=0.01)
    await sim.set_tickers(["AAPL", "GOOGL"])
    await sim.start()

    ticks: list[PriceTick] = []
    async for tick in sim.subscribe():
        ticks.append(tick)
        if len(ticks) >= 10:
            break
    await sim.stop()

    assert ticks[0].ticker in {"AAPL", "GOOGL"}
    assert ticks[0].price > 0
    assert all(t.price > 0 for t in ticks)
    # Snapshot test — captured from first run, asserts no regression:
    assert ticks[0].price == 189.97
```

Statistical sanity tests (run with many ticks, weaker assertions):

- Log-returns over a long run have mean ≈ `μ · Δt` per ticker.
- Sample correlations approach the configured `Σ` as N → ∞.
- No price ever goes negative or NaN.

---

## 7. What this simulator deliberately does **not** do

These omissions are intentional — they would add complexity for very
little demo value. They are listed here so future contributors don't
"fix" them by accident.

- **Trading hours.** Prices tick 24/7. The frontend doesn't show a
  market-closed banner.
- **After-hours gaps.** No discontinuous overnight jump.
- **Corporate actions.** No dividends, splits, or ticker renames.
- **Order book.** Market orders fill at the current mid-price instantly
  with zero slippage and zero size impact (see PLAN.md §2 — "Market
  orders only").
- **Volume / VWAP.** `PriceTick` carries price only. If the UI ever
  wants volume, we'll add it as a separate field rather than coupling
  it to GBM (which has nothing to say about volume).

If we eventually want any of these, the simulator is small enough to
extend without disturbing the `MarketSource` contract.
