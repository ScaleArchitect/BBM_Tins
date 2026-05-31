# 04 — API Design

Covers output section **11**. REST, JSON, OpenAPI-documented. Base path `/api/v1`. Versioned by URL prefix.

## Conventions
- Auth: `Authorization: Bearer <jwt>` (admins) or customer session bearer; BFF forwards httpOnly cookie → header.
- Errors: RFC 7807 problem+json: `{ "type", "title", "status", "detail", "errors": {field: [..]} }`.
- Pagination: `?page=&page_size=` → `{ items, page, page_size, total }`. Filtering via explicit query params.
- Idempotency: `Idempotency-Key` header honoured on uploads, invitation sends, exports.
- All times ISO-8601 UTC. All IDs uuid.

## 11.1 Endpoint inventory

### Auth — admins (`/auth`)
| Method | Path | Who | Purpose |
|--------|------|-----|---------|
| POST | `/auth/login` | platform/company admin | password (+TOTP) → tokens |
| POST | `/auth/refresh` | any admin | rotate refresh → new access |
| POST | `/auth/logout` | any admin | revoke refresh family |
| POST | `/auth/totp/enroll` · `/auth/totp/verify` | admin | MFA setup |

### Auth — business customer (`/portal/auth`)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/portal/{slug}/invite/{token}` | resolve invitation + branding (no auth); marks OPENED |
| POST | `/portal/{slug}/otp/request` | body `{email}` → send OTP (rate-limited, no enumeration) |
| POST | `/portal/{slug}/otp/verify` | body `{email, code}` → customer session |

### Platform Admin (`/platform`) — role PLATFORM_*
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/platform/companies` | create tenant (FR-001) |
| GET | `/platform/companies` | list/search tenants |
| GET/PATCH | `/platform/companies/{id}` | view / update status, subscription |
| POST | `/platform/companies/{id}/admins` | seed first company admin (invite email) |
| GET | `/platform/health` | platform ops status, queue depth, OCR stats |
| GET/PATCH | `/platform/ocr-config` | OCR provider/template config |

### Company Admin (`/admin`) — tenant-scoped, role COMPANY_*
Branding & settings:
| Method | Path | Purpose |
|--------|------|---------|
| GET/PUT | `/admin/branding` | logo/colours/welcome (FR-002) |
| POST | `/admin/branding/logo` | upload logo (multipart) |
| GET/PUT | `/admin/settings` | reminders/retention/cert types |
| GET/PUT | `/admin/email-templates` | per-type templates (FR-005) |
| GET/POST | `/admin/users` | manage company admins + roles (FR-004) |

Customers & invitations:
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/admin/customers/import` | CSV bulk import (FR-006), returns row report |
| POST | `/admin/customers` | add one (FR-007) |
| GET | `/admin/customers` | list + search/filter (FR-023) |
| GET/PATCH | `/admin/customers/{id}` | view/edit/archive |
| POST | `/admin/invitations/send` | bulk send to selected/all (FR-008) |
| POST | `/admin/invitations/{id}/resend` | resend one (FR-012) |
| POST | `/admin/reminders/bulk` | manual reminder to all pending (FR-031) |

Dashboard, records, export:
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/dashboard/summary` | counts by status (FR-022) |
| GET | `/admin/submissions` | search/filter records (FR-023) |
| GET | `/admin/submissions/{id}` | drill-down: data + flags + audit (FR-024) |
| GET | `/admin/submissions/{id}/file` | signed URL to PDF |
| GET | `/admin/customers/{id}/audit` | audit history |
| POST | `/admin/exports` | create export job (FR-025/032) |
| GET | `/admin/exports/{id}` | status + signed download URL |

### Customer Portal (`/portal`) — customer session
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/portal/me` | invitation context, enabled cert types, existing submissions |
| POST | `/portal/submissions` | create + upload PDF (multipart) → 202 (FR-013/014/015) |
| GET | `/portal/submissions/{id}` | poll status + extracted data + flags |
| PATCH | `/portal/submissions/{id}` | save corrected `confirmed_data` (FR-018) |
| POST | `/portal/submissions/{id}/confirm` | final submit (FR-017) |
| POST | `/portal/submissions/{id}/reprocess` | re-run OCR after failure |

### Audit (`/admin/audit`, `/platform/audit`)
| GET | `/admin/audit` | tenant audit log, filterable (read-only) |

## 11.2 Key request/response examples

### Create company (Platform Admin)
```http
POST /api/v1/platform/companies
Authorization: Bearer <platform-jwt>
{
  "legal_name": "Acme Trading LLC",
  "slug": "acme",
  "trade_license_number": "CN-1234567",
  "primary_admin_email": "admin@acme.ae",
  "enabled_cert_types": ["VAT", "CT"]
}
→ 201
{ "id": "0c2...", "slug": "acme", "status": "PENDING",
  "portal_url": "https://acme.taxportal.ae", "admin_invite_sent": true }
```

### Request OTP (customer)
```http
POST /api/v1/portal/acme/otp/request
{ "email": "vendor@supplier.ae" }
→ 200  { "message": "If the email matches an invitation, an OTP has been sent.",
         "otp_ttl_seconds": 600 }
```

### Verify OTP
```http
POST /api/v1/portal/acme/otp/verify
{ "email": "vendor@supplier.ae", "code": "418207" }
→ 200  { "session_token": "<bearer>", "expires_in": 3600,
         "enabled_cert_types": ["VAT","CT"] }
→ 423 (locked)  { "title":"Locked","detail":"Too many attempts. Try again in 28 minutes." }
```

### Upload certificate (customer) — async
```http
POST /api/v1/portal/submissions
Authorization: Bearer <customer-session>
Content-Type: multipart/form-data
  cert_type=VAT
  file=@vat-cert.pdf
Idempotency-Key: 4f1c...
→ 202
{ "id": "sub_9a...", "status": "UPLOADED", "ocr_status": "QUEUED",
  "poll_url": "/api/v1/portal/submissions/sub_9a..." }
```

### Poll submission after OCR
```http
GET /api/v1/portal/submissions/sub_9a...
→ 200
{
  "id": "sub_9a...", "cert_type": "VAT",
  "status": "UNDER_REVIEW", "ocr_status": "COMPLETED",
  "extracted_data": {
    "trn": "100123456700003", "legal_name_en": "Supplier FZ LLC",
    "legal_name_ar": "المورد", "trade_license_number": "DED-998877",
    "emirate": "Dubai", "registration_date": "2018-03-01"
  },
  "derived": { "trn_normalized": "100123456700003", "tin": "1001234567" },
  "field_confidence": { "trn": 0.99, "legal_name_ar": 0.71, "emirate": 0.95 },
  "flags": [
    { "code": "LOW_CONFIDENCE", "severity": "warn", "field": "legal_name_ar" },
    { "code": "NAME_MISMATCH", "severity": "warn",
      "detail": "Confirmed legal name differs from master data 'Supplier FZE'." }
  ]
}
```

### Save corrections + confirm
```http
PATCH /api/v1/portal/submissions/sub_9a...
{ "confirmed_data": { "legal_name_ar": "المورد ش.م.ح", "emirate": "Dubai" } }
→ 200 { "status": "UNDER_REVIEW", "flags": [ ...recomputed... ] }

POST /api/v1/portal/submissions/sub_9a.../confirm
→ 200 { "status": "SUBMITTED", "submitted_at": "2026-06-01T10:22:03Z",
        "confirmation_email_queued": true }
→ 409 (group cert, REJECT policy)
   { "title":"Group certificate", "detail":"Upload a standalone certificate.",
     "status":409, "code":"GROUP_CERT_REJECTED" }
```

### Dashboard summary (admin)
```http
GET /api/v1/admin/dashboard/summary
→ 200
{ "invited": 240, "submitted": 168, "pending": 52, "overdue": 14,
  "failed_extraction": 3, "flagged": 9, "upload_rate_pct": 70.0 }
```

### Search submissions (admin)
```http
GET /api/v1/admin/submissions?status=FLAGGED&cert_type=VAT&q=supplier&page=1&page_size=25
→ 200 { "items": [ { "id","customer_name","email","cert_type","trn_normalized",
                     "tin","status","flags","submitted_at" } ], "total": 9, ... }
```

### CSV import report
```http
POST /api/v1/admin/customers/import  (multipart csv)
→ 200
{ "received": 120, "created": 113, "updated": 4, "skipped": 3,
  "errors": [ { "row": 17, "reason": "invalid email" } ] }
```

### Create export
```http
POST /api/v1/admin/exports
{ "format": "XLSX", "filter": { "status": "SUBMITTED", "cert_type": "VAT" } }
→ 202 { "id": "exp_1...", "status": "QUEUED" }
GET /api/v1/admin/exports/exp_1...
→ 200 { "status": "READY", "download_url": "<signed 5-min URL>", "row_count": 168 }
```

## 11.3 Status & error codes
`200/201/202` success; `400` validation; `401` unauth; `403` forbidden (RBAC/tenant); `404`; `409` conflict (dup/group cert/idempotency); `413` file too large; `415` bad MIME; `423` locked (OTP); `429` rate-limited (+`Retry-After`); `5xx` with correlation id, never leaking internals.
