"""Schemas for the Platform Admin API (docs/architecture/04 §11.1 — ``/platform``)."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.domains.companies.enums import CompanyStatus, SubscriptionStatus

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_CERT_TYPES = {"VAT", "CT"}


class CompanyCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=512)
    slug: str = Field(min_length=2, max_length=63)
    trade_license_number: str | None = Field(default=None, max_length=128)
    primary_admin_email: EmailStr
    enabled_cert_types: list[str] = Field(default_factory=lambda: ["VAT", "CT"])

    @field_validator("slug")
    @classmethod
    def _slug_ok(cls, v: str) -> str:
        v = v.strip().lower()
        if not _SLUG_RE.match(v):
            raise ValueError("slug must be lowercase alphanumeric/hyphen (DNS-label safe)")
        return v

    @field_validator("enabled_cert_types")
    @classmethod
    def _cert_types_ok(cls, v: list[str]) -> list[str]:
        up = [c.strip().upper() for c in v]
        bad = [c for c in up if c not in _CERT_TYPES]
        if bad:
            raise ValueError(f"unknown cert types: {bad}; allowed: {sorted(_CERT_TYPES)}")
        if not up:
            raise ValueError("at least one cert type is required")
        return list(dict.fromkeys(up))  # dedupe, preserve order


class CompanyUpdate(BaseModel):
    status: CompanyStatus | None = None
    subscription_status: SubscriptionStatus | None = None


class CompanyRead(BaseModel):
    id: UUID
    slug: str
    legal_name: str
    trade_license_number: str | None
    status: CompanyStatus
    subscription_status: SubscriptionStatus
    primary_admin_email: str
    enabled_cert_types: list[str] = Field(default_factory=list)
    portal_url: str
    created_at: datetime


class CompanyCreateResult(CompanyRead):
    admin_invite_sent: bool


class CompanyAdminSeed(BaseModel):
    email: EmailStr
    role: str = "COMPANY_ADMIN"
