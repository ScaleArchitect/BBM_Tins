# TIN Collection Portal — Initial Analysis

**Source documents:** `BRD_TIN_Portal v02.pdf` (BRD v0.2), `TIN_Portal_Process_Flows v01.pdf` (Process Flows, based on BRD v0.2)
**Date:** 2026-06-01
**Status:** Initial review — pre-build
**Author:** Mounir Melaine

---

## 1. Product summary

A **white-label, multi-tenant B2B SaaS** that lets a subscribing UAE company collect FTA tax certificates (VAT + Corporate Tax) from its vendors/customers/partners.

**Actors:**
- **Platform Admin (BBI)** — onboards companies, manages subscriptions, monitors platform, maintains OCR engine.
- **Company Admin (tenant)** — configures branding, uploads customer lists, sends invitations, monitors dashboard, exports data.
- **Business Customer (uploader)** — receives invite, authenticates via OTP, uploads certificate PDFs, reviews/corrects extracted data, confirms.

**Core pipeline:** branded invite → OTP auth → PDF upload → OCR extraction → TIN derivation → validation → review/correct → store → dashboard/export.

The concept is coherent; process flows align well with the functional requirements; the data model is reasonably complete.

---

## 2. Contradictions & document defects

Concrete errors in the BRD that will cause downstream confusion:

| # | Issue | Detail | Action |
|---|-------|--------|--------|
| D1 | **Duplicate requirement IDs** | `FR-028` is used twice — "reject Group VAT Certificate" (§6.4) and "automated reminder emails" (§6.5). Everything after §6.4 is mis-numbered. | Re-sequence all FR IDs cleanly. |
| D2 | **FR-013 vs FR-014 overlap** | FR-013 = "upload VAT / Corp Tax cert" (conflates both); FR-014 = "upload Corporate Tax cert" (duplicates CT). | FR-013 = VAT only; FR-014 = Corporate Tax only. |
| D3 | **Data residency contradiction** | NFR-006 requires "data hosted in UAE", but §11 lists **"AWS ME Bahrain"** as acceptable. Bahrain ≠ UAE — fails strict UAE residency. | Compliant options: **Azure UAE North**, Oracle UAE, or local provider. Decide early (cascades to OCR choice). |
| D4 | **"Verified" status with no verifier** | Data model `Status` enum includes `verified` and FR-027 references verification, but the approval/review workflow is **out of scope for v1**. Nothing in v1 can set `verified`. | Drop `verified` from v1, or define who/what sets it. |

---

## 3. Underspecified requirements (biggest risks)

| # | Item | Gap | Why it matters |
|---|------|-----|----------------|
| U1 | **Data integrity check vs. "group data"** | "Group data" is never defined. Whose data — the Company Admin's master vendor list? Pre-known TRN/legal-name per invitee? | A **Must** validation with no specification. Single biggest open question. |
| U2 | **Group VAT certificate detection (FR-028)** | No rule for *how* OCR distinguishes a group certificate from standalone. | Needs a concrete heuristic (e.g., "Tax Group"/member-list field present, specific title text). |
| U3 | **TIN derivation rule** | "TIN = first 10 digits of 15-digit TRN" with format `100-XXXX-XXXX-XXX-X` needs unambiguous definition (strip separators, then take 10). | Central to the whole product. Confirm this matches actual FTA TRN↔TIN relationship. |
| U4 | **Certificate expiry / re-collection** | Status `expired` and "certificates expiring soon" (FR-027) imply lifecycle mgmt, but no expiry rule, re-collection cadence, or data retention (only 30-day *backup* retention). | PDPL requires a defined retention/deletion policy for personal data. |
| U5 | **Company/Platform Admin authentication** | Business customers are OTP-only (NFR-008), but admin auth (password? SSO? MFA?) is unspecified. | Required for security design. |

---

## 4. Technical considerations

- **Arabic OCR is the key accuracy risk.** Extracting Arabic legal names (RTL) at the claimed 95%+ is optimistic for scanned/low-quality PDFs. Mitigation: surface per-field confidence scores and flag low-confidence fields for user review (FR-017/018 already supports this).
- **OCR engine ↔ data residency coupling.** If data must stay in UAE, the OCR vendor must process in-region. **Azure AI Document Intelligence (UAE North)** is the cleanest fit; AWS Textract / Google Document AI may lack a UAE region, forcing certificate data out of the country during processing.
- **Multi-tenancy + per-tenant subdomains.** White-label subdomains (`companyname.taxportal.ae`) require automated DNS + TLS provisioning and strict tenant isolation. Decide row-level vs schema/db-per-tenant up front.
- **Email deliverability & OTP security.** OTP-by-email is the weakest link for both security and deliverability. Essential: reputable provider, SPF/DKIM/DMARC, optional per-tenant custom sender domain.
- **Async OCR.** NFR-002 (30s/cert) + concurrency targets (NFR-003) imply a queue-based extraction pipeline, not synchronous request handling.

---

## 5. What's solid

- Clear scope boundaries (v1 vs future).
- Well-defined actor model and both user journeys.
- NFRs cover the right categories (security, residency, PDPL, audit, i18n).
- Risks/mitigations sensibly identified.

---

## 6. Recommended next steps

1. **Tighten the BRD** — produce a client clarification list resolving U1–U5 and D1–D4; issue a corrected requirements table with fixed IDs.
2. **Architecture & tech-stack proposal** — concrete v1 architecture (hosting, OCR, multi-tenancy, auth) with the residency decision made (D3).
3. **Data model / schema** — formalize entities into a relational schema.
4. **Scaffold the project** — once stack decisions are made.
