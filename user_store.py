"""SQLite-backed Telegram user registry and access-control helpers."""
from __future__ import annotations

import os
from contextlib import closing
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
    with closing(_connect()) as conn, conn:
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
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT NOT NULL,
                provider TEXT,
                filename TEXT,
                size_bytes INTEGER,
                success INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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


def list_users(limit: int = 30, offset: int = 0) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT u.user_id, u.username, u.first_name, u.last_seen,
                   u.message_count, a.status
            FROM users u
            LEFT JOIN access a ON a.user_id=u.user_id
            ORDER BY u.last_seen DESC
            LIMIT ? OFFSET ?
            """,
            (max(1, min(limit, 100)), max(0, offset)),
        ).fetchall()
        return [dict(row) for row in rows]


def get_user(user_id: int) -> dict[str, Any] | None:
    with closing(_connect()) as conn, conn:
        row = conn.execute(
            """
            SELECT u.user_id, u.username, u.first_name, u.first_seen,
                   u.last_seen, u.message_count, a.status, a.updated_at
            FROM users u
            LEFT JOIN access a ON a.user_id=u.user_id
            WHERE u.user_id=?
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def record_event(
    user_id: int | None,
    event_type: str,
    provider: str | None = None,
    filename: str | None = None,
    size_bytes: int | None = None,
    success: bool = True,
) -> None:
    """Store operational events without source URLs or credentials."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            """
            INSERT INTO usage_events(
                user_id, event_type, provider, filename, size_bytes, success
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, event_type[:40], (provider or "")[:80],
             (filename or "")[:255], max(0, size_bytes or 0), int(success)),
        )


def get_analytics(days: int = 30) -> dict[str, Any]:
    days = max(1, min(days, 365))
    with closing(_connect()) as conn, conn:
        totals = conn.execute(
            """
            SELECT COUNT(*) AS events,
                SUM(CASE WHEN event_type='resolve_success' THEN 1 ELSE 0 END) AS resolved,
                SUM(CASE WHEN event_type='resolve_failed' THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN event_type='download_success' THEN 1 ELSE 0 END) AS downloads,
                SUM(CASE WHEN event_type='download_failed' THEN 1 ELSE 0 END) AS download_failures,
                SUM(CASE WHEN event_type='drip_upload_success' THEN 1 ELSE 0 END) AS drip_uploads,
                COUNT(DISTINCT user_id) AS active_users,
                COALESCE(SUM(CASE WHEN event_type IN ('download_success','drip_upload_success')
                                  THEN size_bytes ELSE 0 END), 0) AS bytes_transferred
            FROM usage_events WHERE created_at >= datetime('now', ?)
            """,
            (f"-{days} days",),
        ).fetchone()
        providers = conn.execute(
            """
            SELECT provider, COUNT(*) AS uses FROM usage_events
            WHERE event_type='resolve_success' AND provider IS NOT NULL
              AND provider != '' AND created_at >= datetime('now', ?)
            GROUP BY provider ORDER BY uses DESC LIMIT 8
            """,
            (f"-{days} days",),
        ).fetchall()
        active = conn.execute(
            """
            SELECT e.user_id, COALESCE(u.first_name, '') AS first_name,
                   COALESCE(u.username, '') AS username, COUNT(*) AS operations
            FROM usage_events e LEFT JOIN users u ON u.user_id=e.user_id
            WHERE e.user_id IS NOT NULL AND e.created_at >= datetime('now', ?)
            GROUP BY e.user_id ORDER BY operations DESC LIMIT 8
            """,
            (f"-{days} days",),
        ).fetchall()
        recent = conn.execute(
            """
            SELECT event_type, provider, filename, size_bytes, success, created_at
            FROM usage_events
            WHERE created_at >= datetime('now', ?)
            ORDER BY id DESC LIMIT 10
            """,
            (f"-{days} days",),
        ).fetchall()
        return {
            "totals": dict(totals),
            "providers": [dict(row) for row in providers],
            "active_users": [dict(row) for row in active],
            "recent": [dict(row) for row in recent],
            "days": days,
        }


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
