# 02 — Security & Compliance Architecture

Covers output section **8**. Strong baseline, OWASP Top 10-aware, PDPL-aware.

## 8.1 Identities & authentication

Three principal types, two auth mechanisms:

| Principal | Mechanism | Session | Storage |
|-----------|-----------|---------|---------|
| Platform Admin (BBI) | Email + password (Argon2id) + **mandatory TOTP MFA** | JWT access (15 min) + refresh (7 d, rotating) in httpOnly cookies | `platform_admins` |
| Company Admin | Email + password (Argon2id), optional TOTP | Same JWT scheme, claims carry `company_id` + role | `company_admins` |
| Business Customer | Invitation token → email → **OTP** (no password) | Short-lived bearer session (30–60 min) scoped to `invitation_id` + `company_id` | none persistent (NFR-008) |

- **Password hashing:** Argon2id (`argon2-cffi`), per-password salt, tuned params (e.g. t=3, m=64MB, p=2). No plaintext, ever.
- **JWT:** asymmetric (RS256) signing; private key in Key Vault. Claims: `sub`, `principal_type`, `company_id` (null for platform), `role`, `jti`, `exp`. Refresh rotation with reuse detection (revoke family on reuse).
- **Cookies:** `HttpOnly`, `Secure`, `SameSite=Strict` (admin) / `Lax` (customer portal cross-link), set by the Next.js BFF so tokens never touch client JS.

### OTP flow (business customer) — exact rules
1. Customer opens invitation link `/{slug}/invite/{token}`. Token is opaque (32-byte random, stored hashed) + bound to the invitation; expires per invitation policy.
2. Customer enters email → must match the invitation's target email (case-insensitive) → else generic "if this email matches, an OTP was sent" (no enumeration).
3. Generate 6-digit OTP, store **only** `hmac_sha256(otp, server_pepper)` in `otp_challenges` with `expires_at = now + 10 min`. Pepper from Key Vault.
4. Email OTP via notification service.
5. Verify: constant-time compare of HMAC. Track `attempts`. **Max 3** → on 3rd failure set `locked_until = now + 30 min`. Rate-limit per email + per IP in Redis (atomic INCR + TTL).
6. On success: issue customer session, mark invitation `AUTHENTICATED`, invalidate the OTP, audit `OTP_VERIFIED`.

## 8.2 Authorization & RBAC

Roles and the permission matrix (enforced server-side via a `require(permission)` dependency; never trust the client):

| Role | Scope | Key permissions |
|------|-------|-----------------|
| `PLATFORM_OWNER` / `PLATFORM_ADMIN` | global | manage companies, subscriptions, OCR config, view ops health; **no** access to tenant certificate PII by default (break-glass + audited) |
| `COMPANY_OWNER` | one tenant | everything in tenant incl. manage admins, branding, exports |
| `COMPANY_ADMIN` | one tenant | customers, invitations, reminders, dashboard, view records, export |
| `COMPANY_VIEWER` | one tenant | read-only dashboard + records, no export, no invite |
| `BUSINESS_CUSTOMER` | one invitation | upload/review/confirm own submissions only |

- Permission checks are **deny-by-default**. Every endpoint declares required permission + scope.
- Platform Admin accessing tenant PII is a **break-glass** action: extra confirmation, always audited with reason.

## 8.3 Tenant isolation (defence in depth)

1. **Claim-bound context:** middleware extracts `company_id` from the validated JWT/customer-session and stores it in a request-scoped context var.
2. **Repository guard:** `TenantRepository` base auto-applies `WHERE company_id = :ctx_company_id` on every read/write of tenant-scoped tables; raises if context is missing. Cross-tenant access requires an explicit, audited platform-admin path.
3. **PostgreSQL RLS:** each tenant table has an RLS policy `USING (company_id = current_setting('app.current_company_id')::uuid)`. The API issues `SET LOCAL app.current_company_id = :id` per transaction. Even a SQL-injection or ORM bug cannot cross tenants. Platform role uses a `BYPASSRLS`-capable role only on explicit admin queries.
4. **Storage isolation:** object keys are tenant-prefixed; signed URLs minted only after the repository-level authz check passes.

## 8.4 File upload security

Pipeline (all server-side, before/around storage write):
1. **Size:** reject > 10 MB (enforced at proxy *and* app).
2. **MIME + magic bytes:** must be `application/pdf` by header *and* by content sniff (`%PDF-` magic); reject mismatches.
3. **Filename:** never trust client name; generate `uuid4().pdf` as the storage object; store original name as metadata only, sanitized.
4. **Hash:** compute SHA-256; store on `certificate_files`; used for dedupe + integrity + tamper-evidence.
5. **PDF sanity:** parse with PyMuPDF; reject encrypted/corrupt/JS-laden PDFs; cap page count.
6. **Malware scan (v1.1):** queue ClamAV (local) / Defender (Azure) scan; submission stays `QUARANTINED` until clean. MVP: design the status + hook, implementation deferred.
7. **No execution, no inline rendering of untrusted HTML.** PDFs served with `Content-Disposition: attachment` or sandboxed viewer; correct `Content-Type`.

**File access control:** downloads never use public URLs. Client requests `GET /submissions/{id}/file` → API authorizes (tenant + role / owning customer) → mints a 5-minute signed URL → 302 / returns URL. Signed URL is single-tenant-scoped key, short TTL, audited (`RECORD_DOWNLOADED`).

## 8.5 OWASP Top 10 mitigations (mapping)

| OWASP (2021) | Mitigation here |
|--------------|-----------------|
| A01 Broken Access Control | Deny-by-default RBAC, RLS, repository tenant guard, server-side checks only |
| A02 Cryptographic Failures | TLS 1.2+ everywhere; AES-256 at rest (Blob/Postgres TDE); Argon2id; OTP hashed+peppered; keys in Key Vault |
| A03 Injection | SQLAlchemy parameterized queries; Pydantic validation; no string-built SQL; output encoding in React |
| A04 Insecure Design | Threat-modelled flows (OTP, upload, multi-tenant); rate limits designed in |
| A05 Security Misconfig | Hardened headers (CSP, HSTS, X-Content-Type-Options, frame-ancestors), minimal images, no debug in prod |
| A06 Vulnerable Components | Pinned deps, Dependabot/`pip-audit`/`npm audit` in CI, base image scanning |
| A07 Auth Failures | Lockout, rate limiting, MFA for platform admin, rotating refresh w/ reuse detection, no user enumeration |
| A08 Integrity Failures | Signed images, SBOM, CI provenance; file SHA-256; refresh-token reuse detection |
| A09 Logging/Monitoring Failures | Structured audit log + App Insights alerts on auth anomalies, OTP lockouts, OCR failures |
| A10 SSRF | OCR/email providers call fixed allow-listed endpoints; no user-supplied URLs fetched server-side |

## 8.6 Rate limiting

Redis-backed sliding window / token bucket on:
- OTP request: per email (e.g. 5/hour) + per IP.
- OTP verify: 3 attempts → 30-min lockout (FR-010).
- Admin login: per account + per IP, exponential backoff.
- Upload: per customer session.
- Export: per admin (prevents data-exfil bursts).
Abstracted behind `RateLimiter`; 429 with `Retry-After`.

## 8.7 CORS / CSRF / headers

- **CORS:** allow-list the known frontend origins (tenant domains/subdomains) only; credentials true; no `*`.
- **CSRF:** cookie-based admin sessions use double-submit token or `SameSite=Strict` + custom header check on state-changing requests routed through the BFF.
- **Security headers:** strict CSP (no inline scripts; nonce-based), HSTS, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, `frame-ancestors 'none'`.

## 8.8 Secret management

- **Local:** `.env` (git-ignored), `.env.example` committed with placeholder keys.
- **Azure:** Key Vault; ACA pulls secrets via managed identity + Key Vault secret references. Rotation supported. Secrets: DB DSN, JWT private key, OTP pepper, provider API keys, storage creds.
- No secrets in code, logs, images, or git history (gitleaks in CI).

## 8.9 Logging without leaking sensitive data

- Structured JSON logs; **never** log OTP codes, passwords, JWTs, full TRN/TIN in plain app logs (mask to last 4), or full PII.
- Correlation IDs per request; tenant + actor IDs (not names) for traceability.
- Audit log (business-level, in DB) is distinct from app/diagnostic logs (App Insights). PII in the audit log is access-controlled.

## 8.10 Data encryption, backup, retention

- **In transit:** TLS 1.2+ (Front Door / Traefik). Internal ACA traffic over the platform network.
- **At rest:** Postgres + Blob encrypted (AES-256, platform-managed keys MVP; CMK in Key Vault optional).
- **Backups:** Postgres automated daily + PITR, **30-day retention** (NFR-013); Blob soft-delete + versioning; documented restore runbook.
- **Retention (PDPL):** default 24-month data retention (OQ6, configurable per tenant); scheduled purge job; soft-delete then hard-purge.

## 8.11 Compliance (PDPL)

- **UAE data residency:** all storage + compute in UAE North; OCR in-region per OQ4.
- **Data subject rights:** export (already built), correction (customer review/edit + admin edit), deletion/anonymization request workflow (anonymize PII, retain audit metadata).
- **Lawful processing & audit:** every access to PII audited (actor, action, entity, time, IP, UA).
- **Breach posture:** monitoring + alerting; documented incident response in production-readiness checklist.

## 8.12 Security review checklist (gate before each release)

- [ ] All new endpoints declare required permission + tenant scope; deny-by-default verified.
- [ ] No new query bypasses the tenant repository / RLS.
- [ ] No secrets/PII in logs (grep + reviewer check); gitleaks clean.
- [ ] Input validated by Pydantic; file uploads pass MIME/size/hash/PDF-sanity.
- [ ] Rate limits applied to new auth/OTP/export paths.
- [ ] Dependencies scanned (`pip-audit`, `npm audit`), images scanned.
- [ ] Security headers present on new routes; CORS allow-list unchanged or reviewed.
- [ ] New sensitive actions emit audit events.
- [ ] AuthZ tested with cross-tenant negative tests.
