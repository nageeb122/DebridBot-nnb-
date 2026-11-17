"""SQLite-backed Telegram user registry and access-control helpers."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("USER_DB_PATH", "data/users.sqlite3"))


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS access (
                user_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL CHECK(status IN ('approved', 'blocked')),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )


def record_activity(user_id: int, username: str | None, first_name: str | None) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users(user_id, username, first_name, message_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_seen=CURRENT_TIMESTAMP,
                message_count=users.message_count + 1
            """,
            (user_id, username, first_name),
        )


def _status(conn: sqlite3.Connection, user_id: int) -> str | None:
    row = conn.execute("SELECT status FROM access WHERE user_id=?", (user_id,)).fetchone()
    return row["status"] if row else None


def is_authorized(
    user_id: int, admin_ids: frozenset[int], allowed_ids: frozenset[int]
) -> bool:
    if user_id in admin_ids:
        return True
    default_mode = "restricted" if allowed_ids else "open"
    with _connect() as conn:
        status = _status(conn, user_id)
        if status == "blocked":
            return False
        row = conn.execute(
            "SELECT value FROM settings WHERE key='access_mode'"
        ).fetchone()
        mode = row["value"] if row else default_mode
        if mode == "open":
            return True
        return user_id in allowed_ids or status == "approved"


def get_access_mode(default_mode: str) -> str:
    with _connect() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key='access_mode'"
        ).fetchone()
        return row["value"] if row else default_mode


def set_access_mode(mode: str) -> None:
    if mode not in {"open", "restricted"}:
        raise ValueError("mode must be open or restricted")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value) VALUES ('access_mode', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (mode,),
        )


def set_user_status(user_id: int, status: str) -> None:
    if status not in {"approved", "blocked"}:
        raise ValueError("status must be approved or blocked")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO access(user_id, status) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                status=excluded.status, updated_at=CURRENT_TIMESTAMP
            """,
            (user_id, status),
        )


def clear_user_status(user_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM access WHERE user_id=?", (user_id,))


def list_users(limit: int = 30) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT u.user_id, u.username, u.first_name, u.last_seen,
                   u.message_count, a.status
            FROM users u
            LEFT JOIN access a ON a.user_id=u.user_id
            ORDER BY u.last_seen DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        ).fetchall()
        return [dict(row) for row in rows]


def get_user_counts() -> dict[str, int]:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM access WHERE status='approved'"
        ).fetchone()[0]
        blocked = conn.execute(
            "SELECT COUNT(*) FROM access WHERE status='blocked'"
        ).fetchone()[0]
        return {"total": total, "approved": approved, "blocked": blocked}
