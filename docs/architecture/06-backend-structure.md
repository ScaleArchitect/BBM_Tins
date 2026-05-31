# 06 — Backend Project Structure

Covers output section **13**. FastAPI modular monolith, SQLAlchemy 2.0 + Alembic, Pydantic v2, Arq workers. Layering: `router → service → repository → model`, with provider interfaces for storage/OCR/email/queue.

## 13.1 Folder structure

```
backend/
  app/
    main.py                      # FastAPI app factory, middleware, router mount
    worker.py                    # Arq WorkerSettings (same image, different entrypoint)
    scheduler.py                 # Arq cron jobs (reminders, weekly summary, retention purge)
    core/
      config.py                  # Pydantic Settings (env-driven)
      db.py                      # async engine, session, RLS SET LOCAL helper
      security.py                # JWT, Argon2, OTP hashing, deps (current_principal)
      rbac.py                    # permission enum + require(permission) dependency
      tenancy.py                 # request context var + tenant middleware
      rate_limit.py              # RateLimiter interface + Redis impl
      logging.py                 # structured logging + correlation id
      errors.py                  # problem+json handlers
      pagination.py
    providers/                   # ── ABSTRACTIONS (no domain logic) ──
      storage/
        base.py                  # StorageProvider Protocol
        local_fs.py  minio.py  azure_blob.py
        factory.py               # build from settings.STORAGE_PROVIDER
      ocr/
        base.py                  # OCRProvider Protocol + OCRExtraction model
        local.py                 # PyMuPDF/pdfplumber + Tesseract
        azure_doc_intelligence.py
        factory.py
      email/
        base.py                  # EmailProvider Protocol
        smtp.py  acs.py  sendgrid.py
        factory.py
      queue/
        base.py                  # TaskQueue Protocol
        arq_redis.py  azure_service_bus.py
        factory.py
    domains/                     # ── BUSINESS MODULES ──
      auth/         (router, service, schemas)               # admin login, refresh, totp
      platform/     (router, service, repository, schemas)   # companies, subscription, ops
      companies/    (models, repository, service)            # branding, settings, templates
      admins/       (models, repository, service, router)    # company_admins + RBAC mgmt
      customers/    (models, repository, service, router)    # business_customers, CSV import
      invitations/  (models, repository, service, router)    # tokens, OTP, send/resend
      certificates/ (models, repository, service, router)    # submissions, files, upload
      ocr/          (service, parsers/, tasks.py)            # orchestration + parsing + worker task
      validation/   (trn.py, tin.py, group_cert.py, integrity.py)  # pure rules, unit-tested
      notifications/(models, repository, service, templates/, tasks.py)
      exports/      (models, repository, service, tasks.py)
      audit/        (models, repository, service)            # append-only recorder
      dashboard/    (service, repository)                    # aggregations
    models/base.py               # Base, TimestampMixin, TenantMixin(company_id)
    api/v1/router.py             # aggregates domain routers under /api/v1
  alembic/                       # migrations (versions/, env.py with RLS)
  tests/
    unit/  integration/  e2e/  factories/  conftest.py
  pyproject.toml  Dockerfile  .env.example
```

## 13.2 Layering rules
- **Routers**: HTTP only — parse/validate (Pydantic), call a service, map result to response. No DB, no rules.
- **Services**: business logic, orchestration, transactions, audit calls, enqueue tasks. The only layer that knows multiple repositories.
- **Repositories**: data access; extend `TenantRepository` which auto-scopes by `company_id` and sets RLS. No business logic.
- **Models**: SQLAlchemy 2.0 mapped classes. `TenantMixin` adds `company_id` + relationship.
- **Providers**: pure infrastructure behind Protocols; chosen by factory from settings; **never imported directly by domain code** — injected via FastAPI dependencies.

## 13.3 Configuration (`core/config.py`)
Pydantic `BaseSettings`, 12-factor, env-driven. Key vars (full list in [09-devops-deployment.md](09-devops-deployment.md)):
```
APP_ENV, DATABASE_URL, REDIS_URL,
STORAGE_PROVIDER=local|minio|azure_blob, OCR_PROVIDER=local|azure, EMAIL_PROVIDER=smtp|acs|sendgrid, QUEUE_PROVIDER=arq_redis|service_bus,
JWT_PRIVATE_KEY/JWT_PUBLIC_KEY, OTP_PEPPER, OTP_TTL_SECONDS=600, OTP_MAX_ATTEMPTS=3, OTP_LOCKOUT_SECONDS=1800,
MAX_UPLOAD_MB=10, SIGNED_URL_TTL=300, RETENTION_MONTHS_DEFAULT=24
```

## 13.4 Tenancy & RLS plumbing
```python
# core/tenancy.py
current_company_id: ContextVar[UUID | None] = ContextVar("current_company_id", default=None)

# dependency: after auth, set context from JWT/customer-session claim
# core/db.py: per-request transaction issues:
await session.execute(text("SET LOCAL app.current_company_id = :cid"), {"cid": str(cid)})
```
`TenantRepository.query()` injects `.where(Model.company_id == current_company_id.get())` and raises if unset (except platform paths).

## 13.5 Dependency-injection pattern (providers)
```python
def get_storage(settings: Settings = Depends(get_settings)) -> StorageProvider:
    return storage_factory(settings)        # cached singleton per process
# routers/services receive providers via Depends → trivially swappable + mockable in tests
```

## 13.6 Background worker structure
- `worker.py` registers task functions: `ocr_extract(ctx, submission_id)`, `send_email(ctx, notification_id)`, `generate_export(ctx, export_id)`, `purge_retention(ctx)`.
- Tasks are thin: load entity (system context, RLS bypass with explicit company set), call the same domain **service** used by the API, persist, audit. No duplicated logic.
- **Retry:** Arq `max_tries` with exponential backoff; OCR `FAILED` after final attempt → submission `EXTRACTION_FAILED`, customer offered reprocess. Email failures retried then `FAILED`/`BOUNCED`.
- **Scheduling:** `scheduler.py` cron — daily reminder evaluation, weekly summary (per tenant), nightly retention purge, OTP/challenge cleanup.

## 13.7 Schemas (Pydantic v2)
- Separate `*Create`, `*Update`, `*Read` schemas per resource. `extracted_data`/`confirmed_data` typed as cert-type-specific models (`VatFields`, `CtFields`) validated on confirm. Shared validators (TRN/TIN) live in `validation/` and are reused by schema + service.

## 13.8 Logging & observability
- Structured JSON (`structlog`), correlation id middleware, OpenTelemetry → App Insights on Azure / stdout locally. Never log secrets/PII (see [02](02-security-compliance.md) §8.9). Metrics: request latency, queue depth, OCR duration/confidence, OTP failure/lockout rate, email delivery rate.

## 13.9 Testing approach (summary; full in [11](11-standards-testing-readiness.md))
- **Unit:** `validation/` (TRN normalize/validate, TIN derive, group-cert, integrity), services with mocked providers/repos.
- **Provider contract tests:** one suite run against every storage/OCR/email impl (local + Azure) to guarantee interchangeability.
- **Integration:** FastAPI + ephemeral Postgres (testcontainers) + fake providers; RLS cross-tenant negative tests.
- **E2E:** full invite→OTP→upload→OCR(local)→review→confirm slice.
