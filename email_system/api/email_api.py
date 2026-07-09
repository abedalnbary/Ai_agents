"""
BitriX Mail API — the real transport for inter-agent email.

Agents no longer share the SQLite file directly: they talk to this HTTP
service. Sending an email is a client-initiated POST (fine to leave as an
LLM tool call — the agent decides when to send). Receiving is different on
purpose: nothing here waits for an agent to "choose" to check its mail.
The orchestrator loop polls GET /emails/{address}/unread on every turn and
force-injects whatever comes back, so a message from another agent is seen
even if the model never calls a tool for it.

Run standalone:
    uvicorn email_system.api.email_api:app --port 8000
main.py also auto-launches this as a subprocess if it isn't already up.
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from email_system.store import email_store

app = FastAPI(title="BitriX Mail API")

VALID_ADDRESSES: frozenset[str] = frozenset({
    "ceo@happytuna.bitrix",
    "coo@happytuna.bitrix",
    "board@happytuna.bitrix",
    "employee@happytuna.bitrix",
    "journalist@happytuna.bitrix",
    "regulator@happytuna.bitrix",
})

_MAX_SUBJECT_LEN = 200
_MAX_BODY_LEN = 5000


class EmailIn(BaseModel):
    from_addr: str = Field(..., description="Sender's BitriX email address")
    to_addr: str = Field(..., description="Recipient's BitriX email address")
    subject: str = Field(..., description="Subject line, max 200 chars")
    body: str = Field(..., description="Email body, max 5000 chars")


class EmailOut(BaseModel):
    id: str
    from_addr: str
    to_addr: str
    subject: str
    body: str
    sent_at: str
    is_read: int


def notify_agent(to_addr: str) -> None:
    # TODO: wake the receiving agent (e.g. ceo.chat("New email..."))
    # Wired later when agent runtime design is decided.
    pass


def _validate_address(field: str, value: str) -> None:
    """Raise HTTP 400 if *value* is not a known BitriX agent address.

    Args:
        field: Parameter name used in the error message (e.g. "from_addr").
        value: Address string to validate.

    Raises:
        HTTPException: 400 with a message listing all valid addresses.
    """
    if value not in VALID_ADDRESSES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown {field} '{value}'. "
                f"Valid addresses: {sorted(VALID_ADDRESSES)}"
            ),
        )


@app.get("/health")
def health() -> dict:
    """Return API liveness status and total email count.

    Returns:
        JSON: {"status": "ok", "emails_stored": <int>}
    """
    return {"status": "ok", "emails_stored": email_store.count_all()}


@app.post("/emails", status_code=201)
def create_email(email: EmailIn) -> dict:
    """Store a new email and notify the recipient agent.

    Validates both addresses against the known agent list and enforces
    subject / body length limits before writing to the store.

    Args:
        email: Parsed request body (from_addr, to_addr, subject, body).

    Returns:
        JSON: {"id": "<uuid>"}

    Raises:
        HTTPException 400: Unknown address or content too long.
    """
    _validate_address("from_addr", email.from_addr)
    _validate_address("to_addr", email.to_addr)

    if not email.subject:
        raise HTTPException(status_code=400, detail="subject must not be empty.")
    if len(email.subject) > _MAX_SUBJECT_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"subject exceeds {_MAX_SUBJECT_LEN} characters (got {len(email.subject)}).",
        )
    if not email.body:
        raise HTTPException(status_code=400, detail="body must not be empty.")
    if len(email.body) > _MAX_BODY_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"body exceeds {_MAX_BODY_LEN} characters (got {len(email.body)}).",
        )

    email_id = email_store.send(
        from_addr=email.from_addr,
        to_addr=email.to_addr,
        subject=email.subject,
        body=email.body,
    )
    notify_agent(email.to_addr)
    return {"id": email_id}


@app.get("/emails/{address}/unread", response_model=list[EmailOut])
def unread_emails(address: str) -> list[dict]:
    """Return the oldest unread email for *address* (at most 1).

    The orchestrator calls this on every agent turn to inject incoming mail.
    Returns an empty list if there is no unread mail.

    Args:
        address: Recipient BitriX address to query.

    Returns:
        JSON array with 0 or 1 EmailOut objects.
    """
    return email_store.get_unread(address)


@app.get("/emails/{address}/unread/count")
def unread_count(address: str) -> dict:
    """Return the total number of unread emails for *address*.

    Args:
        address: Recipient BitriX address to query.

    Returns:
        JSON: {"count": <int>}
    """
    return {"count": email_store.count_unread(address)}


@app.get("/emails/{address}", response_model=list[EmailOut])
def inbox(
    address: str,
    limit: int = Query(default=20, ge=1, le=50, description="Max emails to return (1–50)."),
) -> list[dict]:
    """Return up to *limit* emails for *address*, newest first.

    Args:
        address: Recipient BitriX address.
        limit:   Max results (default 20, max 50).

    Returns:
        JSON array of EmailOut objects ordered newest-first.
    """
    return email_store.get_inbox(address, limit=limit)


@app.post("/emails/{email_id}/read")
def read_email(email_id: str) -> dict:
    """Mark one email as read.

    Args:
        email_id: UUID of the email to mark read.

    Returns:
        JSON: {"status": "ok"}

    Raises:
        HTTPException 404: No email with that ID exists.
    """
    found = email_store.mark_read(email_id)
    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"Email '{email_id}' not found.",
        )
    return {"status": "ok"}
