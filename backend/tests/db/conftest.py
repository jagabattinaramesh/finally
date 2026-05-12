"""Fixtures for db tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db import connect, ensure_initialized, init_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "finally.db"


@pytest.fixture
def raw_conn(db_path: Path) -> sqlite3.Connection:
    """Plain connection, schema not yet created."""
    conn = connect(db_path)
    yield conn
    conn.close()


@pytest.fixture
def conn(db_path: Path) -> sqlite3.Connection:
    """Connection with schema + seed data already applied."""
    conn = ensure_initialized(db_path)
    yield conn
    conn.close()
