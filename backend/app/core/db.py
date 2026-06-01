"""Async database connection skeleton + tenancy/RLS helper.

The engine is created lazily so importing the app (e.g. in tests) never requires
a live database. Row-Level Security plumbing (``SET LOCAL app.current_company_id``)
is provided here; policies themselves are added in Sprint 1 (see
docs/architecture/06 §13.4, docs/architecture/02 §8.3).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.security import Principal, get_current_principal
from app.core.tenancy import set_current_company_id

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


async def set_current_company(session: AsyncSession, company_id: UUID) -> None:
    """Bind the tenant for the current transaction (RLS enforcement)."""
    # SET LOCAL cannot be parameterised; company_id is a trusted UUID from the
    # auth context, and we render it as a quoted literal to be safe.
    await session.execute(text(f"SET LOCAL app.current_company_id = '{company_id}'"))


@asynccontextmanager
async def tenant_session(company_id: UUID) -> AsyncIterator[AsyncSession]:
    """Yield a session bound to a tenant: sets the request context var AND the
    transaction-local RLS GUC. All work runs inside one transaction so SET LOCAL
    stays in effect. Used by tenant-scoped request handlers and workers."""
    set_current_company_id(company_id)
    try:
        async with get_sessionmaker()() as session:
            async with session.begin():
                await set_current_company(session, company_id)
                yield session
    finally:
        set_current_company_id(None)


async def get_request_session() -> AsyncIterator[AsyncSession]:
    """Transactional session for non-tenant routes (auth, platform).

    Opens one transaction that commits on success / rolls back on error. No RLS
    GUC is set, so RLS-protected tables return nothing unless the caller sets the
    tenant context explicitly (e.g. the platform path seeding a new tenant's rows).
    """
    async with get_sessionmaker()() as session:
        async with session.begin():
            yield session


async def get_tenant_session(
    principal: Principal = Depends(get_current_principal),
) -> AsyncIterator[AsyncSession]:
    """Transactional, tenant-bound session for company-admin routes.

    Sets the request context var AND the transaction-local RLS GUC from the
    authenticated principal's ``company_id`` (defence in depth). Rejects principals
    without a tenant scope (e.g. platform admins hitting a tenant route)."""
    if principal.company_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tenant scope required")
    set_current_company_id(principal.company_id)
    try:
        async with get_sessionmaker()() as session:
            async with session.begin():
                await set_current_company(session, principal.company_id)
                yield session
    finally:
        set_current_company_id(None)


async def check_db() -> bool:
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - readiness probe must not raise
        return False
