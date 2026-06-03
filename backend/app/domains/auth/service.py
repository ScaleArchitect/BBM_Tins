"""Admin authentication service (docs/architecture/02 §8.1, §8.6).

Responsibilities:
- **Login** — resolve the principal (platform admin by email, or company admin by
  tenant slug + email), verify the Argon2 password, enforce optional TOTP, apply
  per-identity lockout, and issue an access JWT + a rotating refresh token.
- **Refresh** — validate + rotate the refresh token with reuse detection (a reused
  token revokes the whole family), re-checking the principal's current status/role.
- **Logout** — revoke the refresh-token family.
- **TOTP** — stateless enroll (secret returned, persisted only on verify).

Errors are raised as typed domain exceptions and mapped to HTTP in the router so
the service stays transport-agnostic. No secrets/passwords are ever audited.
"""

from __future__ import annotations

import datetime as dt
import secrets
from uuid import UUID, uuid4

import pyotp
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import set_current_company
from app.core.rate_limit import Throttle
from app.core.security import (
    COMPANY,
    PLATFORM,
    create_access_token,
    hash_token,
    normalize_email,
    verify_password,
)
from app.core.security import Principal as JwtPrincipal
from app.core.tenancy import set_current_company_id
from app.domains.audit import service as audit
from app.domains.audit.models import ActorType
from app.domains.auth import repository as repo
from app.domains.auth.models import RefreshToken
from app.domains.auth.schemas import PrincipalInfo, TokenResponse
from app.domains.companies.enums import CompanyStatus

_BLOCKING_STATUSES = {CompanyStatus.SUSPENDED, CompanyStatus.CANCELLED}


# --------------------------------------------------------------------------- #
# Typed errors (mapped to HTTP in the router)
# --------------------------------------------------------------------------- #
class AuthError(Exception):
    pass


class InvalidCredentials(AuthError):
    pass


class AccountLocked(AuthError):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after


class TenantUnavailable(AuthError):
    """Tenant is suspended or cancelled (A1.2: blocks admin login)."""


class TotpRequired(AuthError):
    pass


class InvalidRefresh(AuthError):
    pass


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _actor(principal_type: str) -> ActorType:
    return ActorType.PLATFORM_ADMIN if principal_type == PLATFORM else ActorType.COMPANY_ADMIN


async def _issue_tokens(
    session: AsyncSession,
    *,
    principal_type: str,
    principal_id: UUID,
    role: str,
    company_id: UUID | None,
    settings: Settings,
    family_id: UUID | None = None,
) -> tuple[str, str, RefreshToken]:
    access, _exp = create_access_token(
        principal_type=principal_type,
        principal_id=principal_id,
        role=role,
        company_id=company_id,
        settings=settings,
    )
    raw_refresh = secrets.token_urlsafe(32)
    token = RefreshToken(
        family_id=family_id or uuid4(),
        token_hash=hash_token(raw_refresh),
        principal_type=principal_type,
        principal_id=principal_id,
        company_id=company_id,
        role=role,
        expires_at=_now() + dt.timedelta(seconds=settings.jwt_refresh_ttl_seconds),
    )
    await repo.add_refresh_token(session, token)
    return access, raw_refresh, token


async def login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    slug: str | None,
    totp_code: str | None,
    throttle: Throttle,
    settings: Settings,
    ip: str | None = None,
    user_agent: str | None = None,
) -> TokenResponse:
    email = normalize_email(email)
    identity = f"{(slug or 'platform').lower()}:{email}"

    remaining = await throttle.check(identity)
    if remaining:
        raise AccountLocked(remaining)

    company_id: UUID | None = None
    company_slug: str | None = None

    if slug:
        company = await repo.get_company_by_slug(session, slug.strip().lower())
        if company is None:
            await _record_failure(session, throttle, identity, ActorType.COMPANY_ADMIN, email, None)
            raise InvalidCredentials
        if company.status in _BLOCKING_STATUSES:
            await audit.record(
                session,
                actor_type=ActorType.COMPANY_ADMIN,
                action="ADMIN_LOGIN_BLOCKED",
                company_id=company.id,
                meta={"email": email, "reason": company.status.value},
                ip_address=ip,
                user_agent=user_agent,
            )
            raise TenantUnavailable
        # Bind RLS to the tenant so the admin lookup is tenant-scoped.
        set_current_company_id(company.id)
        await set_current_company(session, company.id)
        account = await repo.get_company_admin_by_email(session, company.id, email)
        principal_type = COMPANY
        company_id = company.id
        company_slug = company.slug
    else:
        account = await repo.get_platform_admin_by_email(session, email)
        principal_type = PLATFORM

    actor_type = _actor(principal_type)

    if (
        account is None
        or not account.is_active
        or not account.password_hash
        or not verify_password(password, account.password_hash)
    ):
        retry = await _record_failure(session, throttle, identity, actor_type, email, company_id)
        if retry:
            raise AccountLocked(retry)
        raise InvalidCredentials

    if account.totp_secret:
        if not totp_code or not pyotp.TOTP(account.totp_secret).verify(totp_code, valid_window=1):
            retry = await _record_failure(
                session, throttle, identity, actor_type, email, company_id
            )
            if retry:
                raise AccountLocked(retry)
            raise TotpRequired

    await throttle.record_success(identity)
    account.last_login_at = _now()
    role = account.role.value
    access, raw_refresh, _token = await _issue_tokens(
        session,
        principal_type=principal_type,
        principal_id=account.id,
        role=role,
        company_id=company_id,
        settings=settings,
    )
    await audit.record(
        session,
        actor_type=actor_type,
        action="ADMIN_LOGIN_SUCCEEDED",
        company_id=company_id,
        actor_id=account.id,
        ip_address=ip,
        user_agent=user_agent,
    )
    return TokenResponse(
        access_token=access,
        expires_in=settings.jwt_access_ttl_seconds,
        refresh_token=raw_refresh,
        principal=PrincipalInfo(
            id=account.id,
            principal_type=principal_type,
            role=role,
            company_id=company_id,
            company_slug=company_slug,
            email=account.email,
        ),
    )


async def _record_failure(
    session: AsyncSession,
    throttle: Throttle,
    identity: str,
    actor_type: ActorType,
    email: str,
    company_id: UUID | None,
) -> int:
    retry = await throttle.record_failure(identity)
    await audit.record(
        session,
        actor_type=actor_type,
        action="ADMIN_LOGIN_FAILED",
        company_id=company_id,
        meta={"email": email},
    )
    return retry


async def refresh(
    session: AsyncSession,
    *,
    raw_refresh: str,
    settings: Settings,
    ip: str | None = None,
    user_agent: str | None = None,
) -> TokenResponse:
    token = await repo.get_refresh_token(session, hash_token(raw_refresh))
    if token is None:
        raise InvalidRefresh
    now = _now()

    if token.revoked_at is not None:
        # A revoked token presented again => theft. Revoke the entire family.
        await repo.revoke_family(session, token.family_id, now)
        await audit.record(
            session,
            actor_type=_actor(token.principal_type),
            action="REFRESH_REUSE_DETECTED",
            company_id=token.company_id,
            actor_id=token.principal_id,
            ip_address=ip,
            user_agent=user_agent,
        )
        raise InvalidRefresh

    if token.expires_at <= now:
        raise InvalidRefresh

    # Re-validate the principal and pick up the *current* role/status.
    company_slug: str | None = None
    if token.principal_type == PLATFORM:
        account = await repo.get_platform_admin(session, token.principal_id)
        if account is None or not account.is_active:
            raise InvalidRefresh
        company_id = None
    else:
        company = await repo.get_company(session, token.company_id) if token.company_id else None
        if company is None or company.status in _BLOCKING_STATUSES:
            raise InvalidRefresh
        set_current_company_id(company.id)
        await set_current_company(session, company.id)
        account = await repo.get_company_admin(session, token.principal_id)
        if account is None or not account.is_active:
            raise InvalidRefresh
        company_id = company.id
        company_slug = company.slug

    role = account.role.value
    token.revoked_at = now
    access, raw_new, new_token = await _issue_tokens(
        session,
        principal_type=token.principal_type,
        principal_id=token.principal_id,
        role=role,
        company_id=company_id,
        settings=settings,
        family_id=token.family_id,
    )
    token.replaced_by_id = new_token.id
    await audit.record(
        session,
        actor_type=_actor(token.principal_type),
        action="TOKEN_REFRESHED",
        company_id=company_id,
        actor_id=token.principal_id,
        ip_address=ip,
        user_agent=user_agent,
    )
    return TokenResponse(
        access_token=access,
        expires_in=settings.jwt_access_ttl_seconds,
        refresh_token=raw_new,
        principal=PrincipalInfo(
            id=token.principal_id,
            principal_type=token.principal_type,
            role=role,
            company_id=company_id,
            company_slug=company_slug,
            email=account.email,
        ),
    )


async def logout(
    session: AsyncSession,
    *,
    raw_refresh: str,
    principal: JwtPrincipal,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    token = await repo.get_refresh_token(session, hash_token(raw_refresh))
    if token is not None:
        await repo.revoke_family(session, token.family_id, _now())
    await audit.record(
        session,
        actor_type=_actor(principal.principal_type),
        action="ADMIN_LOGGED_OUT",
        company_id=principal.company_id,
        actor_id=principal.id,
        ip_address=ip,
        user_agent=user_agent,
    )


async def load_account(session: AsyncSession, principal: JwtPrincipal):  # noqa: ANN202
    """Load the platform/company admin behind a principal (None if missing/unscoped)."""
    if principal.is_platform:
        return await repo.get_platform_admin(session, principal.id)
    if principal.company_id is None:
        return None
    set_current_company_id(principal.company_id)
    await set_current_company(session, principal.company_id)
    return await repo.get_company_admin(session, principal.id)


async def _totp_pending_key(principal: JwtPrincipal) -> str:
    return f"totp:pending:{principal.principal_type}:{principal.id}"


async def totp_enroll(
    redis: aioredis.Redis,
    *,
    principal: JwtPrincipal,
    account_email: str,
    settings: Settings,
) -> tuple[str, str]:
    """Generate a TOTP secret + provisioning URI.

    The secret is held **server-side** (short-TTL Redis key) until a valid code
    confirms it in :func:`totp_verify`. It is returned here only so the client can
    render the QR/manual-entry code during setup; verification never trusts a
    client-supplied secret.
    """
    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=settings.jwt_issuer)
    await redis.set(
        await _totp_pending_key(principal), secret, ex=settings.totp_pending_ttl_seconds
    )
    return secret, uri


async def totp_verify(
    session: AsyncSession,
    redis: aioredis.Redis,
    *,
    principal: JwtPrincipal,
    code: str,
) -> bool:
    """Confirm the server-held pending secret with a code and persist it.

    Reads the pending secret bound to this principal (never accepts it from the
    client), verifies the code, and on success persists it to the account and
    clears the pending key.
    """
    pending_key = await _totp_pending_key(principal)
    secret = await redis.get(pending_key)
    if not secret:
        return False
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        return False
    account = await load_account(session, principal)
    if account is None:
        raise InvalidCredentials
    account.totp_secret = secret
    await redis.delete(pending_key)
    await audit.record(
        session,
        actor_type=_actor(principal.principal_type),
        action="TOTP_ENROLLED",
        company_id=principal.company_id,
        actor_id=principal.id,
    )
    return True
