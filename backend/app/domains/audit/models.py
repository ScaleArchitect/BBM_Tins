"""Append-only audit log (docs/architecture/03 §9.2, 08 §17).

Append-only: the application/DB role is granted INSERT + SELECT only (no
UPDATE/DELETE). `company_id` is nullable for platform-level events. Note the
column is named `metadata` in SQL but mapped to the `meta` attribute because
`metadata` is reserved on SQLAlchemy declarative classes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ActorType(StrEnum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    COMPANY_ADMIN = "COMPANY_ADMIN"
    BUSINESS_CUSTOMER = "BUSINESS_CUSTOMER"
    SYSTEM = "SYSTEM"


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_company_created", "company_id", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_actor", "actor_type", "actor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    actor_type: Mapped[ActorType] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
