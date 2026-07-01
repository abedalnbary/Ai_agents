from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from base.tool_base import ToolBase, ToolResult, ToolSchema

_ALLOWED_FILTERS = {"all", "unread", "from_sender", "by_subject", "by_date"}
_MAX_RESULTS     = 50


class ReadEmailsTool(ToolBase):
    """Reads emails from the BitriX Mail system for the CEO agent.

    Demonstrates three agent-development concepts:

    1. Allowlist enforcement  -> _ALLOWED_FILTERS gates valid filter modes.
    2. Business-rule validation -> max_results is capped; invalid dates are
       rejected before any I/O, not mid-execution.
    3. Idempotency -> reading never mutates state; safe to retry.
    """

    def __init__(self, mail_client):
        """
        Args:
            mail_client: BitriX mail adapter that exposes .fetch(filters) -> list[dict].
                         In simulation: a mock; in production: real mail API client.
        """
        self._mail = mail_client

 

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="read_emails",
            description=(
                "Reads emails from the CEO's BitriX Mail inbox. "
                "Use this when you need to check for employee reports, "
                "board messages, regulatory notices, or any incoming "
                "communication. Always read emails before making decisions "
                "about ongoing events."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "filter_mode": {
                        "type": "string",
                        "enum": sorted(_ALLOWED_FILTERS),
                        "description": (
                            "How to filter the inbox:\n"
                            "  all          -> return recent emails (default)\n"
                            "  unread       -> only unread emails\n"
                            "  from_sender  -> emails from a specific sender "
                                             "(requires 'sender')\n"
                            "  by_subject   -> emails matching a keyword in the "
                                             "subject (requires 'subject_keyword')\n"
                            "  by_date      -> emails on or after a date "
                                             "(requires 'since_date')"
                        ),
                    },
                    "sender": {
                        "type": "string",
                        "description": (
                            "Email address or name to filter by. "
                            "Required when filter_mode is 'from_sender'."
                        ),
                    },
                    "subject_keyword": {
                        "type": "string",
                        "description": (
                            "Keyword to search for in email subjects. "
                            "Required when filter_mode is 'by_subject'."
                        ),
                    },
                    "since_date": {
                        "type": "string",
                        "description": (
                            "ISO-8601 date string (YYYY-MM-DD). "
                            "Required when filter_mode is 'by_date'. "
                            "Returns all emails on or after this date."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": (
                            f"Maximum number of emails to return (1-{_MAX_RESULTS}). "
                            "Defaults to 10."
                        ),
                        "default": 10,
                    },
                    "include_body": {
                        "type": "boolean",
                        "description": (
                            "Whether to include the full email body. "
                            "Defaults to False (returns subject + metadata only). "
                            "Set True only when you need to read the content."
                        ),
                        "default": False,
                    },
                },
                "required": ["filter_mode"],
            },
        )

    # ------------------------------------------------------------------- run

    def run(
        self,
        filter_mode:     str,
        sender:          Optional[str] = None,
        subject_keyword: Optional[str] = None,
        since_date:      Optional[str] = None,
        max_results:     int           = 10,
        include_body:    bool          = False,
    ) -> ToolResult:

    
        if filter_mode not in _ALLOWED_FILTERS:
            return ToolResult(
                error=(
                    f"Unknown filter_mode '{filter_mode}'. "
                    f"Allowed: {sorted(_ALLOWED_FILTERS)}"
                ),
                is_idempotent=True,
            )

     
        if filter_mode == "from_sender" and not sender:
            return ToolResult(
                error="filter_mode 'from_sender' requires the 'sender' parameter.",
                is_idempotent=True,
            )

        if filter_mode == "by_subject" and not subject_keyword:
            return ToolResult(
                error="filter_mode 'by_subject' requires the 'subject_keyword' parameter.",
                is_idempotent=True,
            )

        if filter_mode == "by_date":
            if not since_date:
                return ToolResult(
                    error="filter_mode 'by_date' requires the 'since_date' parameter.",
                    is_idempotent=True,
                )
            try:
                datetime.strptime(since_date, "%Y-%m-%d")
            except ValueError:
                return ToolResult(
                    error=(
                        f"Invalid since_date '{since_date}'. "
                        "Expected format: YYYY-MM-DD (e.g. 2026-06-19)."
                    ),
                    is_idempotent=True,
                )

        if not (1 <= max_results <= _MAX_RESULTS):
            return ToolResult(
                error=(
                    f"max_results must be between 1 and {_MAX_RESULTS}. "
                    f"Got: {max_results}."
                ),
                is_idempotent=True,
            )

        fetch_filters = {
            "filter_mode":     filter_mode,
            "sender":          sender,
            "subject_keyword": subject_keyword,
            "since_date":      since_date,
            "max_results":     max_results,
            "include_body":    include_body,
        }

        try:
            emails: list[dict] = self._mail.fetch(fetch_filters)
        except Exception as exc:
            return ToolResult(
                error=f"Mail system unavailable: {exc}",
                is_idempotent=True,
            )

      
        if not include_body:
            emails = [
                {k: v for k, v in email.items() if k != "body"}
                for email in emails
            ]

 
        return ToolResult(
            value={
                "total_found": len(emails),
                "filter_applied": filter_mode,
                "emails": emails,
            },
            is_idempotent=True,   # reading never mutates state
        )