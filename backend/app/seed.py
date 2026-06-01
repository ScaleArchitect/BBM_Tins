"""Idempotent dev bootstrap: create the first platform admin.

Creating platform admins is a bootstrap / ops concern (there is no API for it by
design), so this small script seeds one from settings. Run after migrations:

    python -m app.seed

In Docker Compose a one-shot ``seed`` service runs this automatically. In
production the first platform admin is provisioned by infra, not this script.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password, normalize_email
from app.domains.platform.models import PlatformAdmin, PlatformRole

_log = get_logger("seed")


async def seed_platform_admin() -> None:
    settings = get_settings()
    email = normalize_email(settings.platform_bootstrap_email)
    async with get_sessionmaker()() as session:
        async with session.begin():
            existing = await session.scalar(
                select(PlatformAdmin).where(PlatformAdmin.email == email)
            )
            if existing is not None:
                _log.info("seed_platform_admin_exists", email=email)
                return
            session.add(
                PlatformAdmin(
                    email=email,
                    password_hash=hash_password(settings.platform_bootstrap_password),
                    role=PlatformRole.PLATFORM_OWNER,
                    is_active=True,
                )
            )
        _log.info("seed_platform_admin_created", email=email)


def main() -> None:
    configure_logging()
    asyncio.run(seed_platform_admin())


if __name__ == "__main__":
    main()
