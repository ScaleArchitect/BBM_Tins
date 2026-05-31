"""SMTP email provider (Sprint 0 stub).

Implemented in Sprint 3 against Mailpit locally. Cloud providers (ACS/SendGrid)
swap in via configuration without touching domain code.
"""

from __future__ import annotations

from app.providers.email.base import EmailMessage, EmailSendResult


class SmtpEmailProvider:
    def __init__(self, host: str, port: int, default_from: str) -> None:
        self.host = host
        self.port = port
        self.default_from = default_from

    async def send(self, msg: EmailMessage) -> EmailSendResult:
        raise NotImplementedError("SmtpEmailProvider — implemented in Sprint 3.")
