"""Tenant-scoped repository for company-admin users."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select

from app.core.repository import TenantRepository
from app.domains.admins.models import CompanyAdmin, CompanyRole


class CompanyAdminRepository(TenantRepository[CompanyAdmin]):
    model = CompanyAdmin

    async def list_ordered(self) -> Sequence[CompanyAdmin]:
        stmt = (
            select(CompanyAdmin)
            .where(CompanyAdmin.company_id == self.company_id)
            .order_by(CompanyAdmin.created_at.asc())
        )
        return (await self.session.scalars(stmt)).all()

    async def get_by_email(self, email: str) -> CompanyAdmin | None:
        stmt = select(CompanyAdmin).where(
            CompanyAdmin.company_id == self.company_id, CompanyAdmin.email == email
        )
        return await self.session.scalar(stmt)

    async def count_active_owners(self, *, exclude_id=None) -> int:
        stmt = select(func.count()).select_from(CompanyAdmin).where(
            CompanyAdmin.company_id == self.company_id,
            CompanyAdmin.role == CompanyRole.COMPANY_OWNER,
            CompanyAdmin.is_active.is_(True),
        )
        if exclude_id is not None:
            stmt = stmt.where(CompanyAdmin.id != exclude_id)
        return await self.session.scalar(stmt) or 0
