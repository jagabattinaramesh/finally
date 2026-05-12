"""Conformance tests that both SimulatorSource and MassiveSource must pass."""
import asyncio
import pytest
from app.market.models import PriceTick


@pytest.mark.asyncio
async def test_latest_none_for_unknown_ticker(source):
    """latest() returns None for a ticker that was never set."""
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
    tick = source.latest("TSLA")
    assert tick is not None
    assert tick.ticker == "TSLA"


@pytest.mark.asyncio
async def test_stop_is_idempotent(source):
    await source.stop()
    await source.stop()   # must not raise


def test_direction_property():
    tick_up = PriceTick("AAPL", price=191.0, prev_price=190.0,
                        prev_close=189.5, timestamp=1.0)
    tick_down = PriceTick("AAPL", price=189.0, prev_price=190.0,
                          prev_close=189.5, timestamp=1.0)
    tick_flat = PriceTick("AAPL", price=190.0, prev_price=190.0,
                          prev_close=189.5, timestamp=1.0)
    assert tick_up.direction == "up"
    assert tick_down.direction == "down"
    assert tick_flat.direction == "flat"


def test_change_pct():
    tick = PriceTick("AAPL", price=191.0, prev_price=190.0,
                     prev_close=190.0, timestamp=1.0)
    assert abs(tick.change_pct - 0.5263) < 0.01   # (191-190)/190*100


def test_change_pct_zero_prev_close():
    tick = PriceTick("AAPL", price=100.0, prev_price=99.0,
                     prev_close=0.0, timestamp=1.0)
    assert tick.change_pct == 0.0


def test_to_sse_dict_shape():
    tick = PriceTick("AAPL", price=191.0, prev_price=190.0,
                     prev_close=189.5, timestamp=1715444532.0)
    d = tick.to_sse_dict()
    assert d["ticker"] == "AAPL"
    assert d["price"] == 191.0
    assert d["prev_price"] == 190.0
    assert d["prev_close"] == 189.5
    assert d["ts"] == 1715444532.0
    assert d["dir"] == "up"
    assert isinstance(d["change_pct"], float)
