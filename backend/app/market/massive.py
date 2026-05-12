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
