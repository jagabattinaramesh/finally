"""Canned HTTP responses for MassiveSource unit tests."""
import httpx

_CANNED_SNAPSHOT = {
    "status": "OK",
    "count": 2,
    "tickers": [
        {
            "ticker": "AAPL",
            "lastTrade": {"p": 190.73},
            "day": {"c": 190.73},
            "prevDay": {"c": 189.50},
            "todaysChangePerc": 0.65,
            "updated": 1715444532000000000,
        },
        {
            "ticker": "GOOGL",
            "lastTrade": {"p": 175.12},
            "day": {"c": 175.12},
            "prevDay": {"c": 174.00},
            "todaysChangePerc": 0.64,
            "updated": 1715444532000000000,
        },
    ],
}


class FakeMassiveTransport(httpx.MockTransport):
    def __init__(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_CANNED_SNAPSHOT,
                headers={"content-type": "application/json"},
            )
        super().__init__(handler=handler)

    def build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://api.massive.com",
            transport=self,
            timeout=5.0,
        )
