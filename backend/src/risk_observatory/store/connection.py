"""SQLite connection helper. Auto-applies schema on first open."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

from ..config import SETTINGS

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


_init_lock = Lock()
_initialised: set[str] = set()


def _ensure_schema(conn: sqlite3.Connection, db_key: str) -> None:
    with _init_lock:
        if db_key in _initialised:
            return
        conn.executescript(_SCHEMA_PATH.read_text())
        conn.commit()
        _initialised.add(db_key)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open (and lazily initialise) the observatory database."""
    path = db_path or SETTINGS.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_schema(conn, str(path))
    return conn
