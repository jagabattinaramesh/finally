"""Tests for repository CRUD functions."""

from __future__ import annotations

import sqlite3

import pytest

from app.db import (
    DEFAULT_CASH,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST,
    add_watchlist,
    delete_position,
    get_position,
    get_user,
    insert_chat_message,
    insert_snapshot,
    insert_trade,
    list_chat_messages,
    list_positions,
    list_snapshots,
    list_trades,
    list_watchlist,
    remove_watchlist,
    update_cash,
    upsert_position,
)


# ----- users_profile ----------------------------------------------------------

def test_get_user_default(conn: sqlite3.Connection) -> None:
    user = get_user(conn)
    assert user is not None
    assert user["id"] == DEFAULT_USER_ID
    assert user["cash_balance"] == DEFAULT_CASH


def test_update_cash(conn: sqlite3.Connection) -> None:
    update_cash(conn, 5_000.0)
    assert get_user(conn)["cash_balance"] == 5_000.0


# ----- watchlist --------------------------------------------------------------

def test_list_watchlist_seeded(conn: sqlite3.Connection) -> None:
    rows = list_watchlist(conn)
    assert {r["ticker"] for r in rows} == set(DEFAULT_WATCHLIST)


def test_add_watchlist_new(conn: sqlite3.Connection) -> None:
    row = add_watchlist(conn, "pypl")
    assert row["ticker"] == "PYPL"
    tickers = [r["ticker"] for r in list_watchlist(conn)]
    assert "PYPL" in tickers


def test_add_watchlist_duplicate_is_noop(conn: sqlite3.Connection) -> None:
    before = list_watchlist(conn)
    row = add_watchlist(conn, "AAPL")
    after = list_watchlist(conn)
    assert row["ticker"] == "AAPL"
    assert len(before) == len(after)


def test_remove_watchlist(conn: sqlite3.Connection) -> None:
    assert remove_watchlist(conn, "AAPL") is True
    assert "AAPL" not in [r["ticker"] for r in list_watchlist(conn)]
    assert remove_watchlist(conn, "AAPL") is False


# ----- positions --------------------------------------------------------------

def test_position_lifecycle(conn: sqlite3.Connection) -> None:
    assert get_position(conn, "AAPL") is None

    upsert_position(conn, "AAPL", quantity=10, avg_cost=190.0)
    pos = get_position(conn, "AAPL")
    assert pos["quantity"] == 10
    assert pos["avg_cost"] == 190.0

    # Update path
    upsert_position(conn, "AAPL", quantity=15, avg_cost=195.0)
    pos = get_position(conn, "AAPL")
    assert pos["quantity"] == 15
    assert pos["avg_cost"] == 195.0

    # Listing
    positions = list_positions(conn)
    assert len(positions) == 1
    assert positions[0]["ticker"] == "AAPL"

    # Delete
    assert delete_position(conn, "AAPL") is True
    assert get_position(conn, "AAPL") is None
    assert delete_position(conn, "AAPL") is False


def test_position_supports_fractional_shares(conn: sqlite3.Connection) -> None:
    upsert_position(conn, "TSLA", quantity=0.5, avg_cost=175.25)
    pos = get_position(conn, "TSLA")
    assert pos["quantity"] == 0.5
    assert pos["avg_cost"] == 175.25


# ----- trades -----------------------------------------------------------------

def test_insert_and_list_trades(conn: sqlite3.Connection) -> None:
    insert_trade(conn, "AAPL", "buy", quantity=10, price=190.0)
    insert_trade(conn, "AAPL", "sell", quantity=5, price=200.0)
    trades = list_trades(conn)
    assert len(trades) == 2
    # Newest first
    assert trades[0]["side"] == "sell"
    assert trades[1]["side"] == "buy"


def test_trade_rejects_bad_side(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        insert_trade(conn, "AAPL", "short", quantity=1, price=1)


def test_list_trades_limit(conn: sqlite3.Connection) -> None:
    for i in range(5):
        insert_trade(conn, "AAPL", "buy", quantity=1, price=float(i + 1))
    trades = list_trades(conn, limit=2)
    assert len(trades) == 2


# ----- portfolio_snapshots ----------------------------------------------------

def test_snapshots(conn: sqlite3.Connection) -> None:
    insert_snapshot(conn, total_value=10_000.0)
    insert_snapshot(conn, total_value=10_500.0)
    snaps = list_snapshots(conn)
    assert len(snaps) == 2
    assert snaps[0]["total_value"] == 10_000.0
    assert snaps[1]["total_value"] == 10_500.0


# ----- chat_messages ----------------------------------------------------------

def test_chat_messages_roundtrip(conn: sqlite3.Connection) -> None:
    insert_chat_message(conn, "user", "buy 10 AAPL please")
    insert_chat_message(
        conn,
        "assistant",
        "Done.",
        actions={"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}]},
    )
    msgs = list_chat_messages(conn)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["actions"] is None
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["actions"] == {
        "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}]
    }


def test_chat_message_rejects_bad_role(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        insert_chat_message(conn, "system", "nope")


def test_chat_messages_limit_returns_most_recent_ordered_oldest_first(
    conn: sqlite3.Connection,
) -> None:
    for i in range(5):
        insert_chat_message(conn, "user", f"m{i}")
    msgs = list_chat_messages(conn, limit=3)
    assert [m["content"] for m in msgs] == ["m2", "m3", "m4"]
