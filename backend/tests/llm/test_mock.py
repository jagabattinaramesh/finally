"""Deterministic mock LLM response patterns."""

from __future__ import annotations

import pytest

from app.llm.mock import mock_response


@pytest.mark.parametrize("text,ticker,qty", [
    ("buy 10 AAPL", "AAPL", 10),
    ("buy 2 shares of AAPL", "AAPL", 2),
    ("BUY 5 GOOGL", "GOOGL", 5),
    ("please buy 1.5 TSLA now", "TSLA", 1.5),
])
def test_buy_pattern(text, ticker, qty):
    r = mock_response(text)
    assert len(r.trades) == 1
    assert r.trades[0].ticker == ticker
    assert r.trades[0].side == "buy"
    assert r.trades[0].quantity == qty
    assert ticker in r.message


@pytest.mark.parametrize("text,ticker,qty", [
    ("sell 5 AAPL", "AAPL", 5),
    ("sell 3 shares of TSLA", "TSLA", 3),
])
def test_sell_pattern(text, ticker, qty):
    r = mock_response(text)
    assert len(r.trades) == 1
    assert r.trades[0].side == "sell"
    assert r.trades[0].ticker == ticker
    assert r.trades[0].quantity == qty


@pytest.mark.parametrize("text,ticker", [
    ("add PYPL", "PYPL"),
    ("watch NFLX", "NFLX"),
])
def test_watchlist_add(text, ticker):
    r = mock_response(text)
    assert r.trades == []
    assert len(r.watchlist_changes) == 1
    assert r.watchlist_changes[0].ticker == ticker
    assert r.watchlist_changes[0].action == "add"


def test_watchlist_remove():
    r = mock_response("remove TSLA")
    assert r.watchlist_changes[0].action == "remove"
    assert r.watchlist_changes[0].ticker == "TSLA"


def test_fallback():
    r = mock_response("hello there")
    assert r.message == "Mock LLM: I received your message."
    assert r.trades == []
    assert r.watchlist_changes == []


def test_determinism():
    """Same input → identical output, every time."""
    a = mock_response("buy 2 shares of AAPL").model_dump()
    b = mock_response("buy 2 shares of AAPL").model_dump()
    c = mock_response("buy 2 shares of AAPL").model_dump()
    assert a == b == c
