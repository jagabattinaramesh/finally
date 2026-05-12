"""SQLite connection helper.

DB path comes from env ``DB_PATH``. Defaults to ``db/finally.db`` resolved
relative to the current working directory, which lines up with both local
development and the container layout (``/app/db/finally.db``).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = "db/finally.db"


def get_db_path() -> Path:
    """Resolve the configured SQLite file path."""
    return Path(os.environ.get("DB_PATH", DEFAULT_DB_PATH))


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with sensible defaults.

    - ``row_factory`` set to ``sqlite3.Row`` for dict-like access.
    - Foreign keys enabled.
    - WAL journal mode for better concurrent reads.
    """
    path = Path(db_path) if db_path is not None else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn
