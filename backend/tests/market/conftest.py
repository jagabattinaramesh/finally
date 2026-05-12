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
        src._client = FakeMassiveTransport().build_client()

    await src.set_tickers(["AAPL", "GOOGL"])
    await src.start()
    yield src
    await src.stop()
