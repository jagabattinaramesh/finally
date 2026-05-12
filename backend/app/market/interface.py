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
