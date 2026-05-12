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
