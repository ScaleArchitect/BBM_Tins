"""Async database connection skeleton + tenancy/RLS helper.

The engine is created lazily so importing the app (e.g. in tests) never requires
a live database. Row-Level Security plumbing (``SET LOCAL app.current_company_id``)
is provided here; policies themselves are added in Sprint 1 (see
docs/architecture/06 §13.4, docs/architecture/02 §8.3).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

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
    """Bind the tenant for the current transaction (RLS enforcement, Sprint 1)."""
    await session.execute(
        text("SET LOCAL app.current_company_id = :cid"), {"cid": str(company_id)}
    )


async def check_db() -> bool:
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - readiness probe must not raise
        return False
