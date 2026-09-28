"""
SQLite persistence for users, Gmail OAuth tokens, and sent-email history.

A single file (app.db) at the project root. Tables are created on import via
init_db(), called from api.py at startup.
"""

import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "app.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS gmail_tokens (
    user_id        TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    email          TEXT,
    access_token   TEXT,
    refresh_token  TEXT,
    token_expires  REAL,
    scope          TEXT,
    connected_at   REAL
);

CREATE TABLE IF NOT EXISTS email_history (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    report_name TEXT,
    recipient   TEXT NOT NULL,
    subject     TEXT NOT NULL,
    status      TEXT NOT NULL,
    message_id  TEXT,
    error       TEXT,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS email_drafts (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipient      TEXT NOT NULL,
    subject        TEXT NOT NULL,
    body           TEXT NOT NULL,
    report_name    TEXT,
    gmail_draft_id TEXT,
    status         TEXT NOT NULL DEFAULT 'draft',
    created_at     REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_history_user
    ON email_history(user_id, created_at DESC);
"""

_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    """Return the shared SQLite connection (created lazily)."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


def init_db() -> None:
    """Explicitly create tables (idempotent)."""
    get_conn()


@contextmanager
def db():
    """Yield a connection with commit/rollback handling."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def create_user(email: str, password_hash: str) -> sqlite3.Row:
    """Insert a new user; raises sqlite3.IntegrityError on duplicate email."""
    user_id = uuid.uuid4().hex
    with db() as conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, email.lower().strip(), password_hash, time.time()),
        )
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_email(email: str) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()


def get_user_by_id(user_id: str) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


# ---------------------------------------------------------------------------
# Gmail tokens
# ---------------------------------------------------------------------------

def upsert_gmail_token(user_id: str, **fields) -> None:
    """Create or update the stored Gmail OAuth token row for a user."""
    allowed = ("email", "access_token", "refresh_token", "token_expires", "scope", "connected_at")
    cols, vals = [], []
    for key in allowed:
        if key in fields and fields[key] is not None:
            cols.append(key)
            vals.append(fields[key])
    if not cols:
        return
    with db() as conn:
        conn.execute(
            f"""
            INSERT INTO gmail_tokens (user_id, {', '.join(cols)})
            VALUES (?, {', '.join('?' for _ in cols)})
            ON CONFLICT(user_id) DO UPDATE SET
                {', '.join(f'{c} = excluded.{c}' for c in cols)}
            """,
            (user_id, *vals),
        )


def get_gmail_token(user_id: str) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM gmail_tokens WHERE user_id = ?", (user_id,)
        ).fetchone()


def delete_gmail_token(user_id: str) -> None:
    with db() as conn:
        conn.execute("DELETE FROM gmail_tokens WHERE user_id = ?", (user_id,))


# ---------------------------------------------------------------------------
# Email history
# ---------------------------------------------------------------------------

def record_email(user_id: str, recipient: str, subject: str, status: str,
                 report_name: str | None = None, message_id: str | None = None,
                 error: str | None = None) -> sqlite3.Row:
    """Append one entry to the sent-email history."""
    row_id = uuid.uuid4().hex
    with db() as conn:
        conn.execute(
            """
            INSERT INTO email_history
                (id, user_id, report_name, recipient, subject, status, message_id, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (row_id, user_id, report_name, recipient, subject, status,
             message_id, error, time.time()),
        )
        return conn.execute("SELECT * FROM email_history WHERE id = ?", (row_id,)).fetchone()


def list_emails(user_id: str, limit: int = 50) -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            """
            SELECT * FROM email_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()


# ---------------------------------------------------------------------------
# Email drafts (used by the Email MCP server tools)
# ---------------------------------------------------------------------------

def create_email_draft(user_id: str, recipient: str, subject: str, body: str,
                       report_name: str | None = None,
                       gmail_draft_id: str | None = None) -> str:
    """Persist a draft; returns its local draft id."""
    draft_id = uuid.uuid4().hex
    with db() as conn:
        conn.execute(
            """
            INSERT INTO email_drafts
                (id, user_id, recipient, subject, body, report_name, gmail_draft_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?)
            """,
            (draft_id, user_id, recipient, subject, body, report_name, gmail_draft_id, time.time()),
        )
    return draft_id


def get_email_draft(draft_id: str) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM email_drafts WHERE id = ?", (draft_id,)
        ).fetchone()


def list_email_drafts(user_id: str, limit: int = 20) -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM email_drafts WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def mark_draft_sent(draft_id: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE email_drafts SET status = 'sent' WHERE id = ?", (draft_id,)
        )
