"""Azure Communication Services email provider (Sprint 0 stub). Implemented Sprint 12."""

from __future__ import annotations

from app.providers.email.base import EmailMessage, EmailSendResult


class AcsEmailProvider:
    def __init__(self, connection_string: str = "") -> None:
        self.connection_string = connection_string

    async def send(self, msg: EmailMessage) -> EmailSendResult:
        raise NotImplementedError("AcsEmailProvider — implemented in Sprint 12.")
