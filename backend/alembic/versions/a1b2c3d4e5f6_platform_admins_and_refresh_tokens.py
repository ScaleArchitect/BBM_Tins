"""platform admins and refresh tokens

Adds Sprint 2 auth tables:
- ``platform_admins`` — BBI internal administrators (not tenant-scoped, no RLS).
- ``refresh_tokens`` — rotating refresh-token store with reuse detection (not
  tenant-scoped; lookup is by token hash before any tenant is known).

Neither table is RLS-protected. The ``tin_app`` role automatically receives
SELECT/INSERT/UPDATE/DELETE on these new tables via the default privileges granted
in migration 0002 (both migrations run as the owner role).

Revision ID: a1b2c3d4e5f6
Revises: 3d27c8ac90bd
Create Date: 2026-06-01
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "3d27c8ac90bd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_admins",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("totp_secret", sa.String(length=255), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM("PLATFORM_OWNER", "PLATFORM_ADMIN", name="platform_role"),
            server_default="PLATFORM_ADMIN",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_platform_admins_email"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("principal_type", sa.String(length=16), nullable=False),
        sa.Column("principal_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_family", "refresh_tokens", ["family_id"], unique=False)
    op.create_index(
        "ix_refresh_tokens_principal",
        "refresh_tokens",
        ["principal_type", "principal_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_principal", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_family", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("platform_admins")
    # Drop enum type (autogenerate does not remove these).
    op.execute("DROP TYPE IF EXISTS platform_role")
