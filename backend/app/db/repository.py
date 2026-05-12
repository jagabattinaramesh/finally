"""CRUD functions over the SQLite schema.

All functions take a ``sqlite3.Connection`` explicitly so callers control
the connection lifecycle and transactions.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .schema import DEFAULT_USER_ID


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


# ----- users_profile ----------------------------------------------------------

def get_user(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def update_cash(conn: sqlite3.Connection, cash_balance: float, user_id: str = DEFAULT_USER_ID) -> None:
    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (cash_balance, user_id),
    )


# ----- watchlist --------------------------------------------------------------

def list_watchlist(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, user_id, ticker, added_at FROM watchlist "
        "WHERE user_id = ? ORDER BY added_at",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_watchlist(conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID) -> dict[str, Any]:
    """Insert a ticker into the watchlist. Returns the new (or existing) row.

    Raises ``sqlite3.IntegrityError`` if a hard constraint fails. Duplicate
    inserts are treated as no-ops and the existing row is returned.
    """
    ticker = ticker.upper()
    row_id = _new_id()
    now = _now()
    try:
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) "
            "VALUES (?, ?, ?, ?)",
            (row_id, user_id, ticker, now),
        )
    except sqlite3.IntegrityError:
        pass
    row = conn.execute(
        "SELECT id, user_id, ticker, added_at FROM watchlist "
        "WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
    return dict(row)


def remove_watchlist(conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    cur = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker.upper()),
    )
    return cur.rowcount > 0


# ----- positions --------------------------------------------------------------

def list_positions(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, user_id, ticker, quantity, avg_cost, updated_at "
        "FROM positions WHERE user_id = ? ORDER BY ticker",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_position(conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT id, user_id, ticker, quantity, avg_cost, updated_at "
        "FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker.upper()),
    ).fetchone()
    return dict(row) if row else None


def upsert_position(
    conn: sqlite3.Connection,
    ticker: str,
    quantity: float,
    avg_cost: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    """Insert or update a position row. Returns the resulting row."""
    ticker = ticker.upper()
    now = _now()
    existing = get_position(conn, ticker, user_id)
    if existing is None:
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_new_id(), user_id, ticker, quantity, avg_cost, now),
        )
    else:
        conn.execute(
            "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
            "WHERE user_id = ? AND ticker = ?",
            (quantity, avg_cost, now, user_id, ticker),
        )
    return get_position(conn, ticker, user_id)  # type: ignore[return-value]


def delete_position(conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    cur = conn.execute(
        "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker.upper()),
    )
    return cur.rowcount > 0


# ----- trades -----------------------------------------------------------------

def insert_trade(
    conn: sqlite3.Connection,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
    row_id = _new_id()
    now = _now()
    conn.execute(
        "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (row_id, user_id, ticker.upper(), side, quantity, price, now),
    )
    return {
        "id": row_id,
        "user_id": user_id,
        "ticker": ticker.upper(),
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": now,
    }


def list_trades(
    conn: sqlite3.Connection,
    limit: int | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> list[dict[str, Any]]:
    sql = (
        "SELECT id, user_id, ticker, side, quantity, price, executed_at "
        "FROM trades WHERE user_id = ? ORDER BY executed_at DESC"
    )
    params: tuple[Any, ...] = (user_id,)
    if limit is not None:
        sql += " LIMIT ?"
        params = (user_id, limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ----- portfolio_snapshots ----------------------------------------------------

def insert_snapshot(
    conn: sqlite3.Connection,
    total_value: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    row_id = _new_id()
    now = _now()
    conn.execute(
        "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?, ?)",
        (row_id, user_id, total_value, now),
    )
    return {
        "id": row_id,
        "user_id": user_id,
        "total_value": total_value,
        "recorded_at": now,
    }


def list_snapshots(
    conn: sqlite3.Connection,
    limit: int | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> list[dict[str, Any]]:
    sql = (
        "SELECT id, user_id, total_value, recorded_at "
        "FROM portfolio_snapshots WHERE user_id = ? ORDER BY recorded_at"
    )
    params: tuple[Any, ...] = (user_id,)
    if limit is not None:
        sql += " LIMIT ?"
        params = (user_id, limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ----- chat_messages ----------------------------------------------------------

def insert_chat_message(
    conn: sqlite3.Connection,
    role: str,
    content: str,
    actions: dict[str, Any] | list[Any] | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    if role not in ("user", "assistant"):
        raise ValueError(f"role must be 'user' or 'assistant', got {role!r}")
    row_id = _new_id()
    now = _now()
    actions_json = json.dumps(actions) if actions is not None else None
    conn.execute(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (row_id, user_id, role, content, actions_json, now),
    )
    return {
        "id": row_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "actions": actions,
        "created_at": now,
    }


def list_chat_messages(
    conn: sqlite3.Connection,
    limit: int | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> list[dict[str, Any]]:
    """Return chat messages oldest-first. ``actions`` is parsed back to Python."""
    sql = (
        "SELECT id, user_id, role, content, actions, created_at "
        "FROM chat_messages WHERE user_id = ? ORDER BY created_at"
    )
    params: tuple[Any, ...] = (user_id,)
    if limit is not None:
        sql = (
            "SELECT * FROM ("
            "  SELECT id, user_id, role, content, actions, created_at "
            "  FROM chat_messages WHERE user_id = ? "
            "  ORDER BY created_at DESC LIMIT ?"
            ") ORDER BY created_at"
        )
        params = (user_id, limit)
    rows = conn.execute(sql, params).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["actions"] = json.loads(d["actions"]) if d["actions"] else None
        out.append(d)
    return out
