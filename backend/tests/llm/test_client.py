"""Parsing of LLM JSON responses, including missing-message coercion."""

from __future__ import annotations

from app.llm.client import _parse_response


def test_parses_full_payload():
    raw = (
        '{"message":"Done.",'
        '"trades":[{"ticker":"AAPL","side":"buy","quantity":2}],'
        '"watchlist_changes":[]}'
    )
    r = _parse_response(raw)
    assert r.message == "Done."
    assert r.trades[0].ticker == "AAPL"


def test_missing_message_with_watchlist_add_synthesises_summary():
    raw = '{"trades":[],"watchlist_changes":[{"ticker":"AAPL","action":"add"}]}'
    r = _parse_response(raw)
    assert "AAPL" in r.message
    assert "watchlist" in r.message.lower()
    assert r.watchlist_changes[0].ticker == "AAPL"


def test_missing_message_with_no_actions_falls_back_to_ok():
    raw = '{"trades":[],"watchlist_changes":[]}'
    r = _parse_response(raw)
    assert r.message == "OK."
    assert r.trades == []
    assert r.watchlist_changes == []


def test_blank_message_is_coerced():
    raw = '{"message":"   ","trades":[],"watchlist_changes":[]}'
    r = _parse_response(raw)
    assert r.message == "OK."


def test_missing_message_with_trade_summarises_trade():
    raw = '{"trades":[{"ticker":"TSLA","side":"sell","quantity":3}]}'
    r = _parse_response(raw)
    assert "TSLA" in r.message
    assert "Selling" in r.message
    assert r.trades[0].side == "sell"
