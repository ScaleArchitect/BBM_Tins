# Sprint 2 — Fixed Technical Debt

**Sprint:** 2 (Authentication, RBAC, Company Management)
**Date addressed:** 2026-06-03
**Verification:** Backend unit suite green (21/21 passing)
This document records technical-debt items identified during the Sprint 2 code
review that have been **resolved**. Items still outstanding are tracked in
[Open_Tech_Debt.md](../Open_Tech_Debt.md).

---

## Security / correctness

### TD-S2-01 — RLS GUC built via f-string (SQLi-shaped pattern) — FIXED
- **Severity:** Medium
- **Location:** `backend/app/core/db.py` (`set_current_company`)
- **Problem:** The tenant RLS binding rendered the company id into SQL with an
  f-string (`SET LOCAL app.current_company_id = '{company_id}'`). The value was a
  trusted `UUID`, so it was not exploitable, but the pattern is injection-shaped
  and could be weaponized by a future refactor passing a raw string.
- **Fix:** Switched to a bound parameter via
  `SELECT set_config('app.current_company_id', :company_id, true)`.

### TD-S2-02 — `/me` silently returned an empty email — FIXED
- **Severity:** Low/Medium
- **Location:** `backend/app/domains/auth/router.py` (`/auth/me`)
- **Problem:** A valid JWT for a deleted/disabled account returned `200` with a
  blank email instead of an auth error.
- **Fix:** `/me` now raises `401 Unauthorized` when the backing account no longer
  exists.

### TD-S2-03 — `/auth/refresh` was not rate-limited — FIXED
- **Severity:** Low (defence-in-depth)
- **Location:** `backend/app/domains/auth/router.py` (`/auth/refresh`),
  `backend/app/core/config.py`
- **Problem:** Only `/auth/login` was throttled; the refresh endpoint had no
  abuse limit.
- **Fix:** Added a per-client-IP fixed-window rate limit
  (`refresh_max_per_window` / `refresh_window_seconds`, default 60/60s) returning
  `429 Too Many Requests` with a `Retry-After` header.

### TD-S2-04 — TOTP login failures were not audited — FIXED
- **Severity:** Low
- **Location:** `backend/app/domains/auth/service.py` (`login`)
- **Problem:** A failed TOTP check called `throttle.record_failure` directly,
  bypassing the audited failure path used for password failures, so TOTP
  failures were not written to the audit log.
- **Fix:** Routed TOTP failures through the shared `_record_failure` helper so
  they are throttled **and** audited consistently.

---

## Maintainability

### TD-S2-05 — Router reached into private service internals — FIXED
- **Severity:** Low
- **Location:** `backend/app/domains/auth/router.py`,
  `backend/app/domains/auth/service.py`
- **Problem:** `/me` and `/totp/enroll` called `service._load_account(...)` with
  `# noqa: SLF001`, accessing a private function across module boundaries.
- **Fix:** Promoted `_load_account` to the public `load_account` and removed the
  `noqa` suppressions.

### TD-S2-06 — `count_active_owners` counted rows in Python — FIXED
- **Severity:** Low
- **Location:** `backend/app/domains/admins/repository.py`
- **Problem:** The last-owner guard loaded every owner row and summed them in
  application code (unbounded fetch) on every owner update.
- **Fix:** Replaced with a SQL `SELECT COUNT(...)` that excludes the target id,
  matching the existing pattern in `platform/repository.py`.

### TD-S2-07 — Invite-send errors were swallowed silently — FIXED
- **Severity:** Low
- **Location:** `backend/app/domains/platform/service.py`,
  `backend/app/domains/admins/service.py`
- **Problem:** A broad `except Exception` collapsed email-send failures to a
  `bool` with no record of the underlying SMTP cause.
- **Fix:** Both paths now log a structured warning (`company_invite_send_failed` /
  `admin_invite_send_failed`) with `exc_info` before returning `False`. The
  audit log still records `invite_sent: false`.

---

## Documentation drift

### TD-S2-08 — Sprint docs described behavior that did not exist — FIXED
- **Severity:** Low (doc accuracy)
- **Location:** `Deliverables/sprint-2.md`, `sprint_demos/sprint-2.md`
- **Problems & fixes:**
  - "Exponential backoff (1s/2s/4s)" described, but the throttle is a
    fixed-window counter with a single fixed cooldown → corrected.
  - Status flow documented as `ONBOARDING → ACTIVE → SUSPENDED` and tiers
    `FREE/PRO/ENTERPRISE`; actual enums are `PENDING/ACTIVE/SUSPENDED/CANCELLED`
    and `TRIAL/ACTIVE/PAST_DUE/CANCELLED` → corrected.
  - Suspended-tenant login documented as `HTTP 423` checked *after* password
    verify; actual behavior is `HTTP 403` checked *before* password verify →
    corrected.
  - Typo `compan_id` → `company_id` fixed.

---

## Second pass — previously-open items now resolved

These items were originally logged in `Open_Tech_Debt.md` (OTD-01..04) and have
since been fixed.

### TD-S2-09 — CSRF protection for state-changing requests (was OTD-01) — FIXED
- **Severity:** Medium
- **Location:** `frontend/app/api/proxy/[...path]/route.ts`,
  `frontend/lib/server/backend.ts`, `frontend/lib/bff.ts`,
  `frontend/app/api/auth/login/route.ts`, `frontend/app/api/auth/logout/route.ts`
- **Problem:** Tokens live in `httpOnly` cookies and the BFF proxy auto-attaches
  the access token to forwarded `POST/PUT/PATCH/DELETE` calls. `sameSite=lax`
  blocks cross-site top-level POSTs but provides no CSRF token for programmatic
  state-changing requests.
- **Fix:** Implemented the **double-submit cookie** pattern, contained to the BFF
  (the backend uses bearer tokens and needs no change):
  - A readable (non-`httpOnly`) `tin_csrf` cookie (`csrfCookieOptions` /
    `newCsrfToken` in `backend.ts`) is bootstrapped by the proxy on first contact
    and set on login.
  - The proxy rejects unsafe methods (`!GET/HEAD/OPTIONS`) with `403` unless the
    `x-csrf-token` header matches the `tin_csrf` cookie. The `/auth/*` credential
    endpoints are exempt (no token exists at login; guarded by credentials).
  - The client (`bffFetch`) reads `tin_csrf` from `document.cookie` and echoes it
    in the `x-csrf-token` header for unsafe methods.
- **Verification:** Frontend typecheck green (`tsc --noEmit`).

### TD-S2-10 — TOTP secret was client-supplied on verify (was OTD-02) — FIXED
- **Severity:** Low/Medium
- **Location:** `backend/app/domains/auth/service.py` (`totp_enroll` /
  `totp_verify`), `backend/app/domains/auth/schemas.py`,
  `backend/app/domains/auth/router.py`, `backend/app/core/config.py`
- **Problem:** `enroll` returned a fresh secret but persisted nothing; `verify`
  trusted and saved the `secret` from the request body, letting an authenticated
  user enroll an arbitrary known secret.
- **Fix:** The pending secret is now held **server-side in Redis**, keyed by
  principal (`totp:pending:{type}:{id}`) with a TTL
  (`totp_pending_ttl_seconds`, default 600s). `enroll` stores it; `verify` reads
  it back, validates the code, persists to `account.totp_secret`, and deletes the
  pending key. The `secret` field was removed from `TotpVerifyRequest`.
- **Verification:** Backend unit suite green (21/21).

### TD-S2-11 — Integration tests not run in CI (was OTD-03) — FIXED
- **Severity:** Medium
- **Location:** `.github/workflows/ci.yml`
- **Problem:** The end-to-end auth/RLS/refresh integration tests skip without a
  reachable database, so they never ran in CI — only the 21 unit tests executed.
- **Fix:** Added an `integration` CI job with `postgres:16` and `redis:7` service
  containers. It runs `alembic upgrade head` (which creates the `tin_app` RLS
  role) as the owner, then `pytest tests/integration` with
  `TEST_APP_DATABASE_URL` / `DATABASE_ADMIN_URL` / `REDIS_URL` pointing at the
  services. `docker-build` now also gates on this job.
- **Note:** Authored against the integration harness contract; runs in GitHub
  Actions (not locally verifiable without Docker).

### TD-S2-12 — Ephemeral JWT keypair invalidated tokens on restart (was OTD-04) — FIXED
- **Severity:** Low
- **Location:** `backend/app/core/security.py` (`_keypair`)
- **Problem:** With key files absent (local/dev), a fresh RSA keypair was
  generated per process, so every restart invalidated all issued access tokens.
- **Fix:** When PEM paths are absent, the dev keypair is now persisted to a
  stable per-machine location under the system temp dir
  (`tin-portal-dev-jwt/{private,public}.pem`, `chmod 0600` best-effort) and
  reused across restarts; it is generated only if missing. Logs
  `jwt_dev_keypair_reused` / `jwt_dev_keypair_generated`. Production still
  provisions keys from Key Vault via `JWT_*_KEY_PATH`.
- **Verification:** Backend unit suite green (21/21).
</content>
</invoke>
