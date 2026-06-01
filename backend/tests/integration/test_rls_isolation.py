"""DB-backed cross-tenant RLS isolation tests (Sprint 1 acceptance gate).

Skips automatically if a Postgres with the Sprint-1 schema + `tin_app` role is
not reachable (e.g. CI without the compose stack). Locally:
    docker compose -f infra/compose/docker-compose.yml up -d
    cd backend && pytest tests/integration -v
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ADMIN_URL = os.environ.get(
    "DATABASE_ADMIN_URL", "postgresql+asyncpg://tin:tin@localhost:5432/tin"
)
APP_URL = os.environ.get(
    "TEST_APP_DATABASE_URL", "postgresql+asyncpg://tin_app:tin_app@localhost:5432/tin"
)

COMPANY_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
COMPANY_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


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


@pytest.fixture
async def seeded():
    if not await _reachable(ADMIN_URL):
        pytest.skip("Postgres admin connection not reachable; start the compose stack.")
    admin = create_async_engine(ADMIN_URL)
    async with admin.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO companies (id, slug, legal_name, primary_admin_email) VALUES
                  (:a, 'rls-a', 'RLS A LLC', 'a@rls.test'),
                  (:b, 'rls-b', 'RLS B LLC', 'b@rls.test')
                ON CONFLICT (id) DO NOTHING;
                """
            ),
            {"a": str(COMPANY_A), "b": str(COMPANY_B)},
        )
        await conn.execute(
            text(
                """
                INSERT INTO company_admins (company_id, email, role) VALUES
                  (:a, 'admin@rls-a.test', 'COMPANY_OWNER'),
                  (:b, 'admin@rls-b.test', 'COMPANY_OWNER')
                ON CONFLICT (company_id, email) DO NOTHING;
                """
            ),
            {"a": str(COMPANY_A), "b": str(COMPANY_B)},
        )
    await admin.dispose()
    yield
    cleanup = create_async_engine(ADMIN_URL)
    async with cleanup.begin() as conn:
        await conn.execute(
            text("DELETE FROM company_admins WHERE company_id IN (:a, :b)"),
            {"a": str(COMPANY_A), "b": str(COMPANY_B)},
        )
        await conn.execute(
            text("DELETE FROM companies WHERE id IN (:a, :b)"),
            {"a": str(COMPANY_A), "b": str(COMPANY_B)},
        )
    await cleanup.dispose()


async def _count_as_tenant(conn, company_id: uuid.UUID | None) -> int:
    if company_id is not None:
        await conn.execute(text(f"SET LOCAL app.current_company_id = '{company_id}'"))
    return await conn.scalar(text("SELECT count(*) FROM company_admins"))


@pytest.mark.asyncio
async def test_tenant_sees_only_its_own_rows(seeded) -> None:
    app = create_async_engine(APP_URL)
    try:
        async with app.connect() as conn:
            async with conn.begin():
                assert await _count_as_tenant(conn, COMPANY_A) == 1
                email = await conn.scalar(text("SELECT email FROM company_admins"))
                assert email == "admin@rls-a.test"
            async with conn.begin():
                assert await _count_as_tenant(conn, COMPANY_B) == 1
                email = await conn.scalar(text("SELECT email FROM company_admins"))
                assert email == "admin@rls-b.test"
    finally:
        await app.dispose()


@pytest.mark.asyncio
async def test_unset_tenant_sees_nothing(seeded) -> None:
    app = create_async_engine(APP_URL)
    try:
        async with app.connect() as conn, conn.begin():
            assert await _count_as_tenant(conn, None) == 0  # deny by default
    finally:
        await app.dispose()


@pytest.mark.asyncio
async def test_with_check_blocks_cross_tenant_insert(seeded) -> None:
    app = create_async_engine(APP_URL)
    try:
        async with app.connect() as conn, conn.begin():
            await conn.execute(text(f"SET LOCAL app.current_company_id = '{COMPANY_A}'"))
            # Attempt to insert a row for tenant B while scoped to A -> RLS WITH CHECK.
            with pytest.raises(Exception):  # noqa: B017,PT011
                await conn.execute(
                    text(
                        "INSERT INTO company_admins (company_id, email, role) "
                        "VALUES (:b, 'evil@rls-a.test', 'COMPANY_ADMIN')"
                    ),
                    {"b": str(COMPANY_B)},
                )
    finally:
        await app.dispose()
