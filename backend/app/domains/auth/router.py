"""Admin authentication routes (docs/architecture/04 §11.1 — ``/auth``).

The router is transport-only: it maps typed service errors to HTTP problem
responses. Tokens are returned in the JSON body; the Next.js BFF stores them in
httpOnly cookies so they never touch client JS (docs/architecture/05 §12.8).
"""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_request_session
from app.core.deps import client_ip, get_login_throttle, get_rate_limiter, get_redis, user_agent
from app.core.rate_limit import RateLimiter, Throttle
from app.core.security import Principal, get_current_principal
from app.domains.auth import service
from app.domains.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    PrincipalInfo,
    RefreshRequest,
    TokenResponse,
    TotpEnrollResponse,
    TotpVerifyRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _map_auth_error(exc: service.AuthError) -> HTTPException:
    if isinstance(exc, service.AccountLocked):
        return HTTPException(
            status.HTTP_423_LOCKED,
            f"Too many attempts. Try again in {exc.retry_after // 60 + 1} minutes.",
            headers={"Retry-After": str(exc.retry_after)},
        )
    if isinstance(exc, service.TenantUnavailable):
        return HTTPException(status.HTTP_403_FORBIDDEN, "This account is not available.")
    if isinstance(exc, service.TotpRequired):
        return HTTPException(status.HTTP_401_UNAUTHORIZED, "A valid TOTP code is required.")
    if isinstance(exc, service.InvalidRefresh):
        return HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session.")
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")


@router.post("/login", response_model=TokenResponse, summary="Admin login (password [+TOTP])")
async def login(
    body: LoginRequest,
    ip: str | None = Depends(client_ip),
    ua: str | None = Depends(user_agent),
    throttle: Throttle = Depends(get_login_throttle),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_request_session),
) -> TokenResponse:
    try:
        return await service.login(
            session,
            email=body.email,
            password=body.password,
            slug=body.slug,
            totp_code=body.totp_code,
            throttle=throttle,
            settings=settings,
            ip=ip,
            user_agent=ua,
        )
    except service.AuthError as exc:
        raise _map_auth_error(exc) from exc


@router.post("/refresh", response_model=TokenResponse, summary="Rotate refresh token")
async def refresh(
    body: RefreshRequest,
    ip: str | None = Depends(client_ip),
    ua: str | None = Depends(user_agent),
    limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_request_session),
) -> TokenResponse:
    allowed = await limiter.hit(
        f"refresh:{ip or 'unknown'}",
        settings.refresh_max_per_window,
        settings.refresh_window_seconds,
    )
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many refresh attempts. Please slow down.",
            headers={"Retry-After": str(settings.refresh_window_seconds)},
        )
    try:
        return await service.refresh(
            session, raw_refresh=body.refresh_token, settings=settings, ip=ip, user_agent=ua
        )
    except service.AuthError as exc:
        raise _map_auth_error(exc) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke session")
async def logout(
    body: LogoutRequest,
    response: Response,
    ip: str | None = Depends(client_ip),
    ua: str | None = Depends(user_agent),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_request_session),
) -> Response:
    await service.logout(
        session, raw_refresh=body.refresh_token, principal=principal, ip=ip, user_agent=ua
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=PrincipalInfo, summary="Current principal")
async def me(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_request_session),
) -> PrincipalInfo:
    account = await service.load_account(session, principal)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account no longer available")
    return PrincipalInfo(
        id=principal.id,
        principal_type=principal.principal_type,
        role=principal.role,
        company_id=principal.company_id,
        email=account.email,
    )


@router.post("/totp/enroll", response_model=TotpEnrollResponse, summary="Begin TOTP enrolment")
async def totp_enroll(
    principal: Principal = Depends(get_current_principal),
    redis: aioredis.Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_request_session),
) -> TotpEnrollResponse:
    account = await service.load_account(session, principal)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    secret, uri = await service.totp_enroll(
        redis, principal=principal, account_email=account.email, settings=settings
    )
    return TotpEnrollResponse(secret=secret, otpauth_url=uri)


@router.post("/totp/verify", summary="Confirm + activate TOTP")
async def totp_verify(
    body: TotpVerifyRequest,
    principal: Principal = Depends(get_current_principal),
    redis: aioredis.Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_request_session),
) -> dict[str, bool]:
    ok = await service.totp_verify(session, redis, principal=principal, code=body.code)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid TOTP code")
    return {"enrolled": True}
