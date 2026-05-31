# 01 — Architecture Overview

Covers output sections **4 (MVP architecture)**, **5 (local)**, **6 (Azure)**, **7 (component-by-component)**.

## 4. Recommended MVP Architecture

### 4.1 Logical view

```
                         ┌─────────────────────────────────────────────┐
                         │              Browser (responsive)            │
                         │  Company Admin · Platform Admin · Customer    │
                         └───────────────┬─────────────────────────────┘
                                         │ HTTPS
                              ┌──────────▼───────────┐
                              │  Reverse proxy        │  Traefik (local) /
                              │  TLS, routing         │  Front Door+ACA ingress (Azure)
                              └─────┬───────────┬─────┘
                       /  (app)     │           │   /api  (REST)
                ┌──────────────────▼┐         ┌─▼───────────────────────┐
                │  Next.js (SSR/CSR) │         │  FastAPI (REST, OpenAPI)│
                │  TS · Tailwind     │  fetch  │  auth · domain services │
                │  BFF route handlers│────────▶│  repository layer (RLS) │
                └────────────────────┘         └───┬─────────┬───────┬───┘
                                                   │         │       │
                              ┌────────────────────▼┐   ┌────▼───┐ ┌─▼──────────────┐
                              │ PostgreSQL           │   │ Redis  │ │ Object storage │
                              │ system of record     │   │ broker │ │ MinIO / Blob   │
                              │ (RLS, JSONB, indexes)│   │ +cache │ │ PDFs (signed)  │
                              └──────────────────────┘   └───┬────┘ └────────────────┘
                                                             │ enqueue
                                              ┌──────────────▼───────────────┐
                                              │  Worker (Arq) processes:      │
                                              │   • OCR jobs                  │
                                              │   • email send                │
                                              │   • reminders (scheduled)     │
                                              │   • exports                   │
                                              └───┬───────────────┬───────────┘
                                                  │               │
                                          ┌───────▼──────┐  ┌─────▼────────┐
                                          │ OCR provider │  │ Email provider│
                                          │ (interface)  │  │ (interface)   │
                                          │ local│Azure  │  │ SMTP│ACS│SG    │
                                          └──────────────┘  └──────────────┘
```

### 4.2 Why this shape

- **Boring 3-tier + workers.** A single FastAPI service (modular monolith), a single worker image (same code, different entrypoint), Postgres, Redis, object storage. No microservices, no K8s. This satisfies the 100/500 concurrency targets with horizontal replicas of the API and worker.
- **Modular monolith, not microservices.** Domain modules (`companies`, `customers`, `invitations`, `auth`, `certificates`, `ocr`, `notifications`, `audit`, `exports`) are cleanly separated *inside* one deployable. They can be split out later if ever needed; doing it now is premature.
- **Worker = same image as API**, started with a different command (`arq app.worker.WorkerSettings`). Guarantees the worker and API share models, schemas, and service code — no drift.
- **Queue choice:** **Arq** (asyncio-native, Redis-backed) for MVP — it fits FastAPI's async model with far less ceremony than Celery. The queue is abstracted behind a `TaskQueue` interface so Azure Service Bus can replace Redis later without touching call sites.

### 4.3 Async OCR sequence (the load-bearing flow)

```
Customer        FastAPI                 Storage        Redis/Queue       Worker            OCR provider
   │  POST /upload  │                       │              │               │                    │
   ├───────────────▶│ validate MIME/size    │              │               │                    │
   │                ├── put(pdf) ───────────▶│              │               │                    │
   │                │  hash, key, metadata   │              │               │                    │
   │                ├── insert submission (UPLOADED) ───────┐               │                    │
   │                ├── enqueue ocr_job(submission_id) ─────▶│               │                    │
   │  202 + sub_id  │◀──────────────────────────────────────┘               │                    │
   │◀───────────────┤                       │              │  pull job ────▶│                    │
   │                │                       │              │               ├── get(pdf) ────────▶│ (storage)
   │                │                       │              │               ├── extract ─────────▶│
   │                │                       │              │               │◀── fields+conf ─────┤
   │                │                       │              │               ├── parse/normalize    │
   │  GET /submissions/{id} (poll/SSE)      │              │               ├── derive TIN, checks │
   │◀───────────────┤ status OCR_COMPLETED  │              │               ├── update submission  │
   │  review form   │ extracted_data+conf   │              │               │  (UNDER_REVIEW)      │
```

Frontend polls `GET /submissions/{id}` (simple, robust) — optional SSE upgrade later. OCR never runs in the request thread.

### 4.4 Single-tenant vs multi-tenant

| Model | Isolation | Ops cost | SaaS fit | Verdict |
|-------|-----------|----------|----------|---------|
| Single-tenant per deployment | Strongest (separate stack) | High (N stacks) | Poor | ❌ rejected for MVP |
| **Controlled multi-tenant, shared DB + RLS** | Strong (row-level + RLS + app guard) | Low | Excellent | ✅ **chosen** |
| DB-per-tenant, shared app | Strong | Medium (N DBs/migrations) | Medium | Possible later for a large/regulated tenant |

**Chosen:** shared-DB multi-tenant. Every tenant-scoped table carries `company_id`. Isolation is enforced at three layers (defence in depth): (1) JWT/ session carries `company_id`; (2) repository base class injects a mandatory `company_id` filter; (3) Postgres **RLS** policy keyed on a per-request `SET app.current_company_id`. Platform Admin context bypasses RLS via a separate role/flag.

## 5. Local Deployment Architecture

`docker compose up` brings the whole platform up offline.

| Service | Image | Role |
|---------|-------|------|
| `proxy` | traefik | TLS (self-signed/ mkcert), routes `/` → web, `/api` → api |
| `web` | node (Next.js) | Frontend, runs `next start` |
| `api` | python (FastAPI/uvicorn) | REST backend |
| `worker` | python (same image as api) | Arq worker: OCR, email, reminders, exports |
| `scheduler` | python (same image) | Arq cron for reminders/weekly summary (or arq's built-in cron) |
| `db` | postgres:16 | System of record |
| `redis` | redis:7 | Queue broker + cache + rate-limit store |
| `storage` | minio | S3-compatible object storage for PDFs |
| `mail` | mailpit (or maildev) | Dev SMTP server + web UI to inspect emails |
| `clamav` *(optional, v1.1)* | clamav/clamav | Malware scan sidecar |

- **OCR local:** runs inside the `worker` image — PyMuPDF/pdfplumber for digital-native text, Tesseract (with `ara`+`eng` language packs) fallback for scanned pages. No external calls.
- **Email local:** SMTP → Mailpit; every email viewable in a browser UI. No mail leaves the machine.
- **Storage local:** MinIO; signed URLs work exactly as Blob signed URLs do, so the upload/download UX is identical to Azure.
- **Secrets local:** `.env` files (git-ignored) loaded by Compose; mirrors Key Vault keys 1:1 so promotion to Azure is a config swap.

See [09-devops-deployment.md](09-devops-deployment.md) for the actual `docker-compose.yml`.

## 6. Azure Deployment Architecture

Target region: **UAE North** (with UAE Central as paired region for DR), subject to per-service availability (OQ4).

| Concern | Azure service | Notes |
|---------|---------------|-------|
| Compute (api, worker, web) | **Azure Container Apps** (ACA) | Same images as local. Separate ACA apps: `web`, `api`, `worker`. KEDA scale rules: api on HTTP concurrency, worker on Redis/Service Bus queue length (scale-to-zero off for worker if using cron). |
| Ingress / WAF | **Azure Front Door** (+ WAF) or App Gateway | TLS termination, custom domains + tenant subdomains, OWASP WAF ruleset. |
| Database | **Azure Database for PostgreSQL Flexible Server** | Zone-redundant HA for ≥99.5%; automated backups, 30-day PITR; private endpoint. |
| Object storage | **Azure Blob Storage** | Private container; access via user-delegation SAS (short-lived). Soft-delete + versioning on. |
| Cache / queue | **Azure Cache for Redis** (MVP parity) or **Service Bus** (preferred for durable queue at scale) | `TaskQueue` interface abstracts which. Start with Redis for parity; Service Bus when durability/ordering matters. |
| OCR | **Azure AI Document Intelligence** (custom + prebuilt models) | If unavailable in UAE North → keep self-hosted OCR worker in-region (OQ4). |
| Email | **Azure Communication Services Email** or **SendGrid** | Behind email interface; SPF/DKIM/DMARC on the sending domain. |
| Secrets | **Azure Key Vault** | DB creds, JWT signing key, OTP pepper, provider keys. ACA references via Key Vault secret refs + managed identity. |
| Identity | **Managed Identity** | ACA → Blob/Key Vault/Service Bus without connection-string secrets. |
| Observability | **Application Insights + Log Analytics** | OpenTelemetry from FastAPI; structured logs; OCR latency, queue depth, OTP failure dashboards + alerts. |
| Networking | VNet + **Private Endpoints** | DB, Redis, Blob, Key Vault private; only Front Door public. |

DR/residency: primary UAE North; backups + Blob GRS paired to UAE Central. No PII leaves UAE (subject to OQ4 OCR decision).

## 7. Component-by-Component Design

For each component: responsibility, key interfaces, MVP implementation, Azure implementation.

### 7.1 Next.js frontend
- **Responsibility:** all three UIs (admin portal, platform admin, branded customer portal); white-label theming per tenant slug; OCR review form; dashboard. **No business logic** — pure presentation + thin BFF.
- **BFF:** Next.js route handlers proxy to FastAPI, attach session cookies, and keep tokens out of client JS where possible. Server components for data-heavy admin pages.
- **Detail:** [05-frontend-design.md](05-frontend-design.md).

### 7.2 FastAPI backend (modular monolith)
- **Responsibility:** REST API, authN/authZ, all domain logic, orchestration of workers. OpenAPI auto-generated.
- **Layering:** `router → service → repository → model`. Pydantic schemas at the edge; SQLAlchemy 2.0 models inside; services hold business rules; repositories enforce tenant scoping.
- **Detail:** [06-backend-structure.md](06-backend-structure.md).

### 7.3 PostgreSQL
- System of record. JSONB for raw OCR + flexible field maps; typed/indexed columns for searchable fields (trn, tin, status, dates, email, names). RLS for tenant isolation. Alembic migrations. Detail: [03-data-model.md](03-data-model.md).

### 7.4 Redis / queue
- Broker for Arq, cache for branding/config lookups, store for OTP rate-limit/lockout counters (atomic INCR + TTL). Abstracted behind `TaskQueue` + `RateLimiter` interfaces.

### 7.5 OCR worker & OCR provider abstraction
- Worker pulls `ocr_job` tasks. `OCRProvider` interface: `extract(file_bytes, cert_type) -> OCRExtraction`. Implementations: `LocalOCRProvider`, `AzureDocIntelligenceProvider`. Selected by `OCR_PROVIDER` env. Detail: [07-ocr-design.md](07-ocr-design.md).

### 7.6 Storage provider abstraction
```python
class StorageProvider(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject: ...
    async def get(self, key: str) -> bytes: ...
    async def signed_url(self, key: str, expires_s: int = 300, disposition: str | None = None) -> str: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
```
- `LocalFsStorageProvider`, `MinioStorageProvider`, `AzureBlobStorageProvider`. Keys are tenant-prefixed: `companies/{company_id}/submissions/{submission_id}/{uuid}.pdf`. Downloads are always via short-lived signed URLs brokered by the API after an authz check — never public.

### 7.7 Email provider abstraction
```python
class EmailProvider(Protocol):
    async def send(self, msg: EmailMessage) -> EmailSendResult: ...   # returns provider message id
```
- `SmtpEmailProvider` (local/Mailpit), `AcsEmailProvider`, `SendGridEmailProvider`. All sends go through the **notification service** (templating + audit + retry), never called ad-hoc. Detail: [08-notifications-export-audit.md](08-notifications-export-audit.md).

### 7.8 Audit service
- Single `audit.record(actor, action, entity, metadata, request_ctx)` API called by every service for sensitive actions. Append-only `audit_logs` table; never updated/deleted. Detail in [08](08-notifications-export-audit.md).

### 7.9 Export service
- Generates CSV/XLSX from filtered query, runs as a worker job for large sets, writes to storage, returns a signed URL; every export is audit-logged with the filter used. Detail in [08](08-notifications-export-audit.md).

### 7.10 Notification / reminder service
- Templated, brand-aware email composition + queueing + retry + bounce tracking; Arq cron drives day-X/2X reminders and the weekly summary. Detail in [08](08-notifications-export-audit.md).

### 7.11 Admin authentication
- Argon2id password hashing; JWT access (short-lived) + rotating refresh; httpOnly secure cookies via the BFF; RBAC roles. Detail in [02-security-compliance.md](02-security-compliance.md).

### 7.12 Business-customer OTP flow
- Invitation token (opaque, signed, single-purpose) → email entry → hashed OTP (10-min TTL, 3 attempts, 30-min lockout via Redis counters) → short-lived customer session scoped to that invitation/company. Detail in [02](02-security-compliance.md).

### 7.13 Dashboard service
- Aggregations (counts by status) + paginated, filterable list queries backed by indexes; drill-down composes submission + files (signed URL) + audit history. Detail in [04-api-design.md](04-api-design.md).
