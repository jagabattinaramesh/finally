"""Simulator-specific tests: GBM math, determinism, event jumps."""
import asyncio
import math
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
async def test_different_seeds_differ():
    """Different seeds produce different sequences."""
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
    run2 = await run_sim(99)
    assert run1 != run2


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


@pytest.mark.asyncio
async def test_prices_are_rounded_to_cents():
    sim = SimulatorSource(seed=7, tick_interval_s=0.01)
    await sim.set_tickers(["AAPL"])
    await sim.start()
    ticks = []
    async for t in sim.subscribe():
        ticks.append(t)
        if len(ticks) >= 10:
            break
    await sim.stop()
    for t in ticks:
        assert round(t.price, 2) == t.price


@pytest.mark.asyncio
async def test_starts_near_seed_price():
    """First tick should be within 5% of the seed price."""
    sim = SimulatorSource(seed=1, tick_interval_s=0.01)
    await sim.set_tickers(["AAPL"])
    await sim.start()
    ticks = []
    async for t in sim.subscribe():
        ticks.append(t)
        if len(ticks) >= 1:
            break
    await sim.stop()
    seed_price = 190.00
    assert abs(ticks[0].price - seed_price) / seed_price < 0.05


@pytest.mark.asyncio
async def test_unknown_ticker_gets_default_seed():
    """Tickers not in SEED_PRICES use DEFAULT_PRICE (100.00)."""
    sim = SimulatorSource(seed=5, tick_interval_s=0.01)
    await sim.set_tickers(["FAKE"])
    await sim.start()
    ticks = []
    async for t in sim.subscribe():
        ticks.append(t)
        if len(ticks) >= 1:
            break
    await sim.stop()
    # DEFAULT_PRICE is 100.00; first tick should be close
    assert abs(ticks[0].price - 100.0) / 100.0 < 0.1


@pytest.mark.asyncio
async def test_start_idempotent():
    """Calling start() twice doesn't create a second background task."""
    sim = SimulatorSource(seed=1, tick_interval_s=0.01)
    await sim.set_tickers(["AAPL"])
    await sim.start()
    task_before = sim._task
    await sim.start()
    assert sim._task is task_before   # same task object
    await sim.stop()


@pytest.mark.asyncio
async def test_event_jumps_fire():
    """With event_prob=1.0, every tick is a jump — moves should be ≥ 1%."""
    sim = SimulatorSource(seed=1, tick_interval_s=0.001, event_prob=1.0)
    await sim.set_tickers(["AAPL"])
    await sim.start()
    ticks = []
    async for t in sim.subscribe():
        ticks.append(t)
        if len(ticks) >= 20:
            break
    await sim.stop()
    # With event_prob=1.0 every tick includes a 2–5% jump
    big_moves = [
        abs(t.price - t.prev_price) / t.prev_price
        for t in ticks if t.prev_price > 0
    ]
    assert all(m > 0.01 for m in big_moves)


@pytest.mark.asyncio
async def test_ticker_prev_price_tracks_last_tick():
    """prev_price on each tick should match the prior tick's price."""
    sim = SimulatorSource(seed=3, tick_interval_s=0.01)
    await sim.set_tickers(["AAPL"])
    await sim.start()
    ticks = []
    async for t in sim.subscribe():
        ticks.append(t)
        if len(ticks) >= 5:
            break
    await sim.stop()
    for i in range(1, len(ticks)):
        assert ticks[i].prev_price == ticks[i - 1].price


def test_cholesky_identity():
    """Cholesky of identity matrix is identity."""
    I = [[1.0, 0.0], [0.0, 1.0]]
    L = _cholesky(I)
    assert abs(L[0][0] - 1.0) < 1e-9
    assert abs(L[1][1] - 1.0) < 1e-9
    assert abs(L[1][0]) < 1e-9
    assert abs(L[0][1]) < 1e-9  # upper triangle is zero


def test_cholesky_3x3():
    """Verify L @ L.T reconstructs the original matrix."""
    m = [
        [1.0, 0.5, 0.3],
        [0.5, 1.0, 0.4],
        [0.3, 0.4, 1.0],
    ]
    L = _cholesky(m)
    n = 3
    # Reconstruct L @ L^T
    reconstructed = [[sum(L[i][k] * L[j][k] for k in range(n)) for j in range(n)] for i in range(n)]
    for i in range(n):
        for j in range(n):
            assert abs(reconstructed[i][j] - m[i][j]) < 1e-9, \
                f"Mismatch at [{i}][{j}]: {reconstructed[i][j]} != {m[i][j]}"


def test_corr_matrix_diagonal():
    m = _corr_matrix(["AAPL", "GOOGL"])
    assert m[0][0] == 1.0
    assert m[1][1] == 1.0
    assert m[0][1] == m[1][0]   # symmetric


def test_corr_matrix_known_pair():
    """AAPL-GOOGL correlation is 0.60 per seed_prices.py."""
    m = _corr_matrix(["AAPL", "GOOGL"])
    assert abs(m[0][1] - 0.60) < 1e-9


def test_corr_matrix_unknown_pair_uses_default():
    """Unknown ticker pairs fall back to DEFAULT_CORR (0.30)."""
    from app.market.seed_prices import DEFAULT_CORR
    m = _corr_matrix(["FAKE1", "FAKE2"])
    assert m[0][1] == DEFAULT_CORR
    assert m[1][0] == DEFAULT_CORR


def test_corr_matrix_reverse_lookup():
    """Correlation is looked up with both (A, B) and (B, A) key ordering."""
    m_ab = _corr_matrix(["AAPL", "GOOGL"])
    m_ba = _corr_matrix(["GOOGL", "AAPL"])
    # Both orderings should give the same off-diagonal value
    assert abs(m_ab[0][1] - m_ba[0][1]) < 1e-9


@pytest.mark.asyncio
async def test_set_tickers_adds_new_without_resetting_existing():
    """Re-adding AAPL after it already has a price should keep the existing price."""
    sim = SimulatorSource(seed=1, tick_interval_s=0.01)
    await sim.set_tickers(["AAPL"])
    await sim.start()
    await asyncio.sleep(0.05)
    price_before = sim._prices.get("AAPL")
    # Add GOOGL while keeping AAPL
    await sim.set_tickers(["AAPL", "GOOGL"])
    price_after = sim._prices.get("AAPL")
    await sim.stop()
    assert price_before == price_after   # AAPL price was preserved


@pytest.mark.asyncio
async def test_empty_ticker_list_produces_no_ticks():
    """set_tickers([]) → no ticks emitted."""
    sim = SimulatorSource(seed=1, tick_interval_s=0.01)
    await sim.set_tickers([])
    await sim.start()
    await asyncio.sleep(0.05)
    await sim.stop()
    # No crashes and no latest entries
    assert sim.latest("AAPL") is None
