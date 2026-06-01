"""Platform administrator model (BBI internal; not tenant-scoped).

Platform admins manage tenants (companies), subscriptions and ops. They are NOT
subject to RLS — there is no ``company_id`` — and authenticate with email +
password (+ mandatory TOTP, enrolled in a later sprint). See docs/architecture/03 §9.2.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PlatformRole(StrEnum):
    PLATFORM_OWNER = "PLATFORM_OWNER"
    PLATFORM_ADMIN = "PLATFORM_ADMIN"


class PlatformAdmin(Base, TimestampMixin):
    __tablename__ = "platform_admins"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    totp_secret: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[PlatformRole] = mapped_column(
        PgEnum(PlatformRole, name="platform_role"),
        nullable=False,
        server_default=PlatformRole.PLATFORM_ADMIN.value,
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
