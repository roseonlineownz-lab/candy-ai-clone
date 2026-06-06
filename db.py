#!/usr/bin/env python3
"""Async SQLite persistence for chat sessions and messages.

Replaces the in-memory ``_sessions`` dict so conversations survive
restarts.  All public functions are async and use a module-level
connection pool (single writer, many readers — fine for SQLite).
"""

from __future__ import annotations

import time
from typing import Optional

import aiosqlite

from config import DB_PATH

_db: Optional[aiosqlite.Connection] = None

# ── bootstrap ────────────────────────────────────────────────────────

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    mode       TEXT NOT NULL DEFAULT 'normal',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT    NOT NULL REFERENCES sessions(id),
    role       TEXT    NOT NULL,
    text       TEXT    NOT NULL,
    persona    TEXT,
    model      TEXT,
    timestamp  REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages(session_id, timestamp);
"""


async def get_db() -> aiosqlite.Connection:
    """Return (and lazily create) the singleton DB connection."""
    global _db
    if _db is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _db = await aiosqlite.connect(str(DB_PATH))
        _db.row_factory = aiosqlite.Row
        await _db.executescript(_SCHEMA)
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        await _db.commit()
    return _db


async def close_db() -> None:
    """Gracefully close the DB connection (call on shutdown)."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


# ── sessions ─────────────────────────────────────────────────────────

async def ensure_session(session_id: str, mode: str = "normal") -> None:
    """Create a session row if it doesn't exist yet."""
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO sessions (id, mode, created_at) VALUES (?, ?, ?)",
        (session_id, mode, time.time()),
    )
    await db.commit()


# ── messages ─────────────────────────────────────────────────────────

async def add_message(
    session_id: str,
    role: str,
    text: str,
    *,
    persona: Optional[str] = None,
    model: Optional[str] = None,
) -> int:
    """Append a message to a session. Returns the new message id."""
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO messages (session_id, role, text, persona, model, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, role, text, persona, model, time.time()),
    )
    await db.commit()
    return cur.lastrowid  # type: ignore[return-value]


async def get_history(session_id: str, limit: int = 200) -> list[dict]:
    """Return the most recent *limit* messages for a session."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT role, text, persona, model, timestamp "
        "FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
        (session_id, limit),
    )
    # Return in chronological order
    return [dict(r) for r in reversed(rows)]


async def clear_session(session_id: str) -> None:
    """Delete all messages (and the session row) for *session_id*."""
    db = await get_db()
    await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    await db.commit()
