"""Append-only audit service (docs/architecture/08 §17).

`record()` inserts an audit row using the caller's session so the audit entry
commits in the SAME transaction as the action it describes. Never updates or
deletes. Metadata must already be masked (no secrets/OTP/full TRN) by the caller.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.models import ActorType, AuditLog


async def record(
    session: AsyncSession,
    *,
    actor_type: ActorType,
    action: str,
    company_id: UUID | None = None,
    actor_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    meta: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        company_id=company_id,
        actor_type=actor_type,
        action=action,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        meta=meta,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(entry)
    await session.flush()
    return entry
