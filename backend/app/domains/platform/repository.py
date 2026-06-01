"""Data access for platform (tenant) management.

``companies`` is the RLS-exempt tenant root, so the platform path reads/writes it
with the ordinary app session. Child config tables (``company_settings``,
``company_branding``, ``company_admins``) are RLS-forced — the service binds the
RLS GUC to the new tenant before inserting their rows.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.companies.models import Company


async def get_by_slug(session: AsyncSession, slug: str) -> Company | None:
    return await session.scalar(select(Company).where(Company.slug == slug))


async def get(session: AsyncSession, company_id: UUID) -> Company | None:
    return await session.scalar(
        select(Company).options(selectinload(Company.settings)).where(Company.id == company_id)
    )


async def list_companies(
    session: AsyncSession, *, offset: int, limit: int, q: str | None
) -> tuple[Sequence[Company], int]:
    stmt = select(Company).options(selectinload(Company.settings))
    count_stmt = select(func.count()).select_from(Company)
    if q:
        like = f"%{q.strip().lower()}%"
        cond = or_(func.lower(Company.legal_name).like(like), Company.slug.like(like))
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    stmt = stmt.order_by(Company.created_at.desc()).offset(offset).limit(limit)
    items = (await session.scalars(stmt)).all()
    total = await session.scalar(count_stmt) or 0
    return items, total
