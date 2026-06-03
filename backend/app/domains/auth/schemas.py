"""Pydantic schemas for the admin auth API (docs/architecture/04 §11.1)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    # Company admins authenticate against their tenant's portal (slug identifies it).
    # Omit `slug` for a platform-admin login.
    slug: str | None = Field(default=None, max_length=63)
    # Required only if the account has TOTP enrolled.
    totp_code: str | None = Field(default=None, max_length=10)


class PrincipalInfo(BaseModel):
    id: UUID
    principal_type: str
    role: str
    company_id: UUID | None = None
    company_slug: str | None = None
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    principal: PrincipalInfo


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TotpEnrollResponse(BaseModel):
    secret: str
    otpauth_url: str


class TotpVerifyRequest(BaseModel):
    # The pending secret is held server-side (keyed by principal) between
    # /totp/enroll and /totp/verify; the client only submits the code.
    code: str = Field(min_length=6, max_length=10)
