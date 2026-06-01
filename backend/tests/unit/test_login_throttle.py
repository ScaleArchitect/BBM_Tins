"""Unit tests for the in-memory login throttle (lockout semantics, no Redis)."""

from __future__ import annotations

import pytest

from app.core.rate_limit import InMemoryLoginThrottle


@pytest.fixture
def throttle() -> InMemoryLoginThrottle:
    return InMemoryLoginThrottle(max_attempts=3, window_seconds=900, lockout_seconds=900)


async def test_not_locked_initially(throttle: InMemoryLoginThrottle) -> None:
    assert await throttle.check("acme:a@x.ae") == 0


async def test_locks_after_max_failures(throttle: InMemoryLoginThrottle) -> None:
    ident = "acme:a@x.ae"
    assert await throttle.record_failure(ident) == 0  # 1
    assert await throttle.record_failure(ident) == 0  # 2
    locked = await throttle.record_failure(ident)  # 3 -> lock
    assert locked == 900
    assert await throttle.check(ident) > 0


async def test_success_clears_failures(throttle: InMemoryLoginThrottle) -> None:
    ident = "acme:a@x.ae"
    await throttle.record_failure(ident)
    await throttle.record_failure(ident)
    await throttle.record_success(ident)
    # Counter reset: two more failures should not lock yet.
    assert await throttle.record_failure(ident) == 0
    assert await throttle.record_failure(ident) == 0
    assert await throttle.check(ident) == 0


async def test_identities_are_independent(throttle: InMemoryLoginThrottle) -> None:
    await throttle.record_failure("acme:a@x.ae")
    await throttle.record_failure("acme:a@x.ae")
    await throttle.record_failure("acme:a@x.ae")
    assert await throttle.check("acme:a@x.ae") > 0
    assert await throttle.check("globex:b@x.ae") == 0
