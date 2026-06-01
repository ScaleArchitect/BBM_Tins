"""Integration test harness for the Sprint 2 auth/company endpoints.

Drives the real FastAPI app over ASGI against the compose Postgres (app role
``tin_app`` at localhost). Skips automatically when that DB is not reachable (e.g.
CI without the stack), mirroring the Sprint 1 RLS integration tests.

The login throttle and email provider are overridden with in-memory fakes so tests
are deterministic and need no Redis / SMTP. A bootstrap platform admin is seeded
via the owner connection; all ``itest-*`` tenants are cleaned up around each test.
"""

from __future__ import annotations

import os
import re
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

APP_URL = os.environ.get(
    "TEST_APP_DATABASE_URL", "postgresql+asyncpg://tin_app:tin_app@localhost:5432/tin"
)
OWNER_URL = os.environ.get(
    "DATABASE_ADMIN_URL", "postgresql+asyncpg://tin:tin@localhost:5432/tin"
)

PLATFORM_EMAIL = "itest-platform@tinportal.local"
PLATFORM_PASSWORD = "Itest!Platform1"


async def _reachable(url: str) -> bool:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


async def _seed_platform_admin() -> None:
    from app.core.security import hash_password

    engine = create_async_engine(OWNER_URL)
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM platform_admins WHERE email = :e"), {"e": PLATFORM_EMAIL}
        )
        await conn.execute(
            text(
                "INSERT INTO platform_admins (email, password_hash, role, is_active) "
                "VALUES (:e, :h, 'PLATFORM_OWNER', true)"
            ),
            {"e": PLATFORM_EMAIL, "h": hash_password(PLATFORM_PASSWORD)},
        )
    await engine.dispose()


async def _cleanup() -> None:
    engine = create_async_engine(OWNER_URL)
    async with engine.begin() as conn:
        sub = "SELECT id FROM companies WHERE slug LIKE 'itest-%'"
        await conn.execute(text(f"DELETE FROM company_admins WHERE company_id IN ({sub})"))
        await conn.execute(text(f"DELETE FROM company_settings WHERE company_id IN ({sub})"))
        await conn.execute(text(f"DELETE FROM company_branding WHERE company_id IN ({sub})"))
        await conn.execute(text(f"DELETE FROM audit_logs WHERE company_id IN ({sub})"))
        await conn.execute(text(f"DELETE FROM refresh_tokens WHERE company_id IN ({sub})"))
        await conn.execute(text("DELETE FROM companies WHERE slug LIKE 'itest-%'"))
        await conn.execute(
            text("DELETE FROM refresh_tokens WHERE principal_id IN "
                 "(SELECT id FROM platform_admins WHERE email = :e)"),
            {"e": PLATFORM_EMAIL},
        )
        await conn.execute(
            text("DELETE FROM platform_admins WHERE email = :e"), {"e": PLATFORM_EMAIL}
        )
    await engine.dispose()


class _FakeEmail:
    def __init__(self) -> None:
        self.sent: list = []

    async def send(self, msg):  # noqa: ANN001, ANN202
        from app.providers.email.base import EmailSendResult

        self.sent.append(msg)
        return EmailSendResult(provider_message_id="fake", accepted=True)

    def temp_password_for(self, to: str) -> str | None:
        for msg in self.sent:
            if msg.to == to:
                m = re.search(r"Temporary password: (\S+)", msg.body_text or "")
                if m:
                    return m.group(1)
        return None


@pytest.fixture
async def api():
    if not await _reachable(APP_URL):
        pytest.skip("app DB (tin_app@localhost) not reachable; start the compose stack")

    # Point the app engine at the localhost app role and rebuild lazy singletons.
    os.environ["DATABASE_URL"] = APP_URL
    from app.core import config, db

    config.get_settings.cache_clear()
    db._engine = None
    db._sessionmaker = None

    await _cleanup()
    await _seed_platform_admin()

    from app.core.deps import get_email_provider, get_login_throttle
    from app.core.rate_limit import InMemoryLoginThrottle
    from app.main import app

    throttle = InMemoryLoginThrottle(max_attempts=3, window_seconds=60, lockout_seconds=60)
    email = _FakeEmail()
    app.dependency_overrides[get_login_throttle] = lambda: throttle
    app.dependency_overrides[get_email_provider] = lambda: email

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield SimpleNamespace(
            client=client,
            email=email,
            throttle=throttle,
            platform_email=PLATFORM_EMAIL,
            platform_password=PLATFORM_PASSWORD,
        )

    app.dependency_overrides.clear()
    await _cleanup()
    await db.get_engine().dispose()
