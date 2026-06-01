"""Company-admin user management (US-B1.3).

Owners manage their tenant's admins: list, invite (creates the account + emails
temporary credentials), change role, and enable/disable. A guard prevents removing
or demoting the last active owner so a tenant can never be locked out.
"""

from __future__ import annotations

import secrets
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import Principal, hash_password, normalize_email
from app.domains.admins.models import CompanyAdmin, CompanyRole
from app.domains.admins.repository import CompanyAdminRepository
from app.domains.admins.schemas import (
    CompanyAdminCreate,
    CompanyAdminCreateResult,
    CompanyAdminRead,
    CompanyAdminUpdate,
)
from app.domains.audit import service as audit
from app.domains.audit.models import ActorType
from app.domains.companies.models import Company
from app.providers.email.base import EmailMessage, EmailProvider


class AdminEmailTaken(Exception):
    pass


class AdminNotFound(Exception):
    pass


class LastOwnerProtected(Exception):
    """Refuse to disable/demote the last active owner of a tenant."""


def _to_read(admin: CompanyAdmin) -> CompanyAdminRead:
    return CompanyAdminRead(
        id=admin.id,
        email=admin.email,
        role=admin.role,
        is_active=admin.is_active,
        last_login_at=admin.last_login_at,
        created_at=admin.created_at,
    )


async def list_admins(session: AsyncSession) -> list[CompanyAdminRead]:
    repo = CompanyAdminRepository(session)
    return [_to_read(a) for a in await repo.list_ordered()]


async def _send_admin_invite(
    email_provider: EmailProvider,
    *,
    to: str,
    company: Company,
    temp_password: str,
    settings: Settings,
) -> bool:
    login_url = f"{settings.public_base_url.rstrip('/')}/login"
    body_text = (
        f"You have been added as an administrator of {company.legal_name} on the "
        f"TIN Collection Portal.\nSign in at {login_url}\n"
        f"Company: {company.slug}\nEmail: {to}\nTemporary password: {temp_password}\n"
    )
    body_html = (
        f"<p>You have been added as an administrator of "
        f"<strong>{company.legal_name}</strong>.</p>"
        f"<p>Sign in at <a href='{login_url}'>{login_url}</a> — company "
        f"<code>{company.slug}</code>, "
        f"email <code>{to}</code>, temporary password <code>{temp_password}</code>.</p>"
    )
    try:
        await email_provider.send(
            EmailMessage(
                to=to,
                subject=f"You've been added to {company.legal_name}",
                body_html=body_html,
                body_text=body_text,
            )
        )
        return True
    except Exception:  # noqa: BLE001
        return False


async def create_admin(
    session: AsyncSession,
    data: CompanyAdminCreate,
    *,
    actor: Principal,
    email_provider: EmailProvider,
    settings: Settings,
) -> CompanyAdminCreateResult:
    repo = CompanyAdminRepository(session)
    email = normalize_email(data.email)
    if await repo.get_by_email(email) is not None:
        raise AdminEmailTaken

    temp_password = secrets.token_urlsafe(12)
    admin = CompanyAdmin(
        email=email,
        password_hash=hash_password(temp_password),
        role=data.role,
        is_active=True,
    )
    await repo.add(admin)  # stamps company_id from the tenant context

    company = await session.get(Company, actor.company_id)
    invite_sent = (
        await _send_admin_invite(
            email_provider,
            to=email,
            company=company,
            temp_password=temp_password,
            settings=settings,
        )
        if company
        else False
    )

    await audit.record(
        session,
        actor_type=ActorType.COMPANY_ADMIN,
        action="COMPANY_ADMIN_CREATED",
        company_id=actor.company_id,
        actor_id=actor.id,
        entity_type="company_admin",
        entity_id=admin.id,
        meta={"email": email, "role": data.role.value, "invite_sent": invite_sent},
    )
    return CompanyAdminCreateResult(**_to_read(admin).model_dump(), invite_sent=invite_sent)


async def update_admin(
    session: AsyncSession,
    admin_id: UUID,
    data: CompanyAdminUpdate,
    *,
    actor: Principal,
) -> CompanyAdminRead:
    repo = CompanyAdminRepository(session)
    admin = await repo.get(admin_id)
    if admin is None:
        raise AdminNotFound

    # Guard the last active owner against demotion / deactivation.
    demoting = data.role is not None and data.role != CompanyRole.COMPANY_OWNER
    deactivating = data.is_active is False
    if admin.role == CompanyRole.COMPANY_OWNER and (demoting or deactivating):
        if await repo.count_active_owners(exclude_id=admin.id) == 0:
            raise LastOwnerProtected

    changes: dict[str, dict[str, object]] = {}
    if data.role is not None and data.role != admin.role:
        changes["role"] = {"from": admin.role.value, "to": data.role.value}
        admin.role = data.role
    if data.is_active is not None and data.is_active != admin.is_active:
        changes["is_active"] = {"from": admin.is_active, "to": data.is_active}
        admin.is_active = data.is_active

    if changes:
        await audit.record(
            session,
            actor_type=ActorType.COMPANY_ADMIN,
            action="COMPANY_ADMIN_UPDATED",
            company_id=actor.company_id,
            actor_id=actor.id,
            entity_type="company_admin",
            entity_id=admin.id,
            meta=changes,
        )
    return _to_read(admin)
