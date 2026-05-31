"""SendGrid email provider (Sprint 0 stub). Implemented Sprint 12 (alt to ACS)."""

from __future__ import annotations

from app.providers.email.base import EmailMessage, EmailSendResult


class SendgridEmailProvider:
    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    async def send(self, msg: EmailMessage) -> EmailSendResult:
        raise NotImplementedError("SendgridEmailProvider — implemented in Sprint 12.")
