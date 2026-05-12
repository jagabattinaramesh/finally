"""End-to-end /api/chat behaviour with LLM_MOCK=true."""

from __future__ import annotations

from app.db import connect, list_chat_messages


def test_chat_buy_executes_trade(client, db_path):
    r = client.post("/api/chat", json={"message": "buy 2 shares of AAPL"})
    assert r.status_code == 200, r.text
    body = r.json()

    assert "Buying 2 shares of AAPL" in body["message"]
    assert len(body["trades"]) == 1
    assert body["trades"][0]["ticker"] == "AAPL"
    assert len(body["executed_trades"]) == 1
    assert body["executed_trades"][0]["side"] == "buy"
    assert body["executed_trades"][0]["quantity"] == 2.0
    assert body["errors"] == []

    pos = client.get("/api/portfolio").json()["positions"]
    assert len(pos) == 1
    assert pos[0]["ticker"] == "AAPL"
    assert pos[0]["quantity"] == 2.0


def test_chat_buy_with_insufficient_cash_reports_error(client):
    r = client.post("/api/chat", json={"message": "buy 1000 AAPL"})
    assert r.status_code == 200
    body = r.json()
    assert body["executed_trades"] == []
    assert len(body["errors"]) == 1
    assert "insufficient cash" in body["errors"][0]

    assert client.get("/api/portfolio").json()["positions"] == []


def test_chat_sell_with_no_position_reports_error(client):
    r = client.post("/api/chat", json={"message": "sell 5 AAPL"})
    body = r.json()
    assert body["executed_trades"] == []
    assert "insufficient shares" in body["errors"][0]


def test_chat_watchlist_add(client, db_path):
    r = client.post("/api/chat", json={"message": "add PYPL"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["applied_watchlist_changes"]) == 1
    assert body["applied_watchlist_changes"][0] == {"ticker": "PYPL", "action": "add"}

    tickers = [w["ticker"] for w in client.get("/api/watchlist").json()]
    assert "PYPL" in tickers


def test_chat_watchlist_remove_missing_reports_error(client):
    r = client.post("/api/chat", json={"message": "remove ZZZZ"})
    body = r.json()
    assert body["applied_watchlist_changes"] == []
    assert any("not in watchlist" in e for e in body["errors"])


def test_chat_fallback_message(client):
    r = client.post("/api/chat", json={"message": "hello there"})
    body = r.json()
    assert body["message"] == "Mock LLM: I received your message."
    assert body["trades"] == []
    assert body["executed_trades"] == []


def test_chat_persists_history(client, db_path):
    client.post("/api/chat", json={"message": "buy 1 AAPL"})
    client.post("/api/chat", json={"message": "hello"})

    conn = connect(db_path)
    try:
        msgs = list_chat_messages(conn)
    finally:
        conn.close()

    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert msgs[0]["content"] == "buy 1 AAPL"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["actions"] is not None
    assert msgs[1]["actions"]["executed_trades"][0]["ticker"] == "AAPL"


def test_chat_empty_message_rejected(client):
    r = client.post("/api/chat", json={"message": ""})
    assert r.status_code == 422
