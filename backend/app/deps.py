"""FastAPI dependency providers wired from app.state.

The market source and a path to the SQLite DB live on app.state. Routes
declare these via Depends() so tests can override them with TestClient.
"""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request

from app.db import get_db_path
from app.market import MarketSource


async def get_db(request: Request) -> AsyncIterator[sqlite3.Connection]:
    """Open a per-request sqlite3 connection.

    Async generator so the connection is created on the event-loop thread,
    avoiding sqlite3's same-thread restriction across async endpoints.
    """
    override = getattr(request.app.state, "db_path", None)
    path = Path(override) if override else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()


def get_market(request: Request) -> MarketSource:
    return request.app.state.market
