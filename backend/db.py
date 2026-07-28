"""Tiny SQLite layer for storing research sessions.

Kept deliberately dependency-free (stdlib sqlite3) so the project has
no external database to stand up for a demo.
"""
import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "scout.db")


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                created_at TEXT NOT NULL,
                final_report TEXT,
                trace_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_session(query: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (query, created_at, trace_json) VALUES (?, ?, ?)",
            (query, datetime.now(timezone.utc).isoformat(), "[]"),
        )
        return cur.lastrowid


def append_trace_step(session_id: int, step: dict):
    with _connect() as conn:
        row = conn.execute(
            "SELECT trace_json FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        trace = json.loads(row["trace_json"]) if row else []
        trace.append(step)
        conn.execute(
            "UPDATE sessions SET trace_json = ? WHERE id = ?",
            (json.dumps(trace), session_id),
        )


def finalize_session(session_id: int, final_report: str):
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET final_report = ? WHERE id = ?",
            (final_report, session_id),
        )


def list_sessions() -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, query, created_at, final_report FROM sessions ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_session(session_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["trace"] = json.loads(data.pop("trace_json"))
        return data
