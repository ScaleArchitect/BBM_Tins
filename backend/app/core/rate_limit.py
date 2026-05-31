"""Rate limiter abstraction (placeholder for Sprint 0).

Real Redis-backed sliding-window limiting for OTP/auth/upload/export is added in
Sprint 4+ (see docs/architecture/02 §8.6). The interface is defined now so call
sites can depend on it.
"""

from __future__ import annotations

from typing import Protocol


class RateLimiter(Protocol):
    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Return True if the action is allowed, False if the limit is exceeded."""
        ...


class NoopRateLimiter:
    """Always-allow limiter used until the Redis implementation lands."""

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:  # noqa: ARG002
        return True
