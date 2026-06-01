"""Company-admin user management routes (``/admin/users`` — US-B1.3).

Owner-only (``MANAGE_ADMINS``). Tenant-scoped session binds RLS to the caller's
company, so every query/write is automatically isolated.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_tenant_session
from app.core.deps import get_email_provider
from app.core.rbac import Permission, require
from app.core.security import Principal
from app.domains.admins import service
from app.domains.admins.schemas import (
    CompanyAdminCreate,
    CompanyAdminCreateResult,
    CompanyAdminRead,
    CompanyAdminUpdate,
)
from app.providers.email.base import EmailProvider

router = APIRouter(prefix="/admin/users", tags=["admin:users"])


@router.get("", response_model=list[CompanyAdminRead], summary="List company admins")
async def list_users(
    _principal: Principal = Depends(require(Permission.MANAGE_ADMINS)),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[CompanyAdminRead]:
    return await service.list_admins(session)


@router.post(
    "",
    response_model=CompanyAdminCreateResult,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a company admin",
)
async def create_user(
    body: CompanyAdminCreate,
    principal: Principal = Depends(require(Permission.MANAGE_ADMINS)),
    email_provider: EmailProvider = Depends(get_email_provider),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_tenant_session),
) -> CompanyAdminCreateResult:
    try:
        return await service.create_admin(
            session, body, actor=principal, email_provider=email_provider, settings=settings
        )
    except service.AdminEmailTaken as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An admin with that email already exists"
        ) from exc


@router.patch("/{admin_id}", response_model=CompanyAdminRead, summary="Update role / status")
async def update_user(
    admin_id: UUID,
    body: CompanyAdminUpdate,
    principal: Principal = Depends(require(Permission.MANAGE_ADMINS)),
    session: AsyncSession = Depends(get_tenant_session),
) -> CompanyAdminRead:
    try:
        return await service.update_admin(session, admin_id, body, actor=principal)
    except service.AdminNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Admin not found") from exc
    except service.LastOwnerProtected as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Cannot remove the last active owner of this company"
        ) from exc
