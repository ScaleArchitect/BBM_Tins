"""Tenant-aware repository base (docs/architecture/06 §13.2/13.4).

Defence-in-depth layer on top of Postgres RLS: every query is auto-scoped to the
current tenant (`company_id` from the request context var), and writes stamp the
tenant id. If the tenant context is unset, operations refuse rather than leak.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy import require_company_id
from app.models.base import Base, TenantMixin

ModelT = TypeVar("ModelT", bound=Base)


class TenantRepository(Generic[ModelT]):
    """Base repository for tenant-scoped models (must inherit TenantMixin)."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        if not issubclass(self.model, TenantMixin):
            raise TypeError(f"{self.model.__name__} is not tenant-scoped (no TenantMixin).")
        self.session = session

    @property
    def company_id(self) -> UUID:
        return require_company_id()

    async def list(self) -> Sequence[ModelT]:
        stmt = select(self.model).where(self.model.company_id == self.company_id)
        return (await self.session.scalars(stmt)).all()

    async def get(self, entity_id: UUID) -> ModelT | None:
        stmt = select(self.model).where(
            self.model.id == entity_id, self.model.company_id == self.company_id
        )
        return await self.session.scalar(stmt)

    async def add(self, entity: ModelT) -> ModelT:
        # Stamp the tenant so callers cannot accidentally (or maliciously) write
        # cross-tenant rows; RLS WITH CHECK enforces this at the DB too.
        entity.company_id = self.company_id
        self.session.add(entity)
        await self.session.flush()
        return entity
