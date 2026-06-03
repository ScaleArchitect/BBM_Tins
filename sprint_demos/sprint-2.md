# Sprint 2 Demo Run

**Date:** 2026-06-01  
**Scope:** Authentication, RBAC, Company Management  
**Status:** READY (pending Docker verification)

## Demo Flows

### 1. Platform Admin Creates Company

**Actors:** Platform Admin (platform@tinportal.local)

**Flow:**
```
1. Platform admin logs in at /login
   → POST /api/proxy/auth/login
   → Credentials verified via Argon2
   → JWT + refresh token issued
   → Tokens stored in httpOnly cookies
   → Redirected to /admin

2. Platform admin navigates to /admin/companies
   → GET /api/proxy/admin/users (verified as PLATFORM_OWNER)
   → GET /api/proxy/platform/companies (MANAGE_COMPANIES permission)
   → Displays empty company list

3. Clicks "+ Create Company"
   → Form shows with slug field
   → Enters slug: "acme-corp"

4. POST /api/proxy/platform/companies
   → Service creates:
     - Company(slug="acme-corp", status="ONBOARDING")
     - CompanySettings (default reminders, cert types)
     - CompanyBranding (default colors, welcome text)
     - CompanyAdmin (role=COMPANY_OWNER, status=ACTIVE)
     - Sends invite email via SMTP to owner_email@company.com
   → Response: CompanyCreateResult with temporary_password

5. Company appears in list with status ONBOARDING
```

**Expected Outcome:**
✓ Company created with ONBOARDING status
✓ Owner admin seeded with temporary credentials
✓ Invite email sent (visible in Mailpit at localhost:1025)
✓ RBAC: Non-platform admins cannot access this endpoint

---

### 2. Company Owner Logs In & Customizes Branding

**Actors:** Company Owner (acme-admin@acme.com)

**Flow:**
```
1. Owner receives invite email with temporary password
   → Logs in at /login using invite credentials
   → POST /api/proxy/auth/login
   → Email resolution: "acme-admin@acme.com" → CompanyAdmin lookup
   → Company context bound via RLS (set_current_company GUC)
   → JWT issued with company_id claim
   → Redirected to /admin

2. Owner views admin nav (tenant-scoped, not platform)
   → Navigation shows: Dashboard, Branding, Settings, Users
   → (NOT Companies - platform-only)

3. Owner navigates to /admin/branding
   → GET /api/proxy/admin/branding
   → RLS filters to company (company_id = owner.company_id)
   → Current colors: #0066FF (primary), #666666 (secondary)

4. Owner updates branding:
   → Primary: #FF6600 (orange)
   → Secondary: #333333
   → Welcome text: "Welcome to ACME TIN Collection"
   → Support email: support@acme.com

5. PUT /api/proxy/admin/branding
   → RBAC: COMPANY_OWNER has MANAGE_BRANDING permission ✓
   → RLS: Update only affects acme-corp company ✓
   → Success response

6. Owner checks /admin/settings
   → GET /api/proxy/admin/settings
   → Updates reminder threshold to 14 days
   → PUT /api/proxy/admin/settings saves changes

7. Owner navigates to /admin/users
   → GET /api/proxy/admin/users (lists company admins)
   → Clicks "+ Invite Admin"
   → Enters email: viewer@acme.com, role: COMPANY_VIEWER
   → POST /api/proxy/admin/users
   → Service enforces: Can't demote last COMPANY_OWNER ✓
   → Invite sent, viewer@acme.com appears in list with COMPANY_VIEWER role
```

**Expected Outcome:**
✓ Branding customization persisted
✓ Settings updated
✓ New viewer invited with restricted permissions
✓ Last-owner guard prevented demotion
✓ All operations RLS-scoped to company
✓ RBAC permissions enforced

---

### 3. Session Refresh & Token Rotation

**Actors:** Company Owner

**Flow:**
```
1. Owner is logged in, access token expires (default 15 min)
   → Client makes next API call
   → GET /api/proxy/admin/branding
   → BFF receives 401 from backend

2. BFF initiates refresh:
   → POST /api/proxy/auth/refresh
   → Includes refresh_token from httpOnly cookie
   → Backend validates & rotates token
   → Old token marked as used (family_id tracked)
   → New access + refresh tokens returned

3. BFF persists new tokens in httpOnly cookies
   → Both tokens refreshed atomically
   → Original request retried transparently
   → GET /api/proxy/admin/branding succeeds

4. On reuse detection (token family compromised):
   → Attacker uses old refresh token
   → Backend detects: token_hash exists but marked used
   → Entire family_id revoked (all tokens from that family invalid)
   → Legitimate owner's next API call fails with 401
   → Owner logs in fresh (new family issued)
```

**Expected Outcome:**
✓ Token rotation transparent to client
✓ New tokens valid for next 15 minutes
✓ Reuse detection revokes entire family (security measure)
✓ No "logout then login" user flow required

---

### 4. Login Throttle & Account Lockout

**Actors:** Attacker (unknown password)

**Flow:**
```
1. Attacker tries login with wrong password
   → POST /api/proxy/auth/login
   → Email: viewer@acme.com, password: "wrong"
   → Error: InvalidCredentials, HTTP 401

2. Attacker retries (attempts 1-5)
   → Each failure increments the per-identity counter (rolling window)
   → On reaching the cap (5), the identity is locked for a fixed cooldown

3. Legitimate owner tries login
   → Email: viewer@acme.com, password: "correct"
   → Lockout still active (cap reached)
   → Response: AccountLocked, HTTP 423
   → Must wait for the fixed cooldown window to elapse

4. After waiting, owner retries with correct password
   → Success ✓
   → Throttle counter cleared
   → Fresh tokens issued
```

**Expected Outcome:**
✓ Failed attempts tracked per identity (slug:email)
✓ Fixed cooldown lockout once the cap is reached
✓ Legitimate users affected (but recoverable after cooldown)
✓ Lockout state per-identity (doesn't affect other users)

---

### 5. RBAC: Viewer Cannot Manage Users

**Actors:** Company Viewer

**Flow:**
```
1. Viewer logs in successfully
   → POST /api/proxy/auth/login
   → Token issued with role=COMPANY_VIEWER

2. Viewer navigates to /admin/users
   → GET /api/proxy/admin/users
   → Backend checks: COMPANY_VIEWER NOT in MANAGE_ADMINS permission ✗
   → Response: HTTP 403 Forbidden
   → Frontend shows "Access Denied"

3. Viewer tries to create admin via API
   → POST /api/proxy/admin/users
   → RBAC guard: require(Permission.MANAGE_ADMINS)
   → Principal role: COMPANY_VIEWER
   → Permission denied ✗
   → Response: HTTP 403

4. Viewer can access read-only pages (if implemented)
   → GET /api/proxy/admin/branding (read)
   → ✓ Allowed if COMPANY_VIEWER in RBAC matrix
```

**Expected Outcome:**
✓ Viewer cannot access admin management pages
✓ Deny-by-default RBAC prevents unauthorized operations
✓ HTTP 403 on permission denial (not 401)
✓ All roles scoped to company (not cross-tenant)

---

### 6. Suspended Company Blocks Login

**Actors:** Company Owner (acme-corp now SUSPENDED)

**Flow:**
```
1. Platform admin suspends company
   → PATCH /api/proxy/platform/companies/{id}
   → Sets status=SUSPENDED
   → Audit log entry created

2. Company owner tries login
   → POST /api/proxy/auth/login
   → Email: admin@acme.com, password: "correct"
   → Company resolved by slug, status checked: SUSPENDED ✗ (before password verify)
   → Error: TenantUnavailable, HTTP 403
   → Response: "This account is not available."

3. Owner cannot proceed
   → Tokens NOT issued
   → No login possible until status=ACTIVE
   → (Platform admin must re-activate)
```

**Expected Outcome:**
✓ Suspended tenants block login
✓ No token bypass (status checked before password verify)
✓ Clear error messaging
✓ Prevents unauthorized access during suspension window

---

## Data Consistency Verification

### Company Creation Atomicity
```
POST /admin/companies → Create:
  ✓ Company(slug="test", status="ONBOARDING")
  ✓ CompanySettings(defaults)
  ✓ CompanyBranding(defaults)
  ✓ CompanyAdmin(owner, temporary_password)
  ✓ Send email (best-effort, non-blocking)
  OR
  ✗ Rollback if any step fails
```

### Token Family Consistency
```
Refresh Token Issued: family_id=UUID, token_hash=SHA256(token)
First Reuse: family_id=UUID found, token_hash != stored → REVOKE family
Second Attempt: All tokens in family_id invalid → Fresh login required
```

### RLS Isolation
```
Request: GET /admin/branding
  1. Extract company_id from Principal (JWT claim)
  2. Execute: SET app.current_company = {company_id}
  3. Query: SELECT * FROM branding WHERE company_id = current_setting(...)
  4. Result: Only branding for this company returned
  5. Cleanup: RESET app.current_company
```

---

## Frontend UX Verification

### Login Page
- [ ] Form renders with email + password fields
- [ ] Error messages display on invalid credentials
- [ ] Loading state shown during submission
- [ ] Submit button disabled while loading
- [ ] Redirects to /admin on success
- [ ] Redirects to /login on 401 response

### Admin Dashboard
- [ ] Auth check runs on mount
- [ ] Redirect to /login if no principal
- [ ] Navigation renders based on role
  - Platform admin: Companies link
  - Company admin: Dashboard, Branding, Settings, Users links
- [ ] Logout button clears cookies + redirects to /login

### Company Management
- [ ] List displays all companies with status badges
- [ ] Create form validates slug format
- [ ] Success message on creation
- [ ] Error message on validation failure (slug already taken, etc.)

### Branding Page
- [ ] Form loads current branding values
- [ ] Color inputs accept hex format
- [ ] Save button shows loading state
- [ ] Success message after update
- [ ] Error handling for invalid colors

---

## Performance Notes

- **JWT Verification**: Asymmetric RS256 validation ~1ms (no DB lookup)
- **RLS Binding**: SET GUC + query ~2ms overhead per request
- **Argon2 Verify**: ~100ms per password check (intentional for security)
- **Token Refresh**: ~50ms (DB transaction + JWT generation)
- **BFF Proxy**: Sub-millisecond overhead (Node.js HTTP forward)

---

**Ready for Next Phase:** Docker Compose stack should execute all flows above without modification.
