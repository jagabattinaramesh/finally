def test_initial_portfolio(client):
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert body["cash_balance"] == 10000.0
    assert body["positions"] == []
    assert body["total_value"] == 10000.0


def test_buy_then_portfolio(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trade"]["side"] == "buy"
    assert body["trade"]["quantity"] == 5
    assert body["cash_balance"] == 10000.0 - 5 * 200.0

    r = client.get("/api/portfolio")
    pos = r.json()["positions"]
    assert len(pos) == 1
    assert pos[0]["ticker"] == "AAPL"
    assert pos[0]["quantity"] == 5
    assert pos[0]["avg_cost"] == 200.0


def test_weighted_avg_cost(client, market):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 5})
    market.set_price("AAPL", 220.0)
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 5})
    pos = client.get("/api/portfolio").json()["positions"][0]
    assert pos["quantity"] == 10
    assert pos["avg_cost"] == 210.0  # (5*200 + 5*220) / 10


def test_sell_partial_and_full(client):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 4})
    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 1})
    assert r.status_code == 200
    pos = client.get("/api/portfolio").json()["positions"]
    assert pos[0]["quantity"] == 3

    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 3})
    assert r.status_code == 200
    assert client.get("/api/portfolio").json()["positions"] == []


def test_insufficient_cash(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1000})
    assert r.status_code == 400
    assert "insufficient cash" in r.json()["detail"]


def test_insufficient_shares(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "sell", "quantity": 1})
    assert r.status_code == 400
    assert "insufficient shares" in r.json()["detail"]


def test_unknown_ticker(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "ZZZZ", "side": "buy", "quantity": 1})
    assert r.status_code == 400
    assert "no live price" in r.json()["detail"]


def test_invalid_side(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "hold", "quantity": 1})
    assert r.status_code == 400


def test_history_records_snapshots_on_trade(client):
    assert client.get("/api/portfolio/history").json() == []
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 1})
    history = client.get("/api/portfolio/history").json()
    assert len(history) == 1
    assert history[0]["total_value"] > 0
