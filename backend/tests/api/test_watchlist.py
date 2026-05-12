def test_default_watchlist_seeded(client):
    r = client.get("/api/watchlist")
    assert r.status_code == 200
    tickers = sorted(x["ticker"] for x in r.json())
    assert tickers == sorted([
        "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
        "NVDA", "META", "JPM", "V", "NFLX",
    ])
    aapl = next(x for x in r.json() if x["ticker"] == "AAPL")
    assert aapl["price"] == 200.0


def test_add_ticker_uppercases_and_dedupes(client):
    r = client.post("/api/watchlist", json={"ticker": "pypl"})
    assert r.status_code == 200
    assert r.json()["ticker"] == "PYPL"

    r = client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert r.status_code == 200

    tickers = [x["ticker"] for x in client.get("/api/watchlist").json()]
    assert tickers.count("PYPL") == 1


def test_delete_ticker(client):
    r = client.delete("/api/watchlist/AAPL")
    assert r.status_code == 200
    tickers = [x["ticker"] for x in client.get("/api/watchlist").json()]
    assert "AAPL" not in tickers


def test_delete_missing_ticker(client):
    r = client.delete("/api/watchlist/ZZZ")
    assert r.status_code == 404
