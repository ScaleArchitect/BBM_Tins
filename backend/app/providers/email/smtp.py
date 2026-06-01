"""SMTP email provider (local Mailpit; swappable for ACS/SendGrid via config).

Sends a multipart/alternative (text + HTML) message. Uses the stdlib ``smtplib``
on a worker thread so the event loop is never blocked. Mailpit (compose service
``mail``) accepts unauthenticated plaintext SMTP on port 1025 and captures every
message for inspection at http://localhost:8025.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage as MimeMessage

from app.providers.email.base import EmailMessage, EmailSendResult


class SmtpEmailProvider:
    def __init__(self, host: str, port: int, default_from: str) -> None:
        self.host = host
        self.port = port
        self.default_from = default_from

    def _build(self, msg: EmailMessage) -> MimeMessage:
        mime = MimeMessage()
        mime["From"] = msg.from_addr or self.default_from
        mime["To"] = msg.to
        mime["Subject"] = msg.subject
        mime.set_content(msg.body_text or "")
        mime.add_alternative(msg.body_html, subtype="html")
        return mime

    def _send_sync(self, mime: MimeMessage) -> None:
        with smtplib.SMTP(self.host, self.port, timeout=10) as client:
            client.send_message(mime)

    async def send(self, msg: EmailMessage) -> EmailSendResult:
        mime = self._build(msg)
        await asyncio.to_thread(self._send_sync, mime)
        return EmailSendResult(provider_message_id=mime.get("Message-ID"), accepted=True)
