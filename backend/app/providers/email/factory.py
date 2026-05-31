"""Email provider factory — selects implementation from settings (IA-09)."""

from __future__ import annotations

from app.core.config import Settings
from app.providers.email.base import EmailProvider


def build_email_provider(settings: Settings) -> EmailProvider:
    provider = settings.email_provider.lower()
    if provider == "smtp":
        from app.providers.email.smtp import SmtpEmailProvider

        return SmtpEmailProvider(
            host=settings.smtp_host, port=settings.smtp_port, default_from=settings.email_from
        )
    if provider == "acs":
        from app.providers.email.acs import AcsEmailProvider

        return AcsEmailProvider()
    if provider == "sendgrid":
        from app.providers.email.sendgrid import SendgridEmailProvider

        return SendgridEmailProvider()
    raise ValueError(f"Unknown EMAIL_PROVIDER: {settings.email_provider!r}")
