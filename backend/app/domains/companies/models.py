"""Company (tenant root) + 1:1 settings/branding models.

`companies` is the tenant root and is NOT tenant-scoped (no RLS). Its child
config tables key on `company_id` as PK/FK. See docs/architecture/03 §9.2.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domains.companies.enums import CompanyStatus, GroupCertPolicy, SubscriptionStatus
from app.models.base import Base, TimestampMixin


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Lowercased by the application; unique tenant slug / subdomain.
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    legal_name: Mapped[str] = mapped_column(Text, nullable=False)
    trade_license_number: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CompanyStatus] = mapped_column(
        PgEnum(CompanyStatus, name="company_status"),
        nullable=False,
        server_default=CompanyStatus.PENDING.value,
    )
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        PgEnum(SubscriptionStatus, name="subscription_status"),
        nullable=False,
        server_default=SubscriptionStatus.TRIAL.value,
    )
    primary_admin_email: Mapped[str] = mapped_column(String(320), nullable=False)
    created_by_platform_admin: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))

    settings: Mapped[CompanySettings] = relationship(
        back_populates="company", uselist=False, cascade="all, delete-orphan"
    )
    branding: Mapped[CompanyBranding] = relationship(
        back_populates="company", uselist=False, cascade="all, delete-orphan"
    )


class CompanySettings(Base, TimestampMixin):
    __tablename__ = "company_settings"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    reminder_offsets_days: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, server_default=text("'{3,7,14}'")
    )
    overdue_after_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("21")
    )
    auto_reminders_enabled: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("true")
    )
    weekly_summary_enabled: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("true")
    )
    retention_months: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("24")
    )
    enabled_cert_types: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{VAT,CT}'")
    )
    group_cert_policy: Mapped[GroupCertPolicy] = mapped_column(
        PgEnum(GroupCertPolicy, name="group_cert_policy"),
        nullable=False,
        server_default=GroupCertPolicy.REJECT.value,
    )

    company: Mapped[Company] = relationship(back_populates="settings")


class CompanyBranding(Base, TimestampMixin):
    __tablename__ = "company_branding"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    logo_object_key: Mapped[str | None] = mapped_column(Text)
    primary_color: Mapped[str | None] = mapped_column(String(9))
    secondary_color: Mapped[str | None] = mapped_column(String(9))
    welcome_text: Mapped[str | None] = mapped_column(Text)
    support_email: Mapped[str | None] = mapped_column(String(320))
    locale_default: Mapped[str] = mapped_column(String(5), nullable=False, server_default="en")

    company: Mapped[Company] = relationship(back_populates="branding")
