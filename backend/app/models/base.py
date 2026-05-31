"""SQLAlchemy declarative base + shared mixins.

Every tenant-scoped model inherits ``TenantMixin`` (mandatory ``company_id``),
which—together with RLS and the repository guard—enforces tenant isolation
(IA-01, docs/architecture/02 §8.3, docs/architecture/03).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TenantMixin:
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), index=True, nullable=False
    )
