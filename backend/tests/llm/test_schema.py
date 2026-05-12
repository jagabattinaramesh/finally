"""Pydantic schema parsing for ChatResponse."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.llm.schema import ChatResponse


def test_minimal_message_only():
    r = ChatResponse.model_validate({"message": "hi"})
    assert r.message == "hi"
    assert r.trades == []
    assert r.watchlist_changes == []


def test_full_payload():
    r = ChatResponse.model_validate({
        "message": "Done.",
        "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 2}],
        "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
    })
    assert r.trades[0].ticker == "AAPL"
    assert r.trades[0].side == "buy"
    assert r.trades[0].quantity == 2.0
    assert r.watchlist_changes[0].action == "add"


def test_rejects_bad_side():
    with pytest.raises(ValidationError):
        ChatResponse.model_validate({
            "message": "x",
            "trades": [{"ticker": "AAPL", "side": "hold", "quantity": 1}],
        })


def test_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        ChatResponse.model_validate({
            "message": "x",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 0}],
        })


def test_rejects_bad_watchlist_action():
    with pytest.raises(ValidationError):
        ChatResponse.model_validate({
            "message": "x",
            "watchlist_changes": [{"ticker": "AAPL", "action": "delete"}],
        })


def test_json_roundtrip():
    payload = '{"message":"ok","trades":[{"ticker":"AAPL","side":"sell","quantity":1.5}]}'
    r = ChatResponse.model_validate_json(payload)
    assert r.trades[0].quantity == 1.5
