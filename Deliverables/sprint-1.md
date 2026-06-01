# Sprint 1 — Foundation (data + tenancy spine)

**Status:** ✅ Complete
**Date:** 2026-06-01
**Goal:** Establish the data foundation and the multi-tenant isolation spine that
every later feature depends on — core schema, Row-Level Security, tenant-aware
data access, and append-only audit.
**Plan ref:** [docs/architecture/10-backlog-sprints.md](../docs/architecture/10-backlog-sprints.md) (Sprint 1) ·
**Demo:** [sprint_demos/sprint-1.md](../sprint_demos/sprint-1.md)
**Commits:** `d9b387a` (models + migrations + RLS), `8053c65` (repository, audit, middleware, wiring + tests).

---

## 1. Scope delivered

- Core SQLAlchemy models on `Base.metadata`: `companies` (tenant root), `company_settings`, `company_branding` (1:1), `company_admins` (tenant-scoped), `audit_logs` (append-only).
- First real Alembic migrations:
  - `0001` (`ed36863c3869`) — tables, enums, indexes, FKs, constraints.
  - `0002` (`3d27c8ac90bd`) — non-superuser app role `tin_app` + **ENABLE/FORCE RLS** + tenant-isolation policies.
- **Triple-layer tenant isolation:** request context var → `TenantRepository` auto-scoping → Postgres RLS (defence in depth).
- `tenant_session()` helper: sets the request context var **and** the transaction-local RLS GUC (`SET LOCAL app.current_company_id`).
- Append-only **audit service** (`audit.record(...)`, same-transaction insert; `tin_app` has no UPDATE/DELETE on `audit_logs`).
- **Correlation-id middleware** (`X-Request-ID`, bound to structlog).
- Compose: one-shot **`migrate`** service runs migrations as owner before app start; api/worker/scheduler connect as **`tin_app`**.

## 2. Artifacts

| File | Purpose |
|------|---------|
| [backend/app/domains/companies/models.py](../backend/app/domains/companies/models.py) · [enums.py](../backend/app/domains/companies/enums.py) | Company + settings + branding; status/subscription/group-cert enums |
| [backend/app/domains/admins/models.py](../backend/app/domains/admins/models.py) | `CompanyAdmin` (tenant-scoped) + `CompanyRole` |
| [backend/app/domains/audit/models.py](../backend/app/domains/audit/models.py) · [service.py](../backend/app/domains/audit/service.py) | Append-only `AuditLog` + recorder service |
| [backend/alembic/versions/ed36863c3869_initial_foundation.py](../backend/alembic/versions/ed36863c3869_initial_foundation.py) | 0001 schema migration |
| [backend/alembic/versions/3d27c8ac90bd_app_role_and_rls_policies.py](../backend/alembic/versions/3d27c8ac90bd_app_role_and_rls_policies.py) | 0002 app role + RLS |
| [backend/app/core/repository.py](../backend/app/core/repository.py) | `TenantRepository` base (auto tenant scoping) |
| [backend/app/core/db.py](../backend/app/core/db.py) | `tenant_session()` + `set_current_company()` |
| [backend/app/core/middleware.py](../backend/app/core/middleware.py) | Correlation-id middleware |
| [backend/tests/unit/test_tenancy.py](../backend/tests/unit/test_tenancy.py) | Context/repository guard unit tests |
| [backend/tests/integration/test_rls_isolation.py](../backend/tests/integration/test_rls_isolation.py) | DB-backed cross-tenant RLS tests |
| [infra/compose/docker-compose.yml](../infra/compose/docker-compose.yml) | `migrate` service + `tin_app` app connection |

## 3. RLS design (how isolation is enforced)

1. **App role:** the app connects as `tin_app` — `NOSUPERUSER NOBYPASSRLS`. Migrations/platform paths use the owner (`tin`), which bypasses RLS by design.
2. **FORCE RLS** on `company_admins`, `company_settings`, `company_branding`.
3. **Policy:** `company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid` for both `USING` and `WITH CHECK`. Unset/empty context → NULL → **0 rows (deny by default)**; `WITH CHECK` blocks writing another tenant's `company_id`.
4. **App layer:** `TenantRepository` also filters by `company_id` and stamps it on insert — so isolation holds even before the query reaches the DB.

## 4. Acceptance criteria — met

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Core schema migrates cleanly (up + down) | ✅ | `alembic upgrade head` / `downgrade` run; enums dropped on downgrade |
| Non-superuser app role enforced | ✅ | `current_user=tin_app`, `rolsuper=f` |
| Tenant sees only its own rows | ✅ | ACME→1, GLOBEX→1 (live psql + integration test) |
| Unset context returns nothing (deny by default) | ✅ | no-ctx → 0 rows |
| Cross-tenant write blocked | ✅ | `WITH CHECK` rejects insert for other tenant (integration test) |
| Audit append-only | ✅ | `UPDATE/DELETE` revoked from `tin_app` on `audit_logs` |
| Tests pass | ✅ | **10 passed** (3 health + 4 tenancy unit + 3 RLS integration) |
| Migrations run automatically before app | ✅ | `migrate` service exit 0; api gated on `service_completed_successfully` |

## 5. Gaps / follow-ups

- No tenant-facing **endpoints** yet (Sprint 2 adds auth + sets the tenant context from the JWT). The spine is built and tested; it is wired into request handling in Sprint 2.
- `audit_logs` is not RLS-restricted (platform events have NULL `company_id`); scoped reads will be enforced in the audit query layer when the admin audit endpoint is built.
- Integration tests **skip** in CI (no DB); they run locally against the compose stack. A future option: testcontainers in CI.
- Dev `tin_app` password is a fixed dev value; production role/secret is provisioned by infra (Azure Key Vault), reusing the same RLS DDL.

## 6. Sign-off

Foundation complete and demonstrated. **Next:** Sprint 2 — Authentication & Company
Management (Argon2 + JWT admin auth, platform company onboarding, branding, RBAC),
which will set the tenant context from the authenticated principal so the spine
built here is exercised by real requests.
