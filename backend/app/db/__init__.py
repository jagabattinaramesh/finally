"""SQLite database layer for FinAlly.

Public surface:

- ``connect`` / ``get_db_path`` — open a connection (uses env ``DB_PATH``).
- ``init_db`` — create tables and seed defaults; idempotent.
- ``ensure_initialized`` — convenience: open + init + return connection.
- Repository functions for each table (see ``repository`` submodule).
"""

from .connection import DEFAULT_DB_PATH, connect, get_db_path
from .repository import (
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
from .schema import (
    DEFAULT_CASH,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST,
    init_db,
)


def ensure_initialized(db_path=None):
    """Open a connection and ensure schema + seed exist. Returns the connection."""
    conn = connect(db_path)
    init_db(conn)
    return conn


__all__ = [
    "DEFAULT_CASH",
    "DEFAULT_DB_PATH",
    "DEFAULT_USER_ID",
    "DEFAULT_WATCHLIST",
    "add_watchlist",
    "connect",
    "delete_position",
    "ensure_initialized",
    "get_db_path",
    "get_position",
    "get_user",
    "init_db",
    "insert_chat_message",
    "insert_snapshot",
    "insert_trade",
    "list_chat_messages",
    "list_positions",
    "list_snapshots",
    "list_trades",
    "list_watchlist",
    "remove_watchlist",
    "update_cash",
    "upsert_position",
]
