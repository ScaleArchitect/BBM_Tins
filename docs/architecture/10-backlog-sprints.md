# 10 — Product Backlog & Sprint Plan

Covers output sections **19 (backlog: epics/features/stories)** and **20 (sprint-by-sprint plan)**. MoSCoW scope lives in [00-index.md §19a](00-index.md).

---

## 19. Product Backlog (epics → features → stories)

Format per story: **US-id** — *As a [role] I want [goal] so that [value]*. `Priority` · `AC` (acceptance criteria) · `Tech notes` · `Deps`.

### EPIC A — Platform & Tenant Onboarding
**Feature A1: Company creation & provisioning**
- **US-A1.1** — *As a Platform Admin I want to create a company with name, trade licence, admin email, enabled cert types so the tenant exists.* · Must · AC: company persisted with unique `slug`, status `PENDING`, first-admin invite email sent; duplicate slug rejected. · Tech: `POST /platform/companies`; RLS-exempt root table. · Deps: Auth (B1).
- **US-A1.2** — *...manage subscription/status (activate/suspend)* · Must · AC: status transitions audited; suspended tenant blocks customer portal + admin login. · Deps: A1.1.
- **US-A1.3** — *...monitor platform health (queue depth, OCR stats, errors)* · Should · AC: `/platform/health` returns live metrics. · Deps: workers.

### EPIC B — Authentication & Access
**Feature B1: Admin auth**
- **US-B1.1** — *As a Company Admin I want to log in securely* · Must · AC: Argon2id verify; JWT access+refresh in httpOnly cookies; lockout + rate limit on brute force; audited. · Tech: see [02](02-security-compliance.md).
- **US-B1.2** — *...MFA (TOTP)* · Should (Must for platform admin) · AC: enroll/verify; required for platform role.
- **US-B1.3** — *...manage company admin users & roles* · Should · AC: owner can add/disable admins with role owner/admin/viewer; permissions enforced server-side.

**Feature B2: Customer OTP auth**
- **US-B2.1** — *As a Business Customer I want to open my invitation link and get an OTP by email* · Must · AC: token resolves branding; email must match invitation; OTP emailed; no enumeration. · Deps: D1, notifications (G).
- **US-B2.2** — *...enter OTP to authenticate* · Must · AC: 6-digit, 10-min TTL, 3 attempts → 30-min lockout; hashed+peppered; session scoped to invitation/company; audited.

### EPIC C — Branding & White-label
- **US-C1.1** — *...upload logo, set colours, welcome text* · Must · AC: stored; reflected on customer portal + emails; contrast warning on bad colours.
- **US-C1.2** — *...configure invitation/reminder/confirmation email templates per locale* · Should · AC: tokens validated; falls back to default; preview.

### EPIC D — Business Customer Management
- **US-D1.1** — *...import customers via CSV (name,email,contact[,expected_trn,expected_legal_name,...])* · Must · AC: row-level report (created/updated/skipped/errors); idempotent on email; dupes flagged.
- **US-D1.2** — *...add/edit/archive a customer manually* · Must · AC: validation; archive hides from active list + stops reminders.
- **US-D1.3** — *...send/resend bulk + individual invitations* · Must · AC: branded email; invitation status tracked; resend re-issues token; audited.

### EPIC E — Certificate Upload & Storage
- **US-E1.1** — *As a Business Customer I want to upload a VAT or CT PDF* · Must · AC: PDF-only, ≤10MB, MIME+magic+hash validated; original stored in object storage (not DB); submission `UPLOADED`; OCR enqueued; 202 returned. · Tech: storage abstraction; signed download.
- **US-E1.2** — *...choose which cert type(s) based on company config* · Must · AC: only `enabled_cert_types` offered.
- **US-E1.3** — *(v1.1)* malware scan before processing · Could · AC: `QUARANTINED` until clean; infected → `REJECTED`.

### EPIC F — OCR & Validation
- **US-F1.1** — *...OCR extracts fields asynchronously* · Must · AC: worker produces `ocr_results.raw_json` + parsed `extracted_data` + `field_confidence`; never runs in request; failure → `EXTRACTION_FAILED` + retry/reprocess. · Tech: [07](07-ocr-design.md).
- **US-F1.2** — *...TRN normalized + validated (15 digits) and TIN derived (first 10)* · Must · AC: deterministic; invalid TRN flagged not blocked; unit-tested with fixtures.
- **US-F1.3** — *...duplicate TRN/TIN flagged within tenant* · Should · AC: `DUPLICATE` flag with reference to other submission.
- **US-F1.4** — *...group VAT cert detected & rejected (or warned per policy)* · Must · AC: detection heuristic; REJECT → `409` + standalone modal.
- **US-F1.5** — *...confirmed data validated against master data (soft flag)* · Should · AC: name/TRN mismatch → `*_MISMATCH` warn flag; never blocks.

### EPIC G — Review, Correct, Confirm
- **US-G1.1** — *As a Business Customer I want to review extracted data with low-confidence fields highlighted* · Must · AC: review form seeded from `extracted_data`; amber on `<0.85`; PDF side-by-side.
- **US-G1.2** — *...correct fields and confirm submission* · Must · AC: edits saved to `confirmed_data` (extracted untouched); flags recomputed on save; confirm → `SUBMITTED`, searchable columns populated, confirmation email queued.

### EPIC H — Dashboard, Search, Records
- **US-H1.1** — *...dashboard counts (invited/submitted/pending/overdue/failed/flagged) + upload rate* · Must · AC: accurate per tenant; <2s.
- **US-H1.2** — *...search/filter records (name,email,TRN,TIN,status,date,cert type)* · Must · AC: paginated; indexed; combinable filters.
- **US-H1.3** — *...drill into a record: extracted+confirmed data, PDF, flags, audit history* · Must · AC: signed PDF URL; audit timeline; access audited.

### EPIC I — Notifications & Reminders
- **US-I1.1** — confirmation email on submit · Must.
- **US-I1.2** — automated day-X/2X reminders + overdue flag · Must · AC: per-tenant offsets; stops on submit; idempotent.
- **US-I1.3** — manual bulk reminder to pending · Must.
- **US-I1.4** — weekly summary email to admins · Should.
- **US-I1.5** — bounce/delivery tracking via webhook · Should.

### EPIC J — Export
- **US-J1.1** — *...export filtered/full data to CSV/Excel* · Must · AC: async job → signed URL; full BRD column set; UTF-8/Arabic-safe; request+generate+download audited.

### EPIC K — Audit & Compliance
- **US-K1.1** — all sensitive actions audited with full context · Must · AC: append-only; canonical action list; tenant-readable.
- **US-K1.2** — data retention purge + PDPL deletion/anonymization · Should · AC: per-tenant retention; deletion anonymizes PII, keeps audit.

### EPIC L — Azure Deployment & Prod Readiness
- **US-L1.1** — deploy same images to ACA with Azure providers · Should · AC: Blob/DocIntelligence/ACS/KeyVault wired; UAE North; passes prod-readiness checklist.

---

## 20. Sprint-by-Sprint Plan

Two-week sprints assumed. Each sprint is releasable. Vertical-slice ordering so the core pipeline is exercised early.

### Sprint 0 — Setup & Architecture
- **Goals:** monorepo, CI, Docker Compose skeleton, base apps, decisions locked.
- **Tasks:** repo scaffold (backend/frontend/infra); `docker-compose.yml` (db, redis, minio, mail, api, web, worker); FastAPI app factory + `/health`; Next.js shell; Alembic baseline; provider interface stubs (storage/ocr/email/queue) + local impls; CI (lint/type/test/scan); `.env.example`; seed script.
- **AC:** `docker compose up` serves web+api; migrations run; CI green. **Deliverables:** running skeleton. **Testing:** smoke + provider contract test harness.

### Sprint 1 — Foundation (data + tenancy spine)
- **Goals:** core schema, tenancy/RLS, audit, config.
- **Tasks:** models + migrations for companies, company_admins, audit_logs; `TenantMixin` + `TenantRepository`; RLS policies + `SET LOCAL` plumbing; audit service; structured logging + correlation id + problem+json errors; settings.
- **AC:** cross-tenant query blocked by RLS (negative test passes); audit records persist atomically. **Testing:** RLS isolation tests, repository unit tests.

### Sprint 2 — Authentication & Company Management
- **Goals:** admin auth + platform onboarding + branding.
- **Tasks:** Argon2 + JWT + refresh rotation + cookies via BFF; RBAC `require()`; platform `companies` CRUD + subscription; company admin users/roles; branding + settings; login UI + admin shell.
- **AC:** US-A1.1/2, B1.1/3, C1.1. **Testing:** auth flows, RBAC matrix, lockout/rate-limit.

### Sprint 3 — Customer Import & Invitation
- **Goals:** customer master + invitations (without OTP yet).
- **Tasks:** business_customers model; CSV import (report) + manual CRUD/archive; invitations model + token issue/hash; send/resend; customer list + import UI; notification service skeleton + INVITATION template (SMTP/Mailpit).
- **AC:** US-D1.1/2/3. **Testing:** import edge cases, invitation status transitions, email rendered in Mailpit.

### Sprint 4 — Business Customer Portal & OTP
- **Goals:** branded portal entry + OTP auth.
- **Tasks:** invite link resolve + branding; OTP request/verify (hash+pepper, TTL, attempts, lockout, rate limit); customer session; portal layout/theming; OTP UI (countdown, attempts).
- **AC:** US-B2.1/2. **Testing:** OTP TTL/attempts/lockout, no-enumeration, rate limiting.

### Sprint 5 — PDF Upload & Storage
- **Goals:** secure async upload.
- **Tasks:** submission + certificate_files models; upload endpoint (MIME/magic/size/hash/PDF-sanity); storage put + tenant-prefixed keys; signed download broker; enqueue OCR job (stub worker); dropzone UI + status poll.
- **AC:** US-E1.1/2. **Testing:** file-security cases (oversize, non-PDF, spoofed MIME), signed-URL authz, idempotency.

### Sprint 6 — OCR & Validation
- **Goals:** real local OCR + validation rules.
- **Tasks:** LocalOCRProvider (PyMuPDF + Tesseract eng/ara); parser registry (VAT, CT); ocr_results persistence; TRN normalize/validate, TIN derive, duplicate, group-cert detect, integrity check; flags; status transitions + retry/reprocess.
- **AC:** US-F1.1–F1.5. **Testing:** validation unit tests with real cert fixtures; OCR pipeline integration; failure/retry.

### Sprint 7 — Review / Correct / Confirm
- **Goals:** close the customer happy path.
- **Tasks:** review GET/PATCH/confirm endpoints; recompute flags on save; populate searchable columns + submitted_at on confirm; confirmation email; review UI (confidence highlight, PDF side-by-side, flags, group-cert modal).
- **AC:** US-G1.1/2, US-I1.1. **Testing:** full E2E invite→OTP→upload→OCR→review→confirm; group-cert rejection.

### Sprint 8 — Dashboard & Search/Filter
- **Goals:** admin visibility.
- **Tasks:** dashboard summary aggregation; submissions list with filters + indexes; record drill-down (data tabs + PDF + audit timeline); customer audit view.
- **AC:** US-H1.1/2/3. **Testing:** filter combinations, pagination, <2s perf check.

### Sprint 9 — Export
- **Goals:** auditable data export.
- **Tasks:** exports model + job; CSV/XLSX streaming writer (Arabic-safe); signed download; full BRD column set; audit events; exports UI.
- **AC:** US-J1.1. **Testing:** large-set export, Arabic encoding, audit of request/generate/download.

### Sprint 10 — Reminders & Weekly Summaries
- **Goals:** notification engine.
- **Tasks:** scheduler cron; day-X/2X reminders + overdue flag; manual bulk reminder; weekly summary; reminder idempotency + counters; bounce webhook + status.
- **AC:** US-I1.2/3/4/5. **Testing:** cron logic, stop-on-submit, idempotency, bounce handling.

### Sprint 11 — Audit & Security Hardening
- **Goals:** production-grade security.
- **Tasks:** complete audited-action coverage; security headers/CSP/HSTS; rate-limit sweep; dependency/image scans clean; threat-model review; retention purge + PDPL deletion/anonymization; pen-test fixes; (optional) malware-scan hook.
- **AC:** US-K1.1/2; security checklist passes. **Testing:** security review checklist, abuse/negative tests, retention job.

### Sprint 12 — Azure Deployment & Production Readiness
- **Goals:** go-live on Azure UAE North.
- **Tasks:** Bicep/Terraform for ACA/Postgres/Blob/KV/Redis-or-ServiceBus/DocIntelligence/ACS/FrontDoor+WAF/AppInsights; managed identities + Key Vault refs; Azure provider impls validated by contract tests; CD pipeline + migration job + canary; backups/DR runbook; dashboards/alerts; load test (100/500 concurrency).
- **AC:** US-L1.1; prod-readiness checklist ([11](11-standards-testing-readiness.md)) complete. **Testing:** staging E2E on Azure providers, load/perf (NFR-001/002/003), DR restore drill.

> **Critical path:** S0→S1→S2 (spine) → S4–S7 (customer pipeline vertical slice — highest risk, validate early) → S8/S9 (admin value) → S10/S11 → S12 (Azure). S3 can overlap S2. If timeboxed, the MVP demo target is end of **S8** (full collection loop + dashboard); export/reminders/Azure are v1.
