"""Branding + settings service (US-C1.1 + company settings).

Tenant-scoped: the caller's session is bound to their company via RLS, so the
1:1 ``company_branding`` / ``company_settings`` rows are fetched by ``company_id``.
Rows are created on tenant onboarding; this service create-if-missing for safety.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, normalize_email
from app.domains.audit import service as audit
from app.domains.audit.models import ActorType
from app.domains.companies.models import CompanyBranding, CompanySettings
from app.domains.companies.schemas import (
    BrandingRead,
    BrandingUpdate,
    SettingsRead,
    SettingsUpdate,
)


async def _branding_row(session: AsyncSession, company_id: UUID) -> CompanyBranding:
    row = await session.get(CompanyBranding, company_id)
    if row is None:
        row = CompanyBranding(company_id=company_id)
        session.add(row)
        await session.flush()
    return row


async def _settings_row(session: AsyncSession, company_id: UUID) -> CompanySettings:
    row = await session.get(CompanySettings, company_id)
    if row is None:
        row = CompanySettings(company_id=company_id)
        session.add(row)
        await session.flush()
    return row


def _branding_read(row: CompanyBranding) -> BrandingRead:
    return BrandingRead(
        primary_color=row.primary_color,
        secondary_color=row.secondary_color,
        welcome_text=row.welcome_text,
        support_email=row.support_email,
        locale_default=row.locale_default,
        has_logo=row.logo_object_key is not None,
    )


def _settings_read(row: CompanySettings) -> SettingsRead:
    return SettingsRead(
        reminder_offsets_days=list(row.reminder_offsets_days),
        overdue_after_days=row.overdue_after_days,
        auto_reminders_enabled=row.auto_reminders_enabled,
        weekly_summary_enabled=row.weekly_summary_enabled,
        retention_months=row.retention_months,
        enabled_cert_types=list(row.enabled_cert_types),
        group_cert_policy=row.group_cert_policy,
    )


async def get_branding(session: AsyncSession, company_id: UUID) -> BrandingRead:
    return _branding_read(await _branding_row(session, company_id))


async def update_branding(
    session: AsyncSession, company_id: UUID, data: BrandingUpdate, *, actor: Principal
) -> BrandingRead:
    row = await _branding_row(session, company_id)
    payload = data.model_dump(exclude_unset=True)
    if "support_email" in payload and payload["support_email"]:
        payload["support_email"] = normalize_email(str(payload["support_email"]))
    for field, value in payload.items():
        setattr(row, field, value)
    if payload:
        await audit.record(
            session,
            actor_type=ActorType.COMPANY_ADMIN,
            action="BRANDING_UPDATED",
            company_id=company_id,
            actor_id=actor.id,
            entity_type="company_branding",
            entity_id=company_id,
            meta={"fields": sorted(payload.keys())},
        )
    return _branding_read(row)


async def get_settings(session: AsyncSession, company_id: UUID) -> SettingsRead:
    return _settings_read(await _settings_row(session, company_id))


async def update_settings(
    session: AsyncSession, company_id: UUID, data: SettingsUpdate, *, actor: Principal
) -> SettingsRead:
    row = await _settings_row(session, company_id)
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(row, field, value)
    if payload:
        await audit.record(
            session,
            actor_type=ActorType.COMPANY_ADMIN,
            action="SETTINGS_UPDATED",
            company_id=company_id,
            actor_id=actor.id,
            entity_type="company_settings",
            entity_id=company_id,
            meta={"fields": sorted(payload.keys())},
        )
    return _settings_read(row)
