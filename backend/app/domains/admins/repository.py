"""Tenant-scoped repository for company-admin users."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

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
        stmt = select(CompanyAdmin).where(
            CompanyAdmin.company_id == self.company_id,
            CompanyAdmin.role == CompanyRole.COMPANY_OWNER,
            CompanyAdmin.is_active.is_(True),
        )
        owners = (await self.session.scalars(stmt)).all()
        return sum(1 for o in owners if o.id != exclude_id)
