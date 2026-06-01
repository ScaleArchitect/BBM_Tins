"""Company branding + settings routes (``/admin/branding``, ``/admin/settings``).

Owner-only (``MANAGE_BRANDING`` / ``MANAGE_SETTINGS``). Tenant-scoped session.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_tenant_session
from app.core.rbac import Permission, require
from app.core.security import Principal
from app.domains.companies import service
from app.domains.companies.schemas import (
    BrandingRead,
    BrandingUpdate,
    SettingsRead,
    SettingsUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin:branding-settings"])


@router.get("/branding", response_model=BrandingRead, summary="Get branding (FR-002)")
async def get_branding(
    principal: Principal = Depends(require(Permission.MANAGE_BRANDING)),
    session: AsyncSession = Depends(get_tenant_session),
) -> BrandingRead:
    return await service.get_branding(session, principal.company_id)


@router.put("/branding", response_model=BrandingRead, summary="Update branding (FR-002)")
async def update_branding(
    body: BrandingUpdate,
    principal: Principal = Depends(require(Permission.MANAGE_BRANDING)),
    session: AsyncSession = Depends(get_tenant_session),
) -> BrandingRead:
    return await service.update_branding(session, principal.company_id, body, actor=principal)


@router.get("/settings", response_model=SettingsRead, summary="Get company settings")
async def get_settings(
    principal: Principal = Depends(require(Permission.MANAGE_SETTINGS)),
    session: AsyncSession = Depends(get_tenant_session),
) -> SettingsRead:
    return await service.get_settings(session, principal.company_id)


@router.put("/settings", response_model=SettingsRead, summary="Update company settings")
async def update_settings(
    body: SettingsUpdate,
    principal: Principal = Depends(require(Permission.MANAGE_SETTINGS)),
    session: AsyncSession = Depends(get_tenant_session),
) -> SettingsRead:
    return await service.update_settings(session, principal.company_id, body, actor=principal)
