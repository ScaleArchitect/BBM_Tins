"""Platform Admin routes (docs/architecture/04 §11.1 — ``/platform``).

All routes require a platform principal with ``MANAGE_COMPANIES``. Tenant creation
also seeds the owner admin + config and sends the invitation email.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_request_session
from app.core.deps import get_email_provider
from app.core.pagination import Page, PageParams
from app.core.rbac import Permission, require
from app.core.security import Principal
from app.domains.platform import service
from app.domains.platform.schemas import (
    CompanyCreate,
    CompanyCreateResult,
    CompanyRead,
    CompanyUpdate,
)
from app.providers.email.base import EmailProvider

router = APIRouter(prefix="/platform", tags=["platform"])


@router.post(
    "/companies",
    response_model=CompanyCreateResult,
    status_code=status.HTTP_201_CREATED,
    summary="Create tenant (FR-001)",
)
async def create_company(
    body: CompanyCreate,
    principal: Principal = Depends(require(Permission.MANAGE_COMPANIES)),
    email_provider: EmailProvider = Depends(get_email_provider),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_request_session),
) -> CompanyCreateResult:
    try:
        return await service.create_company(
            session, body, actor=principal, email_provider=email_provider, settings=settings
        )
    except service.SlugTaken as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A company with that slug already exists"
        ) from exc


@router.get("/companies", response_model=Page[CompanyRead], summary="List/search tenants")
async def list_companies(
    page: PageParams = Depends(),
    q: str | None = Query(default=None, max_length=128),
    _principal: Principal = Depends(require(Permission.MANAGE_COMPANIES)),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_request_session),
) -> Page[CompanyRead]:
    items, total = await service.list_companies(
        session, offset=page.offset, limit=page.page_size, q=q, settings=settings
    )
    return Page[CompanyRead](items=items, page=page.page, page_size=page.page_size, total=total)


@router.get("/companies/{company_id}", response_model=CompanyRead, summary="Tenant detail")
async def get_company(
    company_id: UUID,
    _principal: Principal = Depends(require(Permission.MANAGE_COMPANIES)),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_request_session),
) -> CompanyRead:
    try:
        return await service.get_company(session, company_id, settings=settings)
    except service.CompanyNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found") from exc


@router.patch(
    "/companies/{company_id}",
    response_model=CompanyRead,
    summary="Update status / subscription (FR-001, A1.2)",
)
async def update_company(
    company_id: UUID,
    body: CompanyUpdate,
    principal: Principal = Depends(require(Permission.MANAGE_COMPANIES)),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_request_session),
) -> CompanyRead:
    try:
        return await service.update_company(
            session, company_id, body, actor=principal, settings=settings
        )
    except service.CompanyNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found") from exc
