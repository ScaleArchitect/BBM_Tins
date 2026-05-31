# TIN Collection Portal — Solution Architecture & Delivery Plan

> Implementation-oriented architecture for the white-label B2B UAE TIN collection portal.
> Local-first (Docker Compose), Azure-ready (UAE North). Based on BRD v0.2 + Process Flows v01.
> See also: [observations/01-brd-initial-analysis.md](../../observations/01-brd-initial-analysis.md).

## Document map (maps to the requested 24-section output)

| # | Output section | Document |
|---|----------------|----------|
| 1–3, 24 | Exec summary, assumptions, open questions, next steps | **this file** |
| 4–7 | MVP / local / Azure architecture, component design | [01-architecture-overview.md](01-architecture-overview.md) |
| 8 | Security & compliance | [02-security-compliance.md](02-security-compliance.md) |
| 9–10 | Data model, ERD, status lifecycle | [03-data-model.md](03-data-model.md) |
| 11 | API design | [04-api-design.md](04-api-design.md) |
| 12 | Frontend routes & pages | [05-frontend-design.md](05-frontend-design.md) |
| 13 | Backend project structure | [06-backend-structure.md](06-backend-structure.md) |
| 14 | OCR processing | [07-ocr-design.md](07-ocr-design.md) |
| 15–17 | Notifications, export, audit | [08-notifications-export-audit.md](08-notifications-export-audit.md) |
| 18 | Deployment & DevOps | [09-devops-deployment.md](09-devops-deployment.md) |
| 19–20 | MVP backlog, sprint plan | [10-backlog-sprints.md](10-backlog-sprints.md) |
| 21–23 | Standards, testing, readiness, risks | [11-standards-testing-readiness.md](11-standards-testing-readiness.md) |

---

## 1. Executive Summary

The TIN Collection Portal is a **controlled multi-tenant B2B SaaS**. A subscribing company (tenant) invites its business customers (vendors/suppliers/partners) to upload UAE **VAT** and/or **Corporate Tax** registration certificates (PDF). The system extracts fields via a pluggable OCR layer, lets the customer review/correct, validates TRN/TIN rules, stores the original PDF plus structured + confirmed data, and gives the company an admin dashboard for monitoring, reminders, search/filter, and export.

**Architecture in one line:** Next.js (TS/Tailwind) SPA-ish frontend → FastAPI REST backend → PostgreSQL system of record + object storage for PDFs + Redis-backed async workers for OCR and email. Every external dependency (storage, OCR, email) sits behind a **provider interface** selected by configuration, so the **same codebase** runs on Docker Compose locally (MinIO, Tesseract/PyMuPDF, SMTP) and on Azure (Blob, Document Intelligence, ACS Email) without touching domain logic.

**Key engineering decisions (made, not deferred):**

1. **Tenancy:** Controlled multi-tenant — single DB, single schema, mandatory `company_id` on every tenant-scoped row, isolation enforced in a repository base class **and** PostgreSQL Row-Level Security (RLS) as defence-in-depth. One codebase, clean SaaS path. (Not single-tenant-per-deployment; not DB-per-tenant.)
2. **PDFs never in the database.** Object storage only (MinIO/Blob); DB holds metadata + SHA-256 hash + storage key. Access is via short-lived signed URLs brokered by the backend.
3. **OCR is always asynchronous.** Upload returns immediately; a worker processes the job off a queue. The upload request never runs OCR inline.
4. **Raw OCR output and customer-confirmed values are stored separately** (`ocr_results.raw_json` vs `certificate_submissions.confirmed_data`), with extracted values and per-field confidence in between. Nothing is silently overwritten.
5. **No Kubernetes for MVP.** Docker Compose locally, Azure Container Apps in cloud — both give scale-to-N without K8s operational overhead.
6. **OTP and passwords are never stored in plaintext.** OTP codes are hashed (HMAC-SHA256 with a server pepper); admin passwords use Argon2id.

**Recommended starting tenancy model:** controlled multi-tenant from day one. The isolation cost is low if built in from the start (a `tenant_id` column + RLS), and retrofitting multi-tenancy later is expensive. We do **not** start single-tenant.

## 2. Key Assumptions

| ID | Assumption | Impact if wrong |
|----|-----------|-----------------|
| A1 | UAE FTA VAT & CT certificates are reasonably consistent PDFs (mostly digital-native, some scanned). | OCR templates need rework; scanned-only would force Tesseract/OCR-image path and lower accuracy. |
| A2 | "TIN = first 10 digits of the normalized 15-digit TRN" is the agreed business rule. | TIN derivation logic changes (isolated in one validator). |
| A3 | A "Group VAT certificate" is detectable by the presence of a tax-group / member-entity section or specific title text. | Detection heuristic (FR-028) needs redefining. |
| A4 | "Company group data" for the integrity check = the Company Admin's master customer list (expected legal name / TRN / trade licence per invitee). | The integrity-check feature (U1) changes shape. |
| A5 | Azure UAE North offers the required services (PostgreSQL Flexible Server, Blob, Container Apps, Key Vault, ACS Email/SendGrid, Redis/Service Bus). **Azure AI Document Intelligence may not be in UAE North** — see OQ4. | Cloud OCR may have to run in a nearby region (data-residency exception) or be replaced by a self-hosted OCR container in UAE North. |
| A6 | Email-based OTP (no SMS) is acceptable for business-customer auth per NFR-008. | Add SMS/Twilio provider behind the OTP-delivery abstraction. |
| A7 | VAT/CT certificates do not carry a hard machine-readable expiry; "expiring soon" is a derived/configurable concept. | Expiry lifecycle (U4) needs explicit field + source. |
| A8 | Single FTA certificate format per type for v1 (UAE only). | Multi-format parser registry (already designed for) absorbs it. |

## 3. Open Questions / Clarifications Needed

These block or reshape specific features; carried forward from the BRD analysis (U1–U5, D1–D4) plus new ones surfaced by this design.

| ID | Question | Blocks | Default we will build to if unanswered |
|----|----------|--------|----------------------------------------|
| OQ1 | **Define "group/company data" for the integrity check** (A4). Which fields are authoritative, and is a mismatch a hard block or a soft flag? | Validation service, customer master schema | Soft-flag only: compare confirmed legal name + TRN against expected values on the customer record; mismatch raises a `FLAGGED` warning, never blocks submission. |
| OQ2 | **Group VAT certificate detection rule** (A3, FR-028). Reject outright, or warn-and-allow? | OCR parser, submission flow | Detect via tax-group section/keywords; **block** with the standalone-cert pop-up (BRD wording leans reject). |
| OQ3 | **TIN derivation** (A2): confirm normalize-then-take-first-10. Does CT TIN follow the same rule? ("if applicable by rule" in §7.) | TRN/TIN validator | Same rule for both; store TIN nullable on CT if rule says N/A. |
| OQ4 | **Document Intelligence region.** Is processing certificate data outside UAE North acceptable if the service isn't in-region, or must OCR stay in-country? | Azure OCR provider, compliance | Keep OCR in-region: if Document Intelligence is unavailable in UAE North, use a self-hosted OCR worker (Tesseract/Paddle) in UAE North rather than ship data abroad. |
| OQ5 | **Certificate expiry & re-collection cadence** (U4). Is there an expiry date to capture, and a re-request policy? | Status lifecycle, reminders, retention | No hard expiry in MVP; `EXPIRED` reserved/unused; data retention default 24 months, configurable per tenant. |
| OQ6 | **Data retention / PDPL deletion rights.** Default retention period? Hard-delete vs anonymize on request? | Retention jobs, audit | 24-month retention, soft-delete + scheduled purge; deletion requests anonymize PII but keep audit metadata. |
| OQ7 | **Admin auth model.** Local password (Argon2) only for MVP, or Azure AD / SSO for company admins later? | Auth service | Local Argon2 + JWT for MVP; pluggable OIDC later. |
| OQ8 | **Multiple certificates per customer** — can one customer submit several VAT + several CT certs (e.g., multiple licences), or one of each? | Submission cardinality | Allow many submissions per customer per type; latest confirmed is the "current" record. |

> **Decision:** we proceed on the defaults above so development is not blocked; each is isolated behind a service/config so a different answer is a contained change. Answers should be captured in `02-` of `/observations`.

## 19a. MVP Scope (MoSCoW)

**Must-have (MVP)**
- Platform Admin: create/manage company (tenant), provision slug, set subscription status.
- Company Admin: Argon2/JWT login; branding (logo, colours, welcome text); CSV import + manual add/edit/archive of business customers; bulk + resend invitations; manual + automated reminders.
- Business Customer: invitation link → email → OTP (10 min, 3 attempts, 30-min lockout) → upload VAT/CT PDF (≤10 MB, MIME+hash validated) → async OCR → review/correct → confirm → confirmation email.
- OCR abstraction with **local** provider working end-to-end; raw + extracted + confirmed values stored separately with confidence.
- TRN normalize + 15-digit validate + TIN derive; duplicate TRN/TIN flagging; group-VAT detection; soft integrity check vs master data.
- Dashboard: invited/submitted/pending/overdue/failed/flagged counts; search & filter; drill-down with PDF view + audit history.
- CSV/Excel export (audited); full audit logging.
- Async workers for OCR + email; SMTP email provider; MinIO storage.
- Docker Compose local stack.

**Should-have (v1)**
- Azure deployment (Container Apps, Blob, Document Intelligence, Key Vault, ACS Email, Redis/Service Bus, App Insights).
- Configurable email templates per tenant; weekly summary email; bounce tracking.
- Multiple company-admin users with RBAC roles (owner/admin/viewer).
- Arabic UI (i18n scaffolding present from MVP; full translation in v1).
- Field-level low-confidence highlighting in the review UI.

**Could-have (v1.1)**
- Virus/malware scanning step in the upload pipeline (ClamAV local / Defender on Azure).
- REST API keys for tenant programmatic export.
- Certificate "expiring soon" analytics + re-collection campaigns.
- Custom sender domain per tenant.

**Future (v2)**
- ERP integration, webhooks, FTA verification API, multi-country (KSA ZATCA etc.), native mobile, advanced approval workflow, billing/subscription management, dedicated per-client deployments.

## 24. Recommended Next Steps

1. **Resolve OQ1–OQ8** with the client (especially OQ1 group-data definition and OQ4 OCR residency) — capture answers in `/observations/02-clarifications.md`.
2. **Sprint 0** (see [10-backlog-sprints.md](10-backlog-sprints.md)): monorepo scaffold, Docker Compose skeleton, CI, base FastAPI + Next.js apps, Alembic baseline, RLS migration.
3. Stand up the **storage/OCR/email provider interfaces** with local implementations first (contract tests against both local and Azure impls).
4. Build the **auth + tenancy spine** (companies, admins, RLS, JWT, audit) before any feature work — everything else hangs off it.
5. Implement the **business-customer happy path** (invite → OTP → upload → OCR → review → confirm) as the first vertical slice to validate the whole pipeline early.
