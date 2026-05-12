"""MassiveSource-specific tests: field parsing, backoff, fallback logic."""
import asyncio
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
async def test_parses_googl_correctly():
    src = MassiveSource(api_key="test", poll_interval_s=0.05)
    src._client = FakeMassiveTransport().build_client()
    await src.set_tickers(["AAPL", "GOOGL"])
    await src.start()
    await asyncio.sleep(0.15)

    tick = src.latest("GOOGL")
    assert tick is not None
    assert tick.price == 175.12
    assert tick.prev_close == 174.00

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


@pytest.mark.asyncio
async def test_missing_ticker_field_skipped():
    """Entries with no ticker field are silently skipped."""
    canned = {
        "tickers": [
            {"lastTrade": {"p": 100.0}},   # no ticker key
            {"ticker": "AAPL", "lastTrade": {"p": 190.73}, "prevDay": {"c": 189.50}},
        ]
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

    assert src.latest("AAPL") is not None
    await src.stop()


@pytest.mark.asyncio
async def test_missing_price_skipped():
    """Entries with no lastTrade.p and no day.c are silently skipped."""
    canned = {
        "tickers": [
            {"ticker": "AAPL", "prevDay": {"c": 189.50}},  # no price
        ]
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

    # No price available → latest should be None
    assert src.latest("AAPL") is None
    await src.stop()


@pytest.mark.asyncio
async def test_prev_price_tracks_previous_tick():
    """On the second poll, prev_price should equal the first poll's price."""
    poll_count = 0

    def handler(req):
        nonlocal poll_count
        poll_count += 1
        price = 190.0 if poll_count == 1 else 192.0
        return httpx.Response(200, json={
            "tickers": [{
                "ticker": "AAPL",
                "lastTrade": {"p": price},
                "prevDay": {"c": 189.0},
                "updated": 0,
            }]
        })

    src = MassiveSource(api_key="test", poll_interval_s=0.05)
    src._client = httpx.AsyncClient(
        base_url="https://api.massive.com",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
    )
    await src.set_tickers(["AAPL"])
    await src.start()
    # Wait for at least two polls
    await asyncio.sleep(0.2)

    tick = src.latest("AAPL")
    assert tick is not None
    if poll_count >= 2:
        assert tick.price == 192.0
        assert tick.prev_price == 190.0

    await src.stop()


@pytest.mark.asyncio
async def test_start_idempotent():
    """Calling start() twice doesn't create a second background task."""
    src = MassiveSource(api_key="test", poll_interval_s=1.0)
    src._client = FakeMassiveTransport().build_client()
    await src.set_tickers(["AAPL"])
    await src.start()
    task_before = src._task
    await src.start()
    assert src._task is task_before
    await src.stop()


@pytest.mark.asyncio
async def test_stop_closes_client():
    """stop() should close the httpx client."""
    src = MassiveSource(api_key="test", poll_interval_s=1.0)
    src._client = FakeMassiveTransport().build_client()
    await src.set_tickers(["AAPL"])
    await src.start()
    await src.stop()
    assert src._client is None
    assert src._task is None


@pytest.mark.asyncio
async def test_latest_uppercase_lookup():
    """latest() normalises ticker to uppercase."""
    src = MassiveSource(api_key="test", poll_interval_s=0.05)
    src._client = FakeMassiveTransport().build_client()
    await src.set_tickers(["aapl"])   # lowercase input
    await src.start()
    await asyncio.sleep(0.15)

    tick = src.latest("aapl")   # lowercase query
    assert tick is not None
    await src.stop()
