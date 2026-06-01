"""Schemas for company-admin user management (US-B1.3, ``/admin/users``)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.domains.admins.models import CompanyRole


class CompanyAdminCreate(BaseModel):
    email: EmailStr
    role: CompanyRole = CompanyRole.COMPANY_ADMIN


class CompanyAdminUpdate(BaseModel):
    role: CompanyRole | None = None
    is_active: bool | None = None


class CompanyAdminRead(BaseModel):
    id: UUID
    email: str
    role: CompanyRole
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class CompanyAdminCreateResult(CompanyAdminRead):
    invite_sent: bool
