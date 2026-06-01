"""Platform (tenant) management service (US-A1.1/A1.2).

Creates tenants and their initial config + owner admin atomically, seeds/Resends
the first-admin invitation email, and manages company status/subscription. Every
state change is audited as a PLATFORM_ADMIN action.
"""

from __future__ import annotations

import secrets
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import set_current_company
from app.core.security import Principal, hash_password, normalize_email
from app.core.tenancy import set_current_company_id
from app.domains.admins.models import CompanyAdmin, CompanyRole
from app.domains.audit import service as audit
from app.domains.audit.models import ActorType
from app.domains.companies.models import Company, CompanyBranding, CompanySettings
from app.domains.platform import repository as repo
from app.domains.platform.schemas import (
    CompanyCreate,
    CompanyCreateResult,
    CompanyRead,
    CompanyUpdate,
)
from app.providers.email.base import EmailMessage, EmailProvider


class SlugTaken(Exception):
    pass


class CompanyNotFound(Exception):
    pass


def _portal_url(settings: Settings, slug: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/{slug}"


def _to_read(company: Company, settings: Settings) -> CompanyRead:
    cert_types = list(company.settings.enabled_cert_types) if company.settings else []
    return CompanyRead(
        id=company.id,
        slug=company.slug,
        legal_name=company.legal_name,
        trade_license_number=company.trade_license_number,
        status=company.status,
        subscription_status=company.subscription_status,
        primary_admin_email=company.primary_admin_email,
        enabled_cert_types=cert_types,
        portal_url=_portal_url(settings, company.slug),
        created_at=company.created_at,
    )


async def _send_invite(
    email_provider: EmailProvider,
    *,
    to: str,
    company: Company,
    temp_password: str,
    settings: Settings,
) -> bool:
    """Send the first-admin invitation with initial credentials. Best-effort.

    NOTE: Sprint 2 emails a temporary password directly (captured by Mailpit
    locally). The proper one-time set-password link lands with the notification
    engine in Sprint 3 (see Deliverables follow-ups).
    """
    login_url = f"{settings.public_base_url.rstrip('/')}/login"
    body_html = (
        f"<p>You have been invited to administer <strong>{company.legal_name}</strong> "
        f"on the TIN Collection Portal.</p>"
        f"<p>Sign in at <a href='{login_url}'>{login_url}</a> with:</p>"
        f"<ul><li>Company: <code>{company.slug}</code></li>"
        f"<li>Email: <code>{to}</code></li>"
        f"<li>Temporary password: <code>{temp_password}</code></li></ul>"
        f"<p>Please change your password after your first sign-in.</p>"
    )
    body_text = (
        f"You have been invited to administer {company.legal_name} on the TIN Collection Portal.\n"
        f"Sign in at {login_url}\n"
        f"Company: {company.slug}\nEmail: {to}\nTemporary password: {temp_password}\n"
    )
    try:
        await email_provider.send(
            EmailMessage(
                to=to,
                subject=f"Your {company.legal_name} admin invitation",
                body_html=body_html,
                body_text=body_text,
            )
        )
        return True
    except Exception:  # noqa: BLE001 — invite delivery must not fail tenant creation
        return False


async def create_company(
    session: AsyncSession,
    data: CompanyCreate,
    *,
    actor: Principal,
    email_provider: EmailProvider,
    settings: Settings,
) -> CompanyCreateResult:
    if await repo.get_by_slug(session, data.slug) is not None:
        raise SlugTaken
    admin_email = normalize_email(data.primary_admin_email)

    company = Company(
        slug=data.slug,
        legal_name=data.legal_name,
        trade_license_number=data.trade_license_number,
        primary_admin_email=admin_email,
        created_by_platform_admin=actor.id,
    )
    session.add(company)
    await session.flush()  # assign company.id

    # Child config tables are RLS-forced; bind the GUC to the new tenant.
    set_current_company_id(company.id)
    await set_current_company(session, company.id)

    settings_row = CompanySettings(
        company_id=company.id, enabled_cert_types=data.enabled_cert_types
    )
    branding_row = CompanyBranding(company_id=company.id)
    session.add_all([settings_row, branding_row])

    temp_password = secrets.token_urlsafe(12)
    owner = CompanyAdmin(
        company_id=company.id,
        email=admin_email,
        password_hash=hash_password(temp_password),
        role=CompanyRole.COMPANY_OWNER,
        is_active=True,
    )
    session.add(owner)
    await session.flush()

    invite_sent = await _send_invite(
        email_provider,
        to=admin_email,
        company=company,
        temp_password=temp_password,
        settings=settings,
    )

    await audit.record(
        session,
        actor_type=ActorType.PLATFORM_ADMIN,
        action="COMPANY_CREATED",
        company_id=company.id,
        actor_id=actor.id,
        entity_type="company",
        entity_id=company.id,
        meta={"slug": company.slug, "primary_admin_email": admin_email},
    )
    await audit.record(
        session,
        actor_type=ActorType.PLATFORM_ADMIN,
        action="COMPANY_ADMIN_CREATED",
        company_id=company.id,
        actor_id=actor.id,
        entity_type="company_admin",
        entity_id=owner.id,
        meta={
            "email": admin_email,
            "role": CompanyRole.COMPANY_OWNER.value,
            "invite_sent": invite_sent,
        },
    )

    # eager-load settings for the response (already in session)
    company.settings = settings_row
    base = _to_read(company, settings)
    return CompanyCreateResult(**base.model_dump(), admin_invite_sent=invite_sent)


async def get_company(
    session: AsyncSession, company_id: UUID, *, settings: Settings
) -> CompanyRead:
    company = await repo.get(session, company_id)
    if company is None:
        raise CompanyNotFound
    return _to_read(company, settings)


async def list_companies(
    session: AsyncSession, *, offset: int, limit: int, q: str | None, settings: Settings
) -> tuple[list[CompanyRead], int]:
    items, total = await repo.list_companies(session, offset=offset, limit=limit, q=q)
    return [_to_read(c, settings) for c in items], total


async def update_company(
    session: AsyncSession,
    company_id: UUID,
    data: CompanyUpdate,
    *,
    actor: Principal,
    settings: Settings,
) -> CompanyRead:
    company = await repo.get(session, company_id)
    if company is None:
        raise CompanyNotFound

    changes: dict[str, dict[str, str]] = {}
    if data.status is not None and data.status != company.status:
        changes["status"] = {"from": company.status.value, "to": data.status.value}
        company.status = data.status
    sub = data.subscription_status
    if sub is not None and sub != company.subscription_status:
        changes["subscription_status"] = {
            "from": company.subscription_status.value,
            "to": data.subscription_status.value,
        }
        company.subscription_status = data.subscription_status

    if changes:
        await audit.record(
            session,
            actor_type=ActorType.PLATFORM_ADMIN,
            action="COMPANY_STATUS_CHANGED",
            company_id=company.id,
            actor_id=actor.id,
            entity_type="company",
            entity_id=company.id,
            meta=changes,
        )
    return _to_read(company, settings)
