"""
Integration tests for the email_system package.

Requires the API to be running:
    uvicorn email_system.api.email_api:app --port 8000

Run all tests:
    python -m pytest test_email_system.py -v
"""

import pytest
import requests

from email_system.client import mail_client
from email_system.store import email_store
from email_system.tools.send_email import SendEmail
from email_system.tools.check_inbox import CheckInbox

CEO = "ceo@happytuna.bitrix"
COO = "coo@happytuna.bitrix"

SEND = SendEmail()
CHECK = CheckInbox()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_inbox():
    """Mark all CEO and COO emails read before and after each test."""
    email_store.mark_all_read(CEO)
    email_store.mark_all_read(COO)
    yield
    email_store.mark_all_read(CEO)
    email_store.mark_all_read(COO)


# ---------------------------------------------------------------------------
# Part 3.1 — Happy path
# ---------------------------------------------------------------------------

def test_send_increments_unread_count():
    result = SEND.run(from_addr=COO, to_addr=CEO, subject="Q3 report",
                      body="Please review the attached Q3 financials.")
    assert result.ok, result.error

    count = mail_client.count_unread(CEO)
    assert count == 1, f"Expected 1 unread, got {count}"


def test_check_inbox_marks_email_read():
    SEND.run(from_addr=COO, to_addr=CEO, subject="Action required",
             body="Please approve the new budget proposal.")
    assert mail_client.count_unread(CEO) == 1

    result = CHECK.run(address=CEO, unread_only=True)
    assert result.ok, result.error
    assert "Action required" in result.value

    assert mail_client.count_unread(CEO) == 0, "Unread count should be 0 after reading"


def test_send_two_emails_read_one_at_a_time():
    SEND.run(from_addr=COO, to_addr=CEO, subject="First", body="First body.")
    SEND.run(from_addr=COO, to_addr=CEO, subject="Second", body="Second body.")
    assert mail_client.count_unread(CEO) == 2

    r1 = CHECK.run(address=CEO, unread_only=True)
    assert r1.ok and "First" in r1.value
    assert mail_client.count_unread(CEO) == 1

    r2 = CHECK.run(address=CEO, unread_only=True)
    assert r2.ok and "Second" in r2.value
    assert mail_client.count_unread(CEO) == 0


# ---------------------------------------------------------------------------
# Part 3.2 — Validation failures (nothing stored on failure)
# ---------------------------------------------------------------------------

def test_send_fails_empty_subject():
    result = SEND.run(from_addr=COO, to_addr=CEO, subject="", body="Some body.")
    assert not result.ok
    assert "subject" in result.error.lower()
    assert mail_client.count_unread(CEO) == 0


def test_send_fails_empty_body():
    result = SEND.run(from_addr=COO, to_addr=CEO, subject="Test", body="")
    assert not result.ok
    assert "body" in result.error.lower()


def test_send_fails_unknown_address():
    result = SEND.run(from_addr=COO, to_addr="unknown@evil.corp",
                      subject="Hack", body="Body.")
    assert not result.ok
    assert "unknown" in result.error.lower() or "400" in result.error


def test_send_fails_oversized_body():
    oversized = "x" * 5001
    result = SEND.run(from_addr=COO, to_addr=CEO, subject="Big", body=oversized)
    assert not result.ok
    assert "5000" in result.error or "body" in result.error.lower()


def test_send_fails_oversized_subject():
    oversized_subj = "s" * 201
    result = SEND.run(from_addr=COO, to_addr=CEO, subject=oversized_subj, body="Body.")
    assert not result.ok
    assert "200" in result.error or "subject" in result.error.lower()


# ---------------------------------------------------------------------------
# Part 3.3 — Limit param
# ---------------------------------------------------------------------------

def test_inbox_limit_param():
    for i in range(5):
        SEND.run(from_addr=COO, to_addr=CEO, subject=f"msg {i}", body="body")

    email_store.mark_all_read(CEO)

    full = mail_client.fetch_inbox(CEO, limit=50)
    limited = mail_client.fetch_inbox(CEO, limit=2)

    assert len(limited) == 2
    assert len(full) >= 5


# ---------------------------------------------------------------------------
# Part 3.4 — 404 on nonexistent email mark_read
# ---------------------------------------------------------------------------

def test_mark_read_nonexistent_id_returns_404():
    fake_id = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(requests.HTTPError) as exc_info:
        mail_client.mark_read(fake_id)
    assert "404" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Part 3.5 — Health endpoint includes emails_stored
# ---------------------------------------------------------------------------

def test_health_returns_emails_stored():
    resp = requests.get("http://127.0.0.1:8000/health", timeout=5)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body.get("emails_stored"), int)
