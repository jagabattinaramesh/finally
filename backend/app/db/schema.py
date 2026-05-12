"""Schema definition, lazy initialization, and default seed data."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

DEFAULT_USER_ID = "default"
DEFAULT_CASH = 10_000.0
DEFAULT_WATCHLIST = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users_profile (
    id            TEXT PRIMARY KEY,
    cash_balance  REAL NOT NULL DEFAULT 10000.0,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id        TEXT PRIMARY KEY,
    user_id   TEXT NOT NULL DEFAULT 'default',
    ticker    TEXT NOT NULL,
    added_at  TEXT NOT NULL,
    UNIQUE (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS positions (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL DEFAULT 'default',
    ticker      TEXT NOT NULL,
    quantity    REAL NOT NULL,
    avg_cost    REAL NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS trades (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL DEFAULT 'default',
    ticker       TEXT NOT NULL,
    side         TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity     REAL NOT NULL,
    price        REAL NOT NULL,
    executed_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL DEFAULT 'default',
    total_value  REAL NOT NULL,
    recorded_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL DEFAULT 'default',
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    actions     TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_user_time
    ON trades (user_id, executed_at);

CREATE INDEX IF NOT EXISTS idx_snapshots_user_time
    ON portfolio_snapshots (user_id, recorded_at);

CREATE INDEX IF NOT EXISTS idx_chat_user_time
    ON chat_messages (user_id, created_at);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables (idempotent) and seed defaults if empty."""
    conn.executescript(SCHEMA_SQL)
    _seed_defaults(conn)


def _seed_defaults(conn: sqlite3.Connection) -> None:
    """Insert the default user and watchlist tickers if not already present."""
    now = _utc_now()

    cur = conn.execute(
        "SELECT 1 FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
    )
    if cur.fetchone() is None:
        conn.execute(
            "INSERT INTO users_profile (id, cash_balance, created_at) "
            "VALUES (?, ?, ?)",
            (DEFAULT_USER_ID, DEFAULT_CASH, now),
        )

    cur = conn.execute(
        "SELECT COUNT(*) FROM watchlist WHERE user_id = ?", (DEFAULT_USER_ID,)
    )
    if cur.fetchone()[0] == 0:
        import uuid
        rows = [
            (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now)
            for ticker in DEFAULT_WATCHLIST
        ]
        conn.executemany(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
