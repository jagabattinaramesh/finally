import os

from .interface import MarketSource
from .massive import MassiveSource
from .simulator import SimulatorSource


def build_market_source() -> MarketSource:
    """Return the market source configured by environment.

    MASSIVE_API_KEY set and non-empty → MassiveSource (real data)
    otherwise                         → SimulatorSource (synthetic)

    This is the single place that reads the environment variable.
    All other code receives a MarketSource and doesn't know which impl it is.
    """
    key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if key:
        return MassiveSource(api_key=key)
    return SimulatorSource()
