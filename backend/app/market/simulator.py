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
