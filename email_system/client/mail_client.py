"""
HTTP client for the BitriX Mail API (email_system/api/email_api.py).

`pop_unread_as_context` is meant to be called by the orchestrator loop
(main.py) BEFORE an agent's turn, not by the LLM as a tool — that's the
whole point: receiving mail is a flow-level concern, not something the
model opts into.
"""

import os

import requests

_BASE_URL = os.getenv("EMAIL_API_URL", "http://127.0.0.1:8000")
_TIMEOUT = 5


def _raise_for_status(resp: requests.Response) -> None:
    """Raise a descriptive exception when the API returns a non-2xx status.

    Extracts the `detail` field from the JSON body when available so callers
    see the API's validation message rather than a raw HTTP error string.

    Args:
        resp: Response object from any requests call.

    Raises:
        requests.HTTPError: With the API detail message embedded.
    """
    if resp.ok:
        return
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    raise requests.HTTPError(
        f"HTTP {resp.status_code} from Mail API: {detail}",
        response=resp,
    )


def send_email(from_addr: str, to_addr: str, subject: str, body: str) -> str:
    """POST a new email to the API and return the assigned email ID.

    Args:
        from_addr: Sender's BitriX address.
        to_addr:   Recipient's BitriX address.
        subject:   Subject line.
        body:      Email body text.

    Returns:
        UUID string of the stored email.

    Raises:
        requests.HTTPError: If the API rejects the request (e.g. 400 bad address).
    """
    resp = requests.post(
        f"{_BASE_URL}/emails",
        json={"from_addr": from_addr, "to_addr": to_addr, "subject": subject, "body": body},
        timeout=_TIMEOUT,
    )
    _raise_for_status(resp)
    return resp.json()["id"]


def fetch_unread(address: str) -> list[dict]:
    """Fetch the oldest unread email for *address* (0 or 1 items).

    Args:
        address: Recipient BitriX address.

    Returns:
        List with at most one email dict.

    Raises:
        requests.HTTPError: On API error.
    """
    resp = requests.get(f"{_BASE_URL}/emails/{address}/unread", timeout=_TIMEOUT)
    _raise_for_status(resp)
    return resp.json()


def fetch_inbox(address: str, limit: int = 20) -> list[dict]:
    """Fetch up to *limit* emails for *address*, newest first.

    Args:
        address: Recipient BitriX address.
        limit:   Max emails to return (1–50, API enforces ceiling).

    Returns:
        List of email dicts.

    Raises:
        requests.HTTPError: On API error.
    """
    resp = requests.get(
        f"{_BASE_URL}/emails/{address}",
        params={"limit": limit},
        timeout=_TIMEOUT,
    )
    _raise_for_status(resp)
    return resp.json()


def count_unread(address: str) -> int:
    """Return the number of unread emails for *address*.

    Args:
        address: Recipient BitriX address.

    Returns:
        Integer unread count.

    Raises:
        requests.HTTPError: On API error.
    """
    resp = requests.get(f"{_BASE_URL}/emails/{address}/unread/count", timeout=_TIMEOUT)
    _raise_for_status(resp)
    return resp.json()["count"]


def mark_read(email_id: str) -> None:
    """Mark one email as read.

    Args:
        email_id: UUID of the email to mark.

    Raises:
        requests.HTTPError: 404 if the email does not exist, or other API error.
    """
    resp = requests.post(f"{_BASE_URL}/emails/{email_id}/read", timeout=_TIMEOUT)
    _raise_for_status(resp)


def pop_unread_as_context(address: str) -> str | None:
    """Fetch the next unread email for *address*, mark it read, and format it.

    Intended for the orchestrator loop — called BEFORE an agent's turn to
    inject incoming mail as context. Not a tool the LLM calls directly.

    Args:
        address: The agent's BitriX address.

    Returns:
        A formatted string ready to prepend to the agent's prompt, or None
        if there is no unread mail.

    Raises:
        requests.HTTPError: On API error.
    """
    emails = fetch_unread(address)
    if not emails:
        return None

    for email in emails:
        mark_read(email["id"])

    lines = [f"You have {len(emails)} new email{'s' if len(emails) != 1 else ''} in your inbox:\n"]
    for i, email in enumerate(emails, start=1):
        lines.append(
            f"--- Email {i} ---\n"
            f"From:    {email['from_addr']}\n"
            f"Subject: {email['subject']}\n"
            f"Sent:    {email['sent_at']}\n"
            f"\n{email['body']}"
        )
    return "\n\n".join(lines)
