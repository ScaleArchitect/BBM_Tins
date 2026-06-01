"""Branding + settings schemas (US-C1.1 + company settings, ``/admin/...``).

Logo *file* upload is deferred to Sprint 5 (object storage); the colour/welcome/
support fields — the demonstrable core of C1.1 — are managed here. ``has_logo``
reports whether a logo object has been associated.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.domains.companies.enums import GroupCertPolicy

_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_CERT_TYPES = {"VAT", "CT"}
_LOCALES = {"en", "ar"}


def _validate_color(v: str | None) -> str | None:
    if v is None:
        return None
    if not _HEX_COLOR.match(v):
        raise ValueError("colour must be a hex value like #0f2742 or #fff")
    return v.lower()


class BrandingRead(BaseModel):
    primary_color: str | None
    secondary_color: str | None
    welcome_text: str | None
    support_email: str | None
    locale_default: str
    has_logo: bool


class BrandingUpdate(BaseModel):
    primary_color: str | None = Field(default=None, max_length=9)
    secondary_color: str | None = Field(default=None, max_length=9)
    welcome_text: str | None = Field(default=None, max_length=2000)
    support_email: EmailStr | None = None
    locale_default: str | None = None

    _check_primary = field_validator("primary_color")(_validate_color)
    _check_secondary = field_validator("secondary_color")(_validate_color)

    @field_validator("locale_default")
    @classmethod
    def _locale_ok(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        if v not in _LOCALES:
            raise ValueError(f"locale must be one of {sorted(_LOCALES)}")
        return v


class SettingsRead(BaseModel):
    reminder_offsets_days: list[int]
    overdue_after_days: int
    auto_reminders_enabled: bool
    weekly_summary_enabled: bool
    retention_months: int
    enabled_cert_types: list[str]
    group_cert_policy: GroupCertPolicy


class SettingsUpdate(BaseModel):
    reminder_offsets_days: list[int] | None = None
    overdue_after_days: int | None = Field(default=None, ge=1, le=365)
    auto_reminders_enabled: bool | None = None
    weekly_summary_enabled: bool | None = None
    retention_months: int | None = Field(default=None, ge=1, le=120)
    enabled_cert_types: list[str] | None = None
    group_cert_policy: GroupCertPolicy | None = None

    @field_validator("reminder_offsets_days")
    @classmethod
    def _offsets_ok(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        if any(d < 1 or d > 365 for d in v):
            raise ValueError("reminder offsets must be between 1 and 365 days")
        return sorted(set(v))

    @field_validator("enabled_cert_types")
    @classmethod
    def _cert_types_ok(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        up = [c.strip().upper() for c in v]
        bad = [c for c in up if c not in _CERT_TYPES]
        if bad:
            raise ValueError(f"unknown cert types: {bad}; allowed: {sorted(_CERT_TYPES)}")
        if not up:
            raise ValueError("at least one cert type is required")
        return list(dict.fromkeys(up))
