# 09 — Deployment & DevOps Design

Covers output section **18** plus the concrete implementation guidance (output §9: Docker Compose, env vars, pipeline). Maps to requested section O (concrete implementation guidance) for deployment items.

## 18.1 Repository layout (monorepo)
```
/                      (git root, currently here)
  backend/             FastAPI + worker (see 06)
  frontend/            Next.js (see 05)
  infra/
    docker/            Dockerfiles, entrypoints
    compose/           docker-compose.yml + overrides
    azure/             Bicep/Terraform for ACA, Postgres, Blob, KV, etc.
    nginx-or-traefik/  proxy config
  docs/architecture/   these documents
  observations/        analysis + clarifications
  .github/workflows/   CI/CD
```

## 18.2 Local — `docker-compose.yml` (outline)
```yaml
services:
  proxy:    { image: traefik:v3, ports: ["80:80","443:443"], volumes: [./infra/.../traefik.yml], depends_on: [web, api] }
  web:      { build: ./frontend, env_file: .env, depends_on: [api] }              # next start
  api:      { build: ./backend,  command: uvicorn app.main:app --host 0.0.0.0 --port 8000, env_file: .env, depends_on: [db, redis, storage] }
  worker:   { build: ./backend,  command: arq app.worker.WorkerSettings, env_file: .env, depends_on: [db, redis, storage] }
  scheduler:{ build: ./backend,  command: arq app.scheduler.SchedulerSettings, env_file: .env, depends_on: [db, redis] }
  db:       { image: postgres:16, environment: [POSTGRES_*], volumes: [pgdata:/var/lib/postgresql/data], ports: ["5432:5432"] }
  redis:    { image: redis:7, ports: ["6379:6379"] }
  storage:  { image: minio/minio, command: server /data --console-address ":9001", ports: ["9000:9000","9001:9001"], volumes: [minio:/data] }
  mail:     { image: axllent/mailpit, ports: ["8025:8025","1025:1025"] }          # SMTP 1025, UI 8025
volumes: { pgdata: {}, minio: {} }
```
- `api` and `worker` share the **same image** (`./backend`), different `command`.
- One-shot init: `alembic upgrade head` + MinIO bucket create + seed platform admin (entrypoint or `make seed`).
- `make up` / `make seed` / `make test` developer ergonomics.

## 18.3 Example environment variables (`.env.example`)
```
APP_ENV=local
# data
DATABASE_URL=postgresql+asyncpg://tin:tin@db:5432/tin
REDIS_URL=redis://redis:6379/0
# providers
STORAGE_PROVIDER=minio
MINIO_ENDPOINT=http://storage:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
STORAGE_BUCKET=tin-certs
OCR_PROVIDER=local
EMAIL_PROVIDER=smtp
SMTP_HOST=mail
SMTP_PORT=1025
EMAIL_FROM="Acme Tax Portal <no-reply@taxportal.ae>"
QUEUE_PROVIDER=arq_redis
# security
JWT_PRIVATE_KEY_PATH=/run/secrets/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/run/secrets/jwt_public.pem
OTP_PEPPER=change-me-32-bytes
OTP_TTL_SECONDS=600
OTP_MAX_ATTEMPTS=3
OTP_LOCKOUT_SECONDS=1800
MAX_UPLOAD_MB=10
SIGNED_URL_TTL=300
RETENTION_MONTHS_DEFAULT=24
# frontend
NEXT_PUBLIC_API_BASE=/api/v1
```
Azure overrides only the provider block: `STORAGE_PROVIDER=azure_blob` (+ `AZURE_STORAGE_ACCOUNT`, managed identity), `OCR_PROVIDER=azure` (+ `AZURE_DOC_INTELLIGENCE_ENDPOINT`), `EMAIL_PROVIDER=acs` (+ `ACS_CONNECTION_*`), `QUEUE_PROVIDER=service_bus`. Secrets come from Key Vault.

## 18.4 Azure topology (Bicep/Terraform in `infra/azure/`)
- **Resource group** in UAE North; VNet with subnets for ACA env + private endpoints.
- **ACA environment** hosting `web`, `api`, `worker` (+ scheduler as a scheduled job or always-on). KEDA scalers: `api` HTTP concurrency; `worker` queue length.
- **PostgreSQL Flexible Server** (zone-redundant HA, private endpoint, 30-day PITR).
- **Storage account** (Blob, private, soft-delete + versioning) + **Key Vault** + **Cache for Redis** / **Service Bus** + **Document Intelligence** (region per OQ4) + **ACS Email**.
- **Front Door + WAF** public ingress, custom domains/tenant subdomains, OWASP ruleset.
- **App Insights + Log Analytics** wired to all apps.
- **Managed identities** for ACA → Blob/KV/Service Bus (no connection-string secrets).

## 18.5 Images & build
- Multi-stage Dockerfiles; non-root user; pinned base images; `pip install` from locked `pyproject`/`uv.lock`; Next.js standalone output.
- Same images promoted local → Azure (build once, deploy by tag). Image scanning (Trivy) + SBOM in CI.

## 18.6 CI/CD (GitHub Actions)
**CI (PR):**
1. Lint/format: `ruff` + `mypy` (backend), `eslint` + `tsc` (frontend).
2. Tests: backend unit + integration (Postgres service / testcontainers), provider contract tests (local impls), frontend unit + Playwright smoke.
3. Security: `pip-audit`, `npm audit`, `gitleaks`, Trivy image scan.
4. Build images, run `alembic upgrade` against ephemeral DB to validate migrations.

**CD (main → staging → prod):**
1. Build + push images to ACR (tagged by SHA).
2. Deploy to **staging** ACA; run DB migrations as a pre-deploy job (`alembic upgrade head`); smoke E2E.
3. Manual approval gate → **prod** (UAE North); same migration job; canary/rolling via ACA revisions; health-check gate; auto-rollback on failed probes.
- Migrations are **forward-only, additive-first** (expand/contract) so rolling deploys don't break running revisions.

## 18.7 Backups, DR, retention
- Postgres automated daily + PITR, 30-day retention; documented + periodically tested restore runbook.
- Blob soft-delete + versioning; GRS paired region (UAE Central).
- Nightly retention-purge job honours per-tenant `retention_months`.

## 18.8 Observability & ops
- Dashboards: request latency (NFR-001 <2s), OCR duration (NFR-002 <30s cloud), queue depth, OTP failure/lockout rate, email delivery/bounce rate, error rate.
- Alerts: API 5xx spike, queue backlog, OCR failure rate, DB CPU/connections, auth-anomaly (login/OTP bruteforce), cert expiry of TLS/domains.
- `/health` (liveness) + `/ready` (DB/redis/storage reachable) endpoints for probes.
