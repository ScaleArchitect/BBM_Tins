"""Company admin user model (tenant-scoped).

Carries `company_id` via TenantMixin and is protected by RLS. Auth fields
(`password_hash`, `totp_secret`) are present but unused until Sprint 2.
See docs/architecture/03 §9.2.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class CompanyRole(StrEnum):
    COMPANY_OWNER = "COMPANY_OWNER"
    COMPANY_ADMIN = "COMPANY_ADMIN"
    COMPANY_VIEWER = "COMPANY_VIEWER"


class CompanyAdmin(Base, TimestampMixin, TenantMixin):
    __tablename__ = "company_admins"
    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uq_company_admins_company_email"),
        ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="RESTRICT",
            name="fk_company_admins_company",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    totp_secret: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[CompanyRole] = mapped_column(
        PgEnum(CompanyRole, name="company_role"),
        nullable=False,
        server_default=CompanyRole.COMPANY_ADMIN.value,
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
