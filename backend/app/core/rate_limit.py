"""Rate limiting + login lockout (docs/architecture/02 §8.6).

Two abstractions, both with a Redis implementation and an in-memory implementation
for tests:

- ``RateLimiter`` — fixed-window counter (``hit`` returns False when the limit is hit).
- ``LoginThrottle`` — per-identity failure counter + lockout. ``check`` reports the
  remaining lock seconds; ``record_failure`` increments and locks past the cap;
  ``record_success`` clears the counter.

Admin login throttling is keyed per account (and the caller may also key per IP).
"""

from __future__ import annotations

import time
from typing import Protocol

import redis.asyncio as aioredis


class RateLimiter(Protocol):
    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Return True if the action is allowed, False if the limit is exceeded."""
        ...


class Throttle(Protocol):
    """Login lockout interface shared by the Redis + in-memory implementations."""

    async def check(self, identity: str) -> int: ...

    async def record_failure(self, identity: str) -> int: ...

    async def record_success(self, identity: str) -> None: ...


class NoopRateLimiter:
    """Always-allow limiter (used where limiting is intentionally disabled)."""

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:  # noqa: ARG002
        return True


class RedisRateLimiter:
    """Fixed-window counter: INCR the key, set TTL on first hit, allow while <= limit."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, window_seconds)
        return count <= limit


class LoginThrottle:
    """Per-identity failed-login counter with lockout, backed by Redis."""

    def __init__(
        self, redis: aioredis.Redis, *, max_attempts: int, window_seconds: int, lockout_seconds: int
    ) -> None:
        self._redis = redis
        self._max = max_attempts
        self._window = window_seconds
        self._lockout = lockout_seconds

    @staticmethod
    def _fail_key(identity: str) -> str:
        return f"login:fail:{identity}"

    @staticmethod
    def _lock_key(identity: str) -> str:
        return f"login:lock:{identity}"

    async def check(self, identity: str) -> int:
        """Return remaining lock seconds (0 if not locked)."""
        ttl = await self._redis.ttl(self._lock_key(identity))
        return ttl if ttl and ttl > 0 else 0

    async def record_failure(self, identity: str) -> int:
        """Increment the failure counter; lock the identity once it reaches the cap.

        Returns the remaining lock seconds (0 if not yet locked)."""
        count = await self._redis.incr(self._fail_key(identity))
        if count == 1:
            await self._redis.expire(self._fail_key(identity), self._window)
        if count >= self._max:
            await self._redis.set(self._lock_key(identity), "1", ex=self._lockout)
            await self._redis.delete(self._fail_key(identity))
            return self._lockout
        return 0

    async def record_success(self, identity: str) -> None:
        await self._redis.delete(self._fail_key(identity), self._lock_key(identity))


class InMemoryLoginThrottle:
    """In-memory throttle with the same interface as :class:`LoginThrottle` (tests)."""

    def __init__(self, *, max_attempts: int, window_seconds: int, lockout_seconds: int) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._lockout = lockout_seconds
        self._fails: dict[str, list[float]] = {}
        self._locks: dict[str, float] = {}

    async def check(self, identity: str) -> int:
        until = self._locks.get(identity, 0.0)
        remaining = int(until - time.monotonic())
        return remaining if remaining > 0 else 0

    async def record_failure(self, identity: str) -> int:
        now = time.monotonic()
        hits = [t for t in self._fails.get(identity, []) if now - t < self._window]
        hits.append(now)
        self._fails[identity] = hits
        if len(hits) >= self._max:
            self._locks[identity] = now + self._lockout
            self._fails.pop(identity, None)
            return self._lockout
        return 0

    async def record_success(self, identity: str) -> None:
        self._fails.pop(identity, None)
        self._locks.pop(identity, None)
