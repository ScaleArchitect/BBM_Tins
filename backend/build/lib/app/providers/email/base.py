"""EmailProvider interface + message models (docs/architecture/01 §7.7, IA-09).

All sends go through the notification service (templating + audit + retry);
domain code never calls a provider directly.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class EmailMessage(BaseModel):
    to: str
    subject: str
    body_html: str
    body_text: str | None = None
    from_addr: str | None = None


class EmailSendResult(BaseModel):
    provider_message_id: str | None = None
    accepted: bool = True


class EmailProvider(Protocol):
    async def send(self, msg: EmailMessage) -> EmailSendResult: ...
