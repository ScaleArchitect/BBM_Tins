"""Data access for authentication (admins lookup + refresh-token store).

These helpers take an explicit :class:`AsyncSession` (the auth/login route uses a
non-tenant transactional session). Company-admin lookups require the RLS GUC to be
bound to the resolved company first — the service does this via
``db.set_current_company`` before calling :func:`get_company_admin_by_email`.
"""

from __future__ import annotations

import datetime as dt
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.admins.models import CompanyAdmin
from app.domains.auth.models import RefreshToken
from app.domains.companies.models import Company
from app.domains.platform.models import PlatformAdmin


async def get_platform_admin_by_email(session: AsyncSession, email: str) -> PlatformAdmin | None:
    return await session.scalar(select(PlatformAdmin).where(PlatformAdmin.email == email))


async def get_platform_admin(session: AsyncSession, admin_id: UUID) -> PlatformAdmin | None:
    return await session.get(PlatformAdmin, admin_id)


async def get_company_by_slug(session: AsyncSession, slug: str) -> Company | None:
    return await session.scalar(select(Company).where(Company.slug == slug))


async def get_company(session: AsyncSession, company_id: UUID) -> Company | None:
    return await session.get(Company, company_id)


async def get_company_admin_by_email(
    session: AsyncSession, company_id: UUID, email: str
) -> CompanyAdmin | None:
    """Find a company admin by email within a tenant. RLS GUC must already be set."""
    return await session.scalar(
        select(CompanyAdmin).where(
            CompanyAdmin.company_id == company_id, CompanyAdmin.email == email
        )
    )


async def get_company_admin(session: AsyncSession, admin_id: UUID) -> CompanyAdmin | None:
    return await session.scalar(select(CompanyAdmin).where(CompanyAdmin.id == admin_id))


# --- refresh tokens ---
async def add_refresh_token(session: AsyncSession, token: RefreshToken) -> RefreshToken:
    session.add(token)
    await session.flush()
    return token


async def get_refresh_token(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    return await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )


async def revoke_family(session: AsyncSession, family_id: UUID, when: dt.datetime) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=when)
    )
