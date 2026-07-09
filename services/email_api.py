# Backward-compat shim — real implementation moved to email_system/api/email_api.py
from email_system.api.email_api import app  # noqa: F401

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
    uvicorn services.email_api:app --port 8000
main.py also auto-launches this as a subprocess if it isn't already up.
"""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from services import email_store

app = FastAPI(title="BitriX Mail API")


class EmailIn(BaseModel):
    from_addr: str = Field(..., description="Sender's BitriX email address")
    to_addr: str = Field(..., description="Recipient's BitriX email address")
    subject: str
    body: str


class EmailOut(BaseModel):
    id: str
    from_addr: str
    to_addr: str
    subject: str
    body: str
    sent_at: str
    is_read: int


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/emails", status_code=201)
def create_email(email: EmailIn) -> dict:
    email_id = email_store.send(
        from_addr=email.from_addr,
        to_addr=email.to_addr,
        subject=email.subject,
        body=email.body,
    )
    return {"id": email_id}


@app.get("/emails/{address}/unread", response_model=list[EmailOut])
def unread_emails(address: str) -> list[dict]:
    return email_store.get_unread(address)


@app.get("/emails/{address}/unread/count")
def unread_count(address: str) -> dict:
    return {"count": email_store.count_unread(address)}


@app.get("/emails/{address}", response_model=list[EmailOut])
def inbox(address: str) -> list[dict]:
    return email_store.get_inbox(address)


@app.post("/emails/{email_id}/read")
def read_email(email_id: str) -> dict:
    email_store.mark_read(email_id)
    return {"status": "ok"}
