"""Shared FastAPI dependencies (settings, Redis, throttle, providers, request meta).

Providers are built once per process from settings (factory pattern,
docs/architecture/06 §13.5) and injected so routers/services stay swappable and
test-mockable. Tests override these via ``app.dependency_overrides``.
"""

from __future__ import annotations

from functools import lru_cache

import redis.asyncio as aioredis
from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.rate_limit import LoginThrottle, RedisRateLimiter, Throttle
from app.providers.email.base import EmailProvider
from app.providers.email.factory import build_email_provider
from app.providers.storage.base import StorageProvider
from app.providers.storage.factory import build_storage_provider


@lru_cache
def _redis(url: str) -> aioredis.Redis:
    return aioredis.from_url(url, decode_responses=True)


def get_redis(settings: Settings = Depends(get_settings)) -> aioredis.Redis:
    return _redis(settings.redis_url)


def get_rate_limiter(redis: aioredis.Redis = Depends(get_redis)) -> RedisRateLimiter:
    return RedisRateLimiter(redis)


def get_login_throttle(
    settings: Settings = Depends(get_settings),
    redis: aioredis.Redis = Depends(get_redis),
) -> Throttle:
    return LoginThrottle(
        redis,
        max_attempts=settings.login_max_attempts,
        window_seconds=settings.login_attempt_window_seconds,
        lockout_seconds=settings.login_lockout_seconds,
    )


@lru_cache
def _email_provider() -> EmailProvider:
    return build_email_provider(get_settings())


@lru_cache
def _storage_provider() -> StorageProvider:
    return build_storage_provider(get_settings())


def get_email_provider() -> EmailProvider:
    return _email_provider()


def get_storage_provider() -> StorageProvider:
    return _storage_provider()


def client_ip(request: Request) -> str | None:
    # Honour the proxy's forwarded-for, else the socket peer.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")
