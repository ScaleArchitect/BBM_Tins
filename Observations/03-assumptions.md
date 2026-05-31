# Implementation Assumptions

**Project:** TIN Collection Portal  
**Date:** 2026-06-01  
**Status:** Active for Sprint 0 and early MVP development  
**Related:** 
- `observations/02-clarifications.md`
- `docs/architecture/00-index.md`
- `docs/architecture/01-architecture-overview.md`
- `docs/architecture/03-data-model.md`
- `docs/architecture/06-backend-structure.md`
- `docs/architecture/09-devops-deployment.md`
- `docs/architecture/10-backlog-sprints.md`

## Purpose

This document records the safe assumptions that will be used to start implementation of the TIN Collection Portal.

These assumptions allow Sprint 0 scaffolding and early MVP development to proceed without waiting for all client clarifications. Any assumption that may change later must be implemented through configuration, provider abstraction, or isolated domain logic.

No assumption in this document should require a redesign if the client later confirms a different decision.

---

## 1. Implementation Assumptions Summary

| ID | Area | Assumption | Configurable? | Blocks Sprint 0? | Confirm before |
|---|---|---|---|---|---|
| IA-01 | Tenancy | Controlled multi-tenant from day one using shared PostgreSQL, `company_id`, RLS, and repository guard | No, architectural baseline | No | Already decided |
| IA-02 | Deployment model | Local Docker Compose first, Azure deployment later | Yes, by environment/provider config | No | Production |
| IA-03 | Backend | FastAPI modular monolith | No, architectural baseline | No | Already decided |
| IA-04 | Frontend | Next.js, TypeScript, Tailwind | No, architectural baseline | No | Already decided |
| IA-05 | Async jobs | Arq + Redis for local MVP | Yes, behind `TaskQueue` provider | No | Azure deployment |
| IA-06 | Worker | Same backend image as API, different command | No, architectural baseline | No | Already decided |
| IA-07 | Storage | PDFs stored in object storage only, MinIO locally, Azure Blob later | Yes, behind `StorageProvider` | No | Production |
| IA-08 | OCR | OCR always asynchronous; local OCR first, Azure Document Intelligence later | Yes, behind `OCRProvider` | No | Sprint 6 / Sprint 12 |
| IA-09 | Email | SMTP/Mailpit locally, Azure Communication Services or SendGrid later | Yes, behind `EmailProvider` | No | Production |
| IA-10 | Admin auth | Local Argon2id password + JWT for MVP | Yes, auth provider can later support OIDC | No | Sprint 2 |
| IA-11 | Business customer auth | Invitation link + OTP, no password | Mostly fixed by BRD | No | Already decided |
| IA-12 | OTP policy | 10-minute OTP, 3 attempts, 30-minute lockout | Yes, env config | No | Sprint 4 |
| IA-13 | TIN derivation | Normalize TRN by stripping non-digits, derive TIN from first 10 digits | Yes, isolated in `validation/tin.py` | No | Sprint 6 |
| IA-14 | Integrity check | Compare submitted data to expected customer data as soft flags only | Yes, isolated in `validation/integrity.py` | No | Sprint 6 |
| IA-15 | Group VAT certificate | Default policy is `REJECT`, but tenant setting can switch to `WARN` | Yes, `company_settings.group_cert_policy` | No | Sprint 6 |
| IA-16 | Certificate cardinality | Allow many VAT/CT submissions per customer; latest confirmed per type is current | Schema supports this | No | Not blocking |
| IA-17 | Retention | Default retention is 24 months, configurable per tenant | Yes, `company_settings.retention_months` | No | Sprint 11 / production |
| IA-18 | Certificate expiry | No expiry logic in MVP; reserve status/fields for v1.1 | Yes, additive later | No | v1.1 |
| IA-19 | Azure region | Target UAE North; UAE Central for paired DR where applicable | Yes, infra config | No | Production |
| IA-20 | SSO | Not required for MVP; OIDC can be added later | Yes, auth abstraction | No | Sprint 2 if required |

---

## 2. Detailed Assumptions

### IA-01 — Controlled multi-tenant architecture

We will implement controlled multi-tenancy from day one.

Assumption:
- One shared PostgreSQL database.
- Every tenant-scoped table has `company_id`.
- Postgres Row-Level Security will be used.
- Repository-level tenant guards will also enforce `company_id`.
- Application context will carry the current tenant/company.

Rationale:
- Retrofitting tenancy later is expensive.
- The product is intended to become SaaS or at least multi-company capable.
- RLS plus repository guard gives defence-in-depth.

Implementation impact:
- All tenant-scoped models must inherit from `TenantMixin`.
- All tenant-scoped queries must go through tenant-aware repositories.
- Cross-tenant access tests must be created early.

---

### IA-02 — Local-first, Azure-ready deployment

Assumption:
- Development and early demos will run locally using Docker Compose.
- Production or client-hosted deployment can run on Azure later.
- The same codebase and container images should work in both models.

Local target:
- Docker Compose
- FastAPI API container
- FastAPI worker container
- Next.js frontend container
- PostgreSQL
- Redis
- MinIO
- Mailpit

Azure target:
- Azure Container Apps
- Azure Database for PostgreSQL
- Azure Blob Storage
- Azure Key Vault
- Azure AI Document Intelligence where allowed
- Azure Communication Services or SendGrid
- Azure Cache for Redis or Azure Service Bus
- Application Insights

Implementation impact:
- All external dependencies must be abstracted through providers.
- Environment variables must control provider selection.
- No domain logic should depend directly on Azure SDKs.

---

### IA-03 — Modular monolith backend

Assumption:
- The backend will be a modular monolith using FastAPI.
- Business domains will be separated internally but deployed as one service.

Rationale:
- Avoid microservice overhead during MVP.
- Keep transaction boundaries simple.
- Allow future extraction if required.

Implementation impact:
- Use domain modules such as:
  - `auth`
  - `platform`
  - `companies`
  - `admins`
  - `customers`
  - `invitations`
  - `certificates`
  - `ocr`
  - `validation`
  - `notifications`
  - `exports`
  - `audit`
  - `dashboard`

---

### IA-04 — Frontend technology

Assumption:
- The frontend will use Next.js, TypeScript, and Tailwind CSS.
- The first implementation can be English-first.
- Arabic/RTL support should be designed into the structure but not necessarily completed in Sprint 0.

Implementation impact:
- Use a route structure that can support `en` and `ar`.
- Avoid hard-coding layout directions in ways that block RTL later.
- Keep business rules in the backend, not the frontend.

---

### IA-05 — Async jobs with Arq and Redis

Assumption:
- Local MVP uses Arq with Redis.
- Queueing is abstracted behind a `TaskQueue` interface.
- Azure can later swap this to Service Bus if required.

Implementation impact:
- API should enqueue jobs, not execute long-running work inline.
- OCR, email, export generation, reminders, and retention jobs must run in worker/scheduler processes.
- The worker uses the same backend image as the API.

---

### IA-06 — Object storage for PDFs

Assumption:
- PDFs are never stored in the database.
- PDFs are stored in object storage.
- Metadata, hash, storage key, and status are stored in PostgreSQL.

Local:
- MinIO.

Azure:
- Azure Blob Storage.

Implementation impact:
- Use a `StorageProvider` Protocol.
- Use tenant-prefixed object keys:
  `companies/{company_id}/submissions/{submission_id}/{file_id}.pdf`
- File access must go through signed URLs or backend-controlled download routes.

---

### IA-07 — OCR always asynchronous

Assumption:
- Upload requests return quickly after storing the PDF and enqueueing OCR.
- OCR never runs inside the request thread.
- Local OCR provider is implemented first.
- Azure Document Intelligence provider is added later.

Implementation impact:
- Upload endpoint returns `202 Accepted`.
- Submission status transitions from `UPLOADED` to `PROCESSING` to `UNDER_REVIEW` or `EXTRACTION_FAILED`.
- OCR provider interface must exist from Sprint 0, even if only a stub is implemented.

---

### IA-08 — Email provider abstraction

Assumption:
- Local email uses SMTP with Mailpit.
- Cloud email will use Azure Communication Services Email, SendGrid, or similar.
- All emails go through a notification service.

Implementation impact:
- No direct ad-hoc SMTP calls from domain services.
- All email sends should create a `notifications` record.
- Notification service should support templates later.

---

### IA-09 — Admin authentication

Assumption:
- MVP uses local username/email and password authentication.
- Passwords use Argon2id.
- JWT access and refresh tokens are used.
- Platform Admin MFA is expected later but does not block Sprint 0.
- OIDC/SSO can be added later through an auth provider abstraction.

Implementation impact:
- Build local auth first.
- Do not hardwire the architecture in a way that prevents OIDC later.

---

### IA-10 — Business customer authentication

Assumption:
- Business customers do not have passwords.
- Access is by secure invitation link plus OTP.
- OTP is sent by email.
- OTP is valid for 10 minutes.
- Three failed attempts trigger 30-minute lockout.
- OTP is stored hashed/peppered, never plaintext.

Implementation impact:
- OTP constants must be configurable:
  - `OTP_TTL_SECONDS=600`
  - `OTP_MAX_ATTEMPTS=3`
  - `OTP_LOCKOUT_SECONDS=1800`
- OTP logic should live in the invitations/auth domain.

---

### IA-11 — TIN derivation

Assumption:
- TRN is normalized by stripping all non-digits.
- Valid TRN has 15 digits.
- TIN is derived from the first 10 digits of the normalized TRN.
- This same rule is applied to VAT and CT unless later changed.

Implementation impact:
- Implement as a pure function in `validation/tin.py`.
- Use unit tests.
- Do not scatter TIN derivation logic across services.

---

### IA-12 — Integrity check against customer/group data

Assumption:
- Integrity check is soft-flag only for MVP.
- It compares confirmed submitted values against expected values in the `business_customers` master record where available.
- Mismatch does not block submission.

Fields to compare initially:
- expected TRN
- expected legal name
- expected trade licence number

Implementation impact:
- Store flags in submission `flags` JSON.
- Surface flagged records in dashboard.
- Keep logic isolated in `validation/integrity.py`.

---

### IA-13 — Group VAT certificate policy

Assumption:
- Default policy is `REJECT`.
- Per-tenant setting can switch to `WARN`.
- Detection starts with heuristic parsing and will be improved using sample certificates.

Implementation impact:
- Add `company_settings.group_cert_policy`.
- Keep detection logic in `validation/group_cert.py`.
- Return a structured flag or rejection reason.

---

### IA-14 — Multiple certificate submissions per customer

Assumption:
- A business customer can submit multiple VAT and/or CT certificates.
- Latest confirmed submission per customer per certificate type is treated as current.
- Duplicate TRN/TIN is flagged, not blocked.

Implementation impact:
- Schema must support `business_customer 1:N certificate_submissions`.
- Avoid hard unique constraint on `(company_id, customer_id, cert_type)`.
- Use query logic to identify current/latest confirmed record.

---

### IA-15 — Retention and deletion

Assumption:
- Default data retention is 24 months.
- Retention is tenant-configurable.
- Deletion/anonymisation policy will be confirmed before production.
- For now, design the model to support anonymisation while preserving audit records.

Implementation impact:
- Add `retention_months` to company settings.
- Do not implement destructive purge logic until later sprint.
- Design audit logs as append-only.

---

### IA-16 — Certificate expiry

Assumption:
- No certificate expiry or re-collection logic in MVP.
- Reserve fields/statuses for future use.
- Do not build expiry dashboards in Sprint 0–MVP unless explicitly required later.

Implementation impact:
- Avoid blocking the data model.
- Keep `EXPIRED` as reserved status only if already in model.

---

### IA-17 — Azure assumptions

Assumption:
- Azure target is UAE North where possible.
- If a required Azure service is not available in UAE North, local/self-hosted equivalent should be preferred for sensitive data, especially OCR.
- Azure provider integration is not needed for Sprint 0.

Implementation impact:
- Use provider stubs and interfaces now.
- Keep Azure SDK implementations out of Sprint 0 unless trivial.
- Use `.env.example` to show Azure variables as placeholders.

---

## 3. Environment Defaults for Sprint 0

Use these defaults in `.env.example`:

```env
APP_ENV=local

DATABASE_URL=postgresql+asyncpg://tin:tin@db:5432/tin
REDIS_URL=redis://redis:6379/0

STORAGE_PROVIDER=minio
MINIO_ENDPOINT=http://storage:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
STORAGE_BUCKET=tin-certs

OCR_PROVIDER=local
EMAIL_PROVIDER=smtp
SMTP_HOST=mail
SMTP_PORT=1025
EMAIL_FROM="TIN Portal <no-reply@tinportal.local>"

QUEUE_PROVIDER=arq_redis

JWT_PRIVATE_KEY_PATH=/run/secrets/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/run/secrets/jwt_public.pem

OTP_PEPPER=change-me-32-bytes
OTP_TTL_SECONDS=600
OTP_MAX_ATTEMPTS=3
OTP_LOCKOUT_SECONDS=1800

MAX_UPLOAD_MB=10
SIGNED_URL_TTL=300

GROUP_CERT_POLICY=REJECT
TIN_DERIVATION_MODE=TRN_FIRST_10
RETENTION_MONTHS_DEFAULT=24

NEXT_PUBLIC_API_BASE=/api/v1
```

---

## 4. What these assumptions allow us to build now

These assumptions allow Sprint 0 to proceed with:

* Monorepo structure
* FastAPI base app
* Next.js base app
* Docker Compose
* PostgreSQL
* Redis
* MinIO
* Mailpit
* Worker process
* Scheduler process
* Alembic baseline
* Provider interfaces
* Basic local configuration
* Health endpoints
* CI skeleton
* README

They do not require us to implement:

* Full authentication
* RLS policies
* OCR logic
* Email templates
* Customer upload flow
* Dashboard
* Export
* Azure deployment

Those will follow in later sprints.

---

## 5. Guardrails for implementation

When coding from these assumptions:

1. Do not hard-code values that are listed as configurable.
2. Do not implement Azure-specific logic directly in domain services.
3. Do not store PDFs in the database.
4. Do not run OCR synchronously inside upload requests.
5. Do not bypass tenant scoping in repositories.
6. Do not merge OCR-extracted data and customer-confirmed data into one structure.
7. Do not create business logic in the frontend.
8. Do not implement features beyond Sprint 0 unless explicitly requested.
9. Do not introduce Kubernetes.
10. Do not commit real secrets.

---

## 6. Change Control

If a client decision changes one of these assumptions:

1. Update this document.
2. Update `observations/02-clarifications.md`.
3. Add or update a Decision Log entry if the decision is architectural.
4. Update the relevant architecture document under `docs/architecture/`.
5. Only then update code.
