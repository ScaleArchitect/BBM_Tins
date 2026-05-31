# Clarification Register & Decision Log

**Project:** TIN Collection Portal
**Date:** 2026-06-01
**Status:** Open — awaiting client decisions
**Related:** [docs/architecture/00-index.md](../docs/architecture/00-index.md) (§3 Open Questions, §Exec Summary), [observations/01-brd-initial-analysis.md](01-brd-initial-analysis.md)

This document tracks the open questions (OQ1–OQ8) that need client confirmation, and records the key architecture decisions already made. Each open question has a **safe default** so development is **not blocked** — but a different answer is a contained change because each is isolated behind a service/config boundary.

**Blocking legend:**
- 🟢 **Not blocking** — default is safe; can change any time pre-GA with low cost.
- 🟡 **MVP** — should be confirmed before the relevant MVP sprint (changing later = rework within that module).
- 🔴 **Production** — must be confirmed before production readiness / go-live.
- ⚪ **Sprint 0** — affects foundational scaffolding; confirm before/at Sprint 0.

No question blocks **Sprint 0** scaffolding (all carry safe defaults that the abstractions absorb).

---

## Open Questions

### OQ1 — Definition of "group / company data" for the integrity check
- **Question:** What exactly is the "company group data" the BRD requires confirmed submissions to be validated against? Which fields are authoritative (legal name? TRN? trade licence?), and is a mismatch a **hard block** or a **soft flag**?
- **Why it matters:** It is a BRD **Must** validation that is currently undefined. It shapes the `business_customers` master-data columns (`expected_trn`, `expected_legal_name`, `expected_trade_license`) and the `validation/integrity.py` rules.
- **Current safe default:** Soft-flag only. Compare confirmed legal name + TRN against the expected values on the customer record; a mismatch raises a `*_MISMATCH` warning flag and surfaces in the `flagged` dashboard bucket, but **never blocks** submission.
- **Recommended client decision:** Confirm the authoritative field set and keep it a **soft flag** for MVP (hard-blocking risks stranding legitimate vendors on data-entry differences). Revisit hard-block in a later approval-workflow phase.
- **Impact if default changes later:** Low–Medium. Logic is isolated in `integrity.py`; switching to hard-block adds a status transition guard and a new submission state. Adding authoritative fields means a migration + import-mapping change.
- **Blocks:** 🟡 MVP (confirm before **Sprint 6 — OCR & Validation**).

### OQ2 — Group VAT certificate detection & policy (FR-028)
- **Question:** How is a "Group VAT certificate" reliably distinguished from a standalone one, and should it be **rejected outright** or **warned-and-allowed**?
- **Why it matters:** FR-028 is a **Must**. The detection heuristic drives a hard rejection path (`409 GROUP_CERT_REJECTED`) and the standalone-cert pop-up.
- **Current safe default:** Detect via presence of a tax-group / member-entity section or title keywords; policy = **REJECT** (`company_settings.group_cert_policy = REJECT`), matching BRD wording. A per-tenant `WARN` option exists.
- **Recommended client decision:** Provide 2–3 sample group certificates so the detection heuristic can be tuned; confirm REJECT as the default policy.
- **Impact if default changes later:** Low. Policy is a per-tenant setting; the heuristic lives in `validation/group_cert.py` and can be refined without pipeline changes.
- **Blocks:** 🟡 MVP (confirm before **Sprint 6**; sample certs needed for the OCR accuracy harness).

### OQ3 — TIN derivation rule
- **Question:** Confirm TIN = first 10 digits of the **normalized** 15-digit TRN. Does the **Corporate Tax** TIN follow the same rule, or is it N/A (the BRD says "if applicable by rule")?
- **Why it matters:** The TIN is the product's core data element. The rule is central and must be unambiguous.
- **Current safe default:** `normalize_trn` strips non-digits → `derive_tin` takes the first 10 of the 15. Same rule applied to both VAT and CT; `tin` is nullable on CT if the client states it does not apply.
- **Recommended client decision:** Confirm the digit-slice rule and the CT applicability explicitly (ideally referencing FTA guidance).
- **Impact if default changes later:** Low. One pure function (`validation/tin.py`) + its unit fixtures; a backfill migration if already-stored TINs need recomputation.
- **Blocks:** 🟡 MVP (confirm before **Sprint 6**).

### OQ4 — Azure AI Document Intelligence region / OCR data residency
- **Question:** If Document Intelligence is **not available in UAE North**, is it acceptable to process certificate data in a nearby Azure region, or must OCR stay **in-country**?
- **Why it matters:** Certificates contain PII subject to UAE data-residency (NFR-006) and PDPL. Sending them to an out-of-region OCR service may breach residency.
- **Current safe default:** Keep OCR **in-region**. If Document Intelligence is unavailable in UAE North, run the self-hosted OCR worker (PyMuPDF/Tesseract/Paddle) in UAE North rather than ship data abroad. Cloud OCR is treated as an enhancement, not a dependency.
- **Recommended client decision:** Confirm strict in-country processing (recommended). If an exception is acceptable, obtain it in writing with the specific region named.
- **Impact if default changes later:** Medium. Affects only the OCR provider selection + accuracy tuning; the abstraction means the rest of the system is unaffected. Decision must be settled **before** the Azure OCR provider is wired.
- **Blocks:** 🔴 Production (must be resolved before **Sprint 12 — Azure deployment**). Not blocking locally.

### OQ5 — Certificate expiry & re-collection cadence
- **Question:** Is there an expiry date to capture from certificates, and a policy for re-requesting certificates periodically?
- **Why it matters:** The data model reserves an `EXPIRED` status and FR-027 references "certificates expiring soon"; without a rule these are unused.
- **Current safe default:** No hard expiry in MVP; `EXPIRED` reserved/unused; no automated re-collection. "Expiring soon" analytics deferred to v1.1.
- **Recommended client decision:** Confirm whether VAT/CT certificates carry an actionable expiry and whether periodic re-collection campaigns are required (likely v1.1).
- **Impact if default changes later:** Low–Medium. Adds an `expiry_date` field, a status transition, and a reminder campaign type — additive, no rework.
- **Blocks:** 🟢 Not blocking (v1.1 feature).

### OQ6 — Data retention period & PDPL deletion rights
- **Question:** What is the default data-retention period, and on a deletion request should data be **hard-deleted** or **anonymized** (retaining audit metadata)?
- **Why it matters:** PDPL compliance requires a defined retention/deletion policy; it drives the nightly purge job and the deletion workflow.
- **Current safe default:** 24-month retention (per-tenant configurable via `company_settings.retention_months`); soft-delete then scheduled hard-purge; deletion requests **anonymize PII** but preserve audit action records (who/what/when).
- **Recommended client decision:** Confirm the retention period (legal/tax record-keeping obligations may mandate a minimum) and the anonymize-vs-hard-delete stance.
- **Impact if default changes later:** Low. Retention is a config value; the purge/anonymization jobs already exist. A longer legal minimum is just a config change.
- **Blocks:** 🔴 Production (confirm before **Sprint 11 — hardening / retention**; legal sign-off before go-live).

### OQ7 — Admin authentication model
- **Question:** For MVP, is local password (Argon2) + JWT sufficient for company/platform admins, or is **Azure AD / SSO (OIDC)** required at launch?
- **Why it matters:** Determines the auth implementation and onboarding flow for admins.
- **Current safe default:** Local Argon2id + JWT (refresh rotation, httpOnly cookies) for MVP; mandatory TOTP MFA for platform admins. Auth is structured so a pluggable **OIDC** provider can be added later.
- **Recommended client decision:** Confirm local auth for MVP; flag if any enterprise tenant will require SSO at launch (would pull OIDC forward).
- **Impact if default changes later:** Medium. Adding OIDC is additive (new auth path), but if required at launch it must be planned into Sprint 2 rather than later.
- **Blocks:** 🟡 MVP (confirm before **Sprint 2 — Authentication**).

### OQ8 — Certificate cardinality per customer
- **Question:** Can one business customer submit **multiple** VAT and/or CT certificates (e.g. several trade licences), or strictly **one of each type**?
- **Why it matters:** Determines submission cardinality, duplicate handling, and what the dashboard treats as the "current" record.
- **Current safe default:** Allow **many** submissions per customer per type; the latest confirmed submission per type is the "current" record; duplicates (same TRN/TIN) are flagged, not blocked.
- **Recommended client decision:** Confirm multiple-certificate support (recommended — multi-licence entities are common in the UAE).
- **Impact if default changes later:** Low. The schema already supports 1:N; restricting to one-of-each would add a constraint, not a redesign.
- **Blocks:** 🟢 Not blocking (default is the more flexible superset).

---

## Open Questions — summary

| OQ | Topic | Default stance | Blocks | Confirm by |
|----|-------|----------------|--------|-----------|
| OQ1 | "Group data" integrity check | Soft flag | 🟡 MVP | Sprint 6 |
| OQ2 | Group VAT cert detection/policy | Detect + REJECT | 🟡 MVP | Sprint 6 (+ samples) |
| OQ3 | TIN derivation rule | Normalize → first 10; same for CT | 🟡 MVP | Sprint 6 |
| OQ4 | OCR data residency | In-region only | 🔴 Production | Sprint 12 |
| OQ5 | Certificate expiry / re-collection | None in MVP | 🟢 Not blocking | v1.1 |
| OQ6 | Retention & deletion rights | 24mo, anonymize | 🔴 Production | Sprint 11 + legal |
| OQ7 | Admin auth model | Local Argon2+JWT | 🟡 MVP | Sprint 2 |
| OQ8 | Certs per customer | Many per type | 🟢 Not blocking | — |

---

## Decision Log (architecture decisions already made)

These are settled and reflected in the architecture documents. Listed here as the authoritative record.

| ID | Decision | Rationale | Reference |
|----|----------|-----------|-----------|
| DL-01 | **Controlled multi-tenant from day one** (not single-tenant-per-deployment) | Retrofitting tenancy is expensive; isolation cost is low if built in early; clean SaaS path | [00-index §1](../docs/architecture/00-index.md), [01 §4.4](../docs/architecture/01-architecture-overview.md) |
| DL-02 | **Shared PostgreSQL DB** with mandatory `company_id`, **Postgres RLS**, and **repository-level tenant guard** (triple-layer isolation) | Defence in depth — even an ORM/SQL bug cannot cross tenants | [02 §8.3](../docs/architecture/02-security-compliance.md), [03](../docs/architecture/03-data-model.md), [06 §13.4](../docs/architecture/06-backend-structure.md) |
| DL-03 | **Modular monolith** (not microservices) | Clean domain separation inside one deployable; avoids premature distributed complexity | [01 §4.2](../docs/architecture/01-architecture-overview.md) |
| DL-04 | **FastAPI** backend (Python, SQLAlchemy 2.0, Alembic, Pydantic v2) | Async-native, OpenAPI, strong typing; matches stack mandate | [06](../docs/architecture/06-backend-structure.md) |
| DL-05 | **Next.js** frontend (TypeScript, Tailwind, App Router, i18n en/ar) | SSR/BFF, white-label theming, RTL-ready; no business logic in client | [05](../docs/architecture/05-frontend-design.md) |
| DL-06 | **Arq** for async jobs (not Celery) | Asyncio-native, low ceremony, fits FastAPI; behind a `TaskQueue` interface | [01 §4.2](../docs/architecture/01-architecture-overview.md), [06 §13.6](../docs/architecture/06-backend-structure.md) |
| DL-07 | **Worker uses the same image as the API** (different entrypoint) | Guarantees shared models/schemas/services — no drift | [01 §4.2](../docs/architecture/01-architecture-overview.md), [09 §18.2](../docs/architecture/09-devops-deployment.md) |
| DL-08 | **Object storage for PDFs** (MinIO/Blob), never in the database; metadata + SHA-256 in DB | Keeps DB lean; signed-URL access; matches anti-pattern guidance | [01 §7.6](../docs/architecture/01-architecture-overview.md), [02 §8.4](../docs/architecture/02-security-compliance.md) |
| DL-09 | **OCR always asynchronous** (never in the upload request) | Meets NFR-002; resilient; retryable | [01 §4.3](../docs/architecture/01-architecture-overview.md), [07](../docs/architecture/07-ocr-design.md) |
| DL-10 | **Provider abstractions for storage, OCR, email, and queue** (Protocol + factory, selected by env) | Same codebase local↔Azure; no vendor lock-in in domain logic; mockable | [01 §7](../docs/architecture/01-architecture-overview.md), [06 §13.5](../docs/architecture/06-backend-structure.md) |
| DL-11 | **Local Docker Compose first, Azure Container Apps later** (no Kubernetes for MVP) | Scale-to-N without K8s ops overhead; identical images promoted | [01 §5–6](../docs/architecture/01-architecture-overview.md), [09](../docs/architecture/09-devops-deployment.md) |
| DL-12 | **Raw OCR, extracted, and customer-confirmed values stored separately** | Auditability; nothing silently overwritten; searchable columns derived on confirm | [03 §9.2](../docs/architecture/03-data-model.md), [07 §14.8](../docs/architecture/07-ocr-design.md) |
| DL-13 | **OTP & passwords never plaintext** — OTP HMAC-SHA256+pepper, passwords Argon2id | Security baseline / NFR-008 | [02 §8.1](../docs/architecture/02-security-compliance.md) |
| DL-14 | **UAE North** target region; backups/GRS paired to UAE Central | Data residency / PDPL | [01 §6](../docs/architecture/01-architecture-overview.md), [09 §18.4](../docs/architecture/09-devops-deployment.md) |

---

## How to use this register
- Take OQ1–OQ8 to the client; record answers inline under each question (date + who decided).
- When an answer differs from the default, update the affected architecture doc and add a new **DL-xx** row here.
- Re-confirm 🔴 items are closed before the Production Readiness gate ([11 §22](../docs/architecture/11-standards-testing-readiness.md)).
