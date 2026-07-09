import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(os.getenv("EMAIL_DB_PATH", str(Path(__file__).parent.parent / "data" / "email.db")))

_INBOX_DEFAULT_LIMIT = 20
_INBOX_MAX_LIMIT = 50


def _connection() -> sqlite3.Connection:
    """Open (and auto-create) the SQLite database, returning a connection."""
    _DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init() -> None:
    """Create the emails table if it does not exist."""
    with _connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id        TEXT PRIMARY KEY,
                from_addr TEXT NOT NULL,
                to_addr   TEXT NOT NULL,
                subject   TEXT NOT NULL,
                body      TEXT NOT NULL,
                sent_at   TEXT NOT NULL,
                is_read   INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


_init()


def send(from_addr: str, to_addr: str, subject: str, body: str) -> str:
    """Insert a new email row and return its generated UUID.

    Args:
        from_addr: Sender's BitriX address.
        to_addr:   Recipient's BitriX address.
        subject:   Subject line (already validated by caller).
        body:      Email body (already validated by caller).

    Returns:
        The UUID string assigned to the new email.
    """
    email_id = str(uuid.uuid4())
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    with _connection() as conn:
        conn.execute(
            "INSERT INTO emails (id, from_addr, to_addr, subject, body, sent_at, is_read) "
            "VALUES (?, ?, ?, ?, ?, ?, 0)",
            (email_id, from_addr, to_addr, subject, body, sent_at),
        )
        conn.commit()
    return email_id


def count_unread(address: str) -> int:
    """Return the number of unread emails for *address*.

    Args:
        address: Recipient BitriX address to query.

    Returns:
        Integer count of rows where is_read = 0.
    """
    with _connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM emails WHERE to_addr = ? AND is_read = 0",
            (address,),
        ).fetchone()
    return row["n"]


def count_all() -> int:
    """Return the total number of emails stored across all addresses."""
    with _connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM emails").fetchone()
    return row["n"]


def get_inbox(address: str, limit: int = _INBOX_DEFAULT_LIMIT) -> list[dict]:
    """Return up to *limit* emails for *address*, newest first.

    Ordering is deterministic: sent_at DESC, id ASC as tie-breaker.

    Args:
        address: Recipient BitriX address.
        limit:   Maximum rows to return. Clamped to [1, _INBOX_MAX_LIMIT].

    Returns:
        List of email dicts, newest first.
    """
    limit = max(1, min(limit, _INBOX_MAX_LIMIT))
    with _connection() as conn:
        rows = conn.execute(
            "SELECT * FROM emails WHERE to_addr = ? ORDER BY sent_at DESC, id ASC LIMIT ?",
            (address, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_unread(address: str) -> list[dict]:
    """Return exactly 1 unread email for *address* — the oldest one.

    Call repeatedly to process unread messages one at a time.

    Args:
        address: Recipient BitriX address.

    Returns:
        A list with at most one email dict, or an empty list if inbox is clear.
    """
    with _connection() as conn:
        rows = conn.execute(
            "SELECT * FROM emails WHERE to_addr = ? AND is_read = 0 "
            "ORDER BY sent_at ASC, id ASC LIMIT 1",
            (address,),
        ).fetchall()
    return [dict(row) for row in rows]


def mark_read(email_id: str) -> bool:
    """Mark one email as read.

    Args:
        email_id: UUID of the email to mark.

    Returns:
        True if the email existed and was updated, False if not found.
    """
    with _connection() as conn:
        cursor = conn.execute("UPDATE emails SET is_read = 1 WHERE id = ?", (email_id,))
        conn.commit()
    return cursor.rowcount > 0


def mark_all_read(address: str) -> None:
    """Mark every email addressed to *address* as read.

    Args:
        address: Recipient BitriX address whose inbox is cleared.
    """
    with _connection() as conn:
        conn.execute("UPDATE emails SET is_read = 1 WHERE to_addr = ?", (address,))
        conn.commit()
