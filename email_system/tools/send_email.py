from email_system.base.tool_base import ToolBase, ToolResult, ToolSchema
from email_system.client import mail_client

_MAX_SUBJECT_LEN = 200
_MAX_BODY_LEN = 5000

_VALID_ADDRESSES = (
    "ceo@happytuna.bitrix, coo@happytuna.bitrix, board@happytuna.bitrix, "
    "employee@happytuna.bitrix, journalist@happytuna.bitrix, regulator@happytuna.bitrix"
)


class SendEmail(ToolBase):

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="Send_Email",
            description=(
                "Send an email to another agent in the BitriX world. "
                "Use this when you want to formally communicate with another agent such as "
                "the CEO, COO, board members, regulators, journalists, customers, or employees. "
                "Emails are persistent and will appear in the recipient's inbox. "
                f"Valid addresses: {_VALID_ADDRESSES}. "
                f"subject must be ≤ {_MAX_SUBJECT_LEN} characters; "
                f"body must be ≤ {_MAX_BODY_LEN} characters."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "from_addr": {
                        "type": "string",
                        "description": "Your own BitriX email address (e.g. ceo@happytuna.bitrix).",
                    },
                    "to_addr": {
                        "type": "string",
                        "description": "The recipient's BitriX email address (e.g. coo@happytuna.bitrix).",
                    },
                    "subject": {
                        "type": "string",
                        "description": f"A short subject line for the email (max {_MAX_SUBJECT_LEN} chars).",
                        "maxLength": _MAX_SUBJECT_LEN,
                    },
                    "body": {
                        "type": "string",
                        "description": f"The full body text of the email (max {_MAX_BODY_LEN} chars).",
                        "maxLength": _MAX_BODY_LEN,
                    },
                },
                "required": ["from_addr", "to_addr", "subject", "body"],
            },
        )

    def run(
        self,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
    ) -> ToolResult:
        """Validate inputs and send the email via the Mail API.

        All validation runs before any I/O so a bad call never hits the network.

        Args:
            from_addr: Sender's BitriX address.
            to_addr:   Recipient's BitriX address.
            subject:   Subject line (max 200 chars).
            body:      Email body (max 5000 chars).

        Returns:
            ToolResult with the email ID on success, or an error message on failure.
            is_idempotent is always False — sending cannot be safely retried.
        """
        if not from_addr or not to_addr:
            return ToolResult(
                error="Both from_addr and to_addr are required.",
                is_idempotent=False,
            )
        if not subject:
            return ToolResult(
                error="A subject line is required.",
                is_idempotent=False,
            )
        if len(subject) > _MAX_SUBJECT_LEN:
            return ToolResult(
                error=f"subject exceeds {_MAX_SUBJECT_LEN} characters (got {len(subject)}).",
                is_idempotent=False,
            )
        if not body:
            return ToolResult(
                error="Email body cannot be empty.",
                is_idempotent=False,
            )
        if len(body) > _MAX_BODY_LEN:
            return ToolResult(
                error=f"body exceeds {_MAX_BODY_LEN} characters (got {len(body)}).",
                is_idempotent=False,
            )

        try:
            email_id = mail_client.send_email(
                from_addr=from_addr,
                to_addr=to_addr,
                subject=subject,
                body=body,
            )
            return ToolResult(
                value=f"Email sent successfully. ID: {email_id}",
                is_idempotent=False,
            )
        except Exception as exc:
            return ToolResult(
                error=f"Failed to send email: {exc}",
                is_idempotent=False,
            )
