"""Tests for lazy init, schema, and seed data."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db import (
    DEFAULT_CASH,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST,
    connect,
    ensure_initialized,
    init_db,
)


EXPECTED_TABLES = {
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def test_init_creates_all_tables(raw_conn: sqlite3.Connection) -> None:
    init_db(raw_conn)
    assert EXPECTED_TABLES.issubset(_table_names(raw_conn))


def test_init_seeds_default_user(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT id, cash_balance FROM users_profile WHERE id = ?",
        (DEFAULT_USER_ID,),
    ).fetchone()
    assert row is not None
    assert row["id"] == DEFAULT_USER_ID
    assert row["cash_balance"] == DEFAULT_CASH


def test_init_seeds_default_watchlist(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ?",
        (DEFAULT_USER_ID,),
    ).fetchall()
    tickers = {r["ticker"] for r in rows}
    assert tickers == set(DEFAULT_WATCHLIST)


def test_init_is_idempotent(db_path: Path) -> None:
    conn = ensure_initialized(db_path)
    conn.close()
    # Second call must not raise, must not duplicate seed rows.
    conn = ensure_initialized(db_path)
    user_count = conn.execute(
        "SELECT COUNT(*) FROM users_profile"
    ).fetchone()[0]
    watch_count = conn.execute(
        "SELECT COUNT(*) FROM watchlist"
    ).fetchone()[0]
    assert user_count == 1
    assert watch_count == len(DEFAULT_WATCHLIST)
    conn.close()


def test_init_preserves_modified_cash(db_path: Path) -> None:
    """If a user changed cash, re-running init should not overwrite it."""
    conn = ensure_initialized(db_path)
    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (1234.56, DEFAULT_USER_ID),
    )
    conn.close()

    conn = ensure_initialized(db_path)
    row = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?",
        (DEFAULT_USER_ID,),
    ).fetchone()
    assert row["cash_balance"] == 1234.56
    conn.close()


def test_db_path_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "custom" / "finally.db"
    monkeypatch.setenv("DB_PATH", str(target))
    from app.db import get_db_path

    assert get_db_path() == target

    conn = ensure_initialized()
    try:
        assert target.exists()
    finally:
        conn.close()


def test_watchlist_unique_constraint(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) "
            "VALUES ('dup1', ?, 'AAPL', '2024-01-01T00:00:00+00:00')",
            (DEFAULT_USER_ID,),
        )


def test_positions_unique_constraint(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
        "VALUES ('p1', ?, 'AAPL', 1, 1, '2024-01-01T00:00:00+00:00')",
        (DEFAULT_USER_ID,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES ('p2', ?, 'AAPL', 2, 2, '2024-01-01T00:00:00+00:00')",
            (DEFAULT_USER_ID,),
        )


def test_trade_side_check_constraint(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES ('t1', ?, 'AAPL', 'short', 1, 1, '2024-01-01T00:00:00+00:00')",
            (DEFAULT_USER_ID,),
        )


def test_chat_role_check_constraint(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES ('c1', ?, 'system', 'x', NULL, '2024-01-01T00:00:00+00:00')",
            (DEFAULT_USER_ID,),
        )
