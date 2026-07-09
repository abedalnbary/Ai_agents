# BitriX Email System

Shared email infrastructure for the HappyTuna BitriX world simulation. All
six agent types (CEO, COO, Board, Employee, Journalist, Regulator) send and
receive messages through this service over HTTP — no agent ever touches the
database directly. The design follows a strict layer rule:

```
tools → mail_client → HTTP → email_api → email_store → SQLite
```

---

## How to run

### Local

```bash
pip install -r email_system/requirements.txt
uvicorn email_system.api.email_api:app --port 8000 --reload
```

### Docker

```bash
docker compose up email-service
```

Or build and run manually (from the monorepo root):

```bash
docker build -f email_system/Dockerfile -t email-service email_system/
docker run -p 8000:8000 email-service
```

### Verify it's up

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "ok", "emails_stored": 0}
```

### Environment variables

| Variable        | Default                  | Purpose                                      |
|-----------------|--------------------------|----------------------------------------------|
| `EMAIL_API_URL` | `http://127.0.0.1:8000`  | Base URL agents and mail_client connect to.  |
| `EMAIL_DB_PATH` | `email_system/data/email.db` | Override SQLite file path (useful in Docker). |

---

## Features

- **Send email** — POST to the API; the store generates a UUID and records
  the message with a UTC timestamp.
- **Inbox** — fetch up to 50 emails for an address, newest first. Default
  page size is 20 (protects agent context windows from flooded inboxes).
- **Unread queue** — returns **one email at a time, oldest first** (LIMIT 1).
  Call repeatedly to drain the queue. Intentional — lets the orchestrator
  inject mail one message per turn without overwhelming the model.
- **Mark read** — POST to mark a single email read. Returns 404 if the ID
  does not exist.
- **Unread count** — lightweight count query, used by the orchestrator to
  decide whether to poll for new mail.
- **Address validation** — unknown `from_addr` or `to_addr` rejected with
  HTTP 400 listing all valid addresses.
- **Size limits** — subject ≤ 200 chars, body ≤ 5000 chars; enforced at the
  API layer and mirrored in tool schema descriptions so the LLM knows.
- **Agent-waking trigger stub** — `notify_agent(to_addr)` is called after
  every successful send. Currently a no-op; wired later when the agent
  runtime design is finalised.

---

## API reference

### GET /health

Returns liveness status and total email count. Use this as a Docker
healthcheck probe.

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok", "emails_stored": 42}
```

---

### POST /emails

Store a new email. Both addresses must be in the valid agent list.

```bash
curl -X POST http://localhost:8000/emails \
  -H "Content-Type: application/json" \
  -d '{
    "from_addr": "coo@happytuna.bitrix",
    "to_addr":   "ceo@happytuna.bitrix",
    "subject":   "Line 4 halted",
    "body":      "QA flagged batch HT-2026-0089. Awaiting your decision."
  }'
```

**201 Created**

```json
{"id": "550e8400-e29b-41d4-a716-446655440000"}
```

**400 Bad Request — unknown address**

```json
{"detail": "Unknown to_addr 'x@y.z'. Valid addresses: ['board@happytuna.bitrix', ...]"}
```

**400 Bad Request — body too long**

```json
{"detail": "body exceeds 5000 characters (got 5001)."}
```

---

### GET /emails/{address}

Return up to `limit` emails for `address`, newest first.

| Query param | Type | Default | Max | Description          |
|-------------|------|---------|-----|----------------------|
| `limit`     | int  | 20      | 50  | Max emails returned. |

```bash
curl "http://localhost:8000/emails/ceo@happytuna.bitrix?limit=5"
```

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "from_addr": "coo@happytuna.bitrix",
    "to_addr":   "ceo@happytuna.bitrix",
    "subject":   "Line 4 halted",
    "body":      "QA flagged batch HT-2026-0089.",
    "sent_at":   "2026-07-07T10:00:00",
    "is_read":   0
  }
]
```

---

### GET /emails/{address}/unread

Return the **oldest unread** email for `address` — at most 1 item. The
orchestrator calls this before each agent turn.

```bash
curl "http://localhost:8000/emails/ceo@happytuna.bitrix/unread"
```

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "from_addr": "coo@happytuna.bitrix",
    "to_addr":   "ceo@happytuna.bitrix",
    "subject":   "Line 4 halted",
    "body":      "QA flagged batch HT-2026-0089.",
    "sent_at":   "2026-07-07T10:00:00",
    "is_read":   0
  }
]
```

Empty list `[]` means no unread mail.

---

### GET /emails/{address}/unread/count

Return the total unread count for `address`.

```bash
curl "http://localhost:8000/emails/ceo@happytuna.bitrix/unread/count"
```

```json
{"count": 3}
```

---

### POST /emails/{email_id}/read

Mark one email as read.

```bash
curl -X POST \
  "http://localhost:8000/emails/550e8400-e29b-41d4-a716-446655440000/read"
```

**200 OK**

```json
{"status": "ok"}
```

**404 Not Found**

```json
{"detail": "Email '550e8400-...' not found."}
```

---

## Data model

SQLite table `emails` in `email_system/data/email.db`.

| Column      | Type    | Meaning                                        |
|-------------|---------|------------------------------------------------|
| `id`        | TEXT PK | UUID v4 assigned at insert time.               |
| `from_addr` | TEXT    | Sender's BitriX address.                       |
| `to_addr`   | TEXT    | Recipient's BitriX address.                    |
| `subject`   | TEXT    | Subject line (max 200 chars).                  |
| `body`      | TEXT    | Email body (max 5000 chars).                   |
| `sent_at`   | TEXT    | UTC timestamp, format `YYYY-MM-DDTHH:MM:SS`.   |
| `is_read`   | INTEGER | 0 = unread, 1 = read.                          |

Example row:

```json
{
  "id":        "550e8400-e29b-41d4-a716-446655440000",
  "from_addr": "coo@happytuna.bitrix",
  "to_addr":   "ceo@happytuna.bitrix",
  "subject":   "Line 4 halted",
  "body":      "QA flagged batch HT-2026-0089. Awaiting your decision.",
  "sent_at":   "2026-07-07T10:00:00",
  "is_read":   0
}
```

---

## Agent integration

```python
from email_system import SendEmail, CheckInbox, mail_client

# executor is whatever ToolExecutor your project provides
executor.register(SendEmail())
executor.register(CheckInbox())
```

The tools read `EMAIL_API_URL` from the environment — set it to reach the
API across containers:

```bash
EMAIL_API_URL=http://email-service:8000
```

**Orchestrator: inject incoming mail before each agent turn**

```python
context = mail_client.pop_unread_as_context("ceo@happytuna.bitrix")
if context:
    prompt = context + "\n\n" + user_prompt
```

---

## Agent addresses

| Agent      | Address                       |
|------------|-------------------------------|
| CEO        | `ceo@happytuna.bitrix`        |
| COO        | `coo@happytuna.bitrix`        |
| Board      | `board@happytuna.bitrix`      |
| Employee   | `employee@happytuna.bitrix`   |
| Journalist | `journalist@happytuna.bitrix` |
| Regulator  | `regulator@happytuna.bitrix`  |

---

## Isolation guarantee

Zero outward imports — verify at any time:

```bash
grep -rn --include="*.py" "^from base\.\|^import base\.\|^from services\.\|^from agents\." email_system/
# expected: no output
```
