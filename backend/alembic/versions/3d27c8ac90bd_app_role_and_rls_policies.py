"""app role and rls policies

Creates a dedicated NON-SUPERUSER application role (`tin_app`) and enables +
FORCES Row-Level Security on tenant-scoped tables so cross-tenant access is
impossible even with an ORM/SQL bug. The application connects as `tin_app`;
migrations and platform/cross-tenant operations connect as the owner/superuser
(which bypasses RLS by design — see docs/architecture/02 §8.3).

Notes:
- The `tin_app` role here is a DEV convenience (password from APP_DB_PASSWORD,
  default 'tin_app'). In Azure, infra (Key Vault + managed identity / provisioned
  role) owns role creation; the RLS DDL below is the production-relevant part.
- RLS predicate uses current_setting('app.current_company_id', true): unset ->
  NULL -> no rows (deny by default). The app sets it per transaction via
  `SET LOCAL app.current_company_id = :id` (app.core.db.set_current_company).
- audit_logs is append-only: tin_app gets INSERT + SELECT only (UPDATE/DELETE
  revoked); it is not RLS-restricted here because platform events have a NULL
  company_id (scoped reads are enforced in the audit query layer).

Revision ID: 3d27c8ac90bd
Revises: ed36863c3869
Create Date: 2026-06-01
"""
from __future__ import annotations

import os
from collections.abc import Sequence

from alembic import op

revision: str = "3d27c8ac90bd"
down_revision: str | None = "ed36863c3869"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "tin_app"
TENANT_TABLES = ("company_admins", "company_settings", "company_branding")


def upgrade() -> None:
    app_pw = os.environ.get("APP_DB_PASSWORD", "tin_app")

    # 1. Dedicated non-superuser application role (idempotent).
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{app_pw}'
                    NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
            END IF;
        END
        $$;
        """
    )

    # 2. Privileges: CRUD on existing + future tables; append-only on audit_logs.
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE};")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};"
    )
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE};"
    )
    # audit_logs is append-only for the app role.
    op.execute(f"REVOKE UPDATE, DELETE ON audit_logs FROM {APP_ROLE};")

    # 3. Enable + FORCE RLS and a tenant-isolation policy on each tenant table.
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid)
                WITH CHECK (company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid);
            """
        )


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
    # Revert default privileges before the role can be dropped.
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE};"
    )
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE};")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE};")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE};")
    op.execute(f"DROP ROLE IF EXISTS {APP_ROLE};")
