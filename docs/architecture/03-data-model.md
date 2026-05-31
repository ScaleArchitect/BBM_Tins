# 03 — Data Model & Status Lifecycle

Covers output sections **9 (data model / ERD)** and **10 (status lifecycle)**.

Conventions: PostgreSQL 16. PKs are `uuid` (`gen_random_uuid()`). Every table has `created_at timestamptz`, `updated_at timestamptz`. Tenant-scoped tables carry `company_id uuid NOT NULL` + RLS. Money/PII columns noted. Enums implemented as Postgres `ENUM` types (or `text` + check) — names below.

## 9.1 ERD (textual)

```
platform_admins
companies ──1:N── company_admins
   │  1:N
   ├───────── business_customers ──1:N── invitations
   │                 │  1:N
   │                 └───────────── certificate_submissions ──1:1── certificate_files
   │                                        │  1:1                        
   │                                        └──── ocr_results
   ├── company_branding (1:1)
   ├── company_settings (1:1, reminder/retention config)
   ├── email_templates (1:N)
   ├── notifications (1:N)            (email log: invite/otp/reminder/confirm/summary)
   ├── exports (1:N)
   └── audit_logs (1:N)              (also references actor + entity)
```

Cardinalities:
- `company 1:N business_customers`; `business_customer 1:N invitations` (resends/new); `business_customer 1:N certificate_submissions` (many per type — OQ8).
- `certificate_submission 1:1 certificate_files` and `1:1 ocr_results` (reprocess overwrites/append a new ocr_results row, latest wins via `is_current`).

## 9.2 Tables

### `companies` (tenant root)
| col | type | notes |
|-----|------|-------|
| id | uuid PK | |
| slug | citext UNIQUE | portal path/subdomain, e.g. `acme` |
| legal_name | text NOT NULL | |
| trade_license_number | text | |
| status | enum `company_status` | `PENDING, ACTIVE, SUSPENDED, CANCELLED` |
| subscription_status | enum | `TRIAL, ACTIVE, PAST_DUE, CANCELLED` |
| primary_admin_email | citext NOT NULL | |
| created_by_platform_admin | uuid FK platform_admins | |
Indexes: `UNIQUE(slug)`. RLS: exempt (root); reads scoped by platform role or by membership.

### `company_branding` (1:1)
`company_id PK/FK`, `logo_object_key text`, `primary_color text`, `secondary_color text`, `welcome_text text`, `support_email citext`, `locale_default text default 'en'`.

### `company_settings` (1:1)
`company_id PK/FK`, `reminder_offsets_days int[] default '{3,7,14}'`, `overdue_after_days int default 21`, `auto_reminders_enabled bool`, `weekly_summary_enabled bool`, `retention_months int default 24`, `enabled_cert_types text[] default '{VAT,CT}'`, `group_cert_policy enum('REJECT','WARN') default 'REJECT'`.

### `platform_admins`
`id PK`, `email citext UNIQUE`, `password_hash text`, `totp_secret text` (encrypted), `role enum('PLATFORM_OWNER','PLATFORM_ADMIN')`, `is_active bool`, `last_login_at`.

### `company_admins` (tenant-scoped)
| col | type | notes |
|-----|------|-------|
| id | uuid PK | |
| company_id | uuid FK NOT NULL | RLS key |
| email | citext NOT NULL | |
| password_hash | text | Argon2id |
| totp_secret | text | nullable |
| role | enum `company_role` | `COMPANY_OWNER, COMPANY_ADMIN, COMPANY_VIEWER` |
| is_active | bool | |
| last_login_at | timestamptz | |
Indexes: `UNIQUE(company_id, email)`.

### `business_customers` (tenant-scoped) — the invitee + master data
| col | type | notes |
|-----|------|-------|
| id | uuid PK | |
| company_id | uuid FK NOT NULL | RLS key |
| customer_name | text NOT NULL | PII |
| email | citext NOT NULL | PII |
| contact_person | text | PII |
| external_ref | text | internal vendor/customer id (optional) |
| entity_type | text | optional |
| expected_trn | text | master data for integrity check (OQ1) |
| expected_legal_name | text | master data |
| expected_trade_license | text | master data |
| collection_status | enum `collection_status` | see §10.1 |
| invited_at / first_submitted_at / completed_at | timestamptz | |
| reminder_count | int default 0 | |
| last_reminder_at | timestamptz | |
| is_archived | bool default false | |
Indexes: `UNIQUE(company_id, email)`, `(company_id, collection_status)`, `(company_id, customer_name)`, trigram index on name/email for search.

### `invitations` (tenant-scoped)
| col | type | notes |
|-----|------|-------|
| id | uuid PK | |
| company_id | uuid FK NOT NULL | |
| business_customer_id | uuid FK NOT NULL | |
| token_hash | text NOT NULL | sha256 of opaque token; raw never stored |
| status | enum `invitation_status` | see §10.2 |
| sent_at / opened_at / authenticated_at / completed_at | timestamptz | |
| expires_at | timestamptz | |
Indexes: `UNIQUE(token_hash)`, `(company_id, business_customer_id)`.

### `otp_challenges` (tenant-scoped, ephemeral)
| col | type | notes |
|-----|------|-------|
| id | uuid PK | |
| company_id | uuid FK | |
| invitation_id | uuid FK | |
| email | citext | |
| code_hash | text | HMAC-SHA256(code, pepper) |
| attempts | int default 0 | |
| max_attempts | int default 3 | |
| expires_at | timestamptz | now()+10min |
| locked_until | timestamptz | set on 3rd failure (+30min) |
| consumed_at | timestamptz | |
Indexes: `(invitation_id)`, `(email, created_at)`. Periodically purged.

### `certificate_submissions` (tenant-scoped) — core record
| col | type | notes |
|-----|------|-------|
| id | uuid PK | |
| company_id | uuid FK NOT NULL | RLS key |
| business_customer_id | uuid FK NOT NULL | |
| cert_type | enum `cert_type` | `VAT, CT` |
| status | enum `submission_status` | see §10.3 |
| ocr_status | enum `ocr_status` | see §10.4 |
| **trn_normalized** | varchar(15) | digits only; indexed |
| **tin** | varchar(10) | derived; indexed; nullable for CT if rule N/A |
| legal_name_en | text | confirmed value, searchable |
| legal_name_ar | text | Unicode, confirmed |
| trade_license_number | text | |
| issuing_authority | text | |
| registration_date | date | |
| tax_period_start_date | date | CT only |
| registered_address | text | |
| emirate | text | |
| business_activity | text | VAT |
| legal_form | text | CT |
| is_group_certificate | bool default false | FR-028 detection |
| **extracted_data** | jsonb | OCR-parsed field map (pre-correction) |
| **confirmed_data** | jsonb | customer-confirmed field map (post-correction) |
| **field_confidence** | jsonb | per-field confidence 0–1 |
| flags | jsonb | array of {code, severity, message} (duplicate, mismatch, low_conf, group_cert) |
| submitted_at | timestamptz | when customer confirmed |
| created_at/updated_at | timestamptz | |
Indexes: `(company_id, status)`, `(company_id, cert_type)`, `(company_id, trn_normalized)`, `(company_id, tin)`, `(company_id, business_customer_id)`, `(company_id, submitted_at)`. Partial unique to flag dupes is enforced in app + a non-unique index (dupes are flagged, not hard-blocked — OQ1).

> **Separation principle:** `extracted_data` (what OCR produced) and `confirmed_data` (what the customer approved) are never merged. Searchable typed columns (`trn_normalized`, `tin`, `legal_name_*`, dates) are populated from `confirmed_data` on submit.

### `certificate_files` (tenant-scoped)
`id PK`, `company_id FK`, `submission_id FK 1:1`, `storage_key text`, `original_filename text` (sanitized), `content_type text`, `size_bytes bigint`, `sha256 char(64)`, `page_count int`, `scan_status enum('PENDING','CLEAN','INFECTED','SKIPPED')`, `uploaded_by_email citext`, `uploaded_at`. Index `(company_id, sha256)` for dedupe.

### `ocr_results` (tenant-scoped)
`id PK`, `company_id FK`, `submission_id FK`, `provider text` (`local`/`azure_doc_intelligence`), `model_version text`, `raw_json jsonb` (full provider response), `overall_confidence numeric`, `pages int`, `duration_ms int`, `is_current bool`, `error text`, `created_at`. Reprocessing inserts a new row, flips prior `is_current=false`. Raw output preserved forever (until retention purge).

### `email_templates` (tenant-scoped)
`id PK`, `company_id FK`, `type enum('INVITATION','OTP','REMINDER','CONFIRMATION','WEEKLY_SUMMARY')`, `subject text`, `body_html text`, `body_text text`, `locale text`, `is_active bool`. Default platform templates used if none.

### `notifications` (tenant-scoped) — email send log
`id PK`, `company_id FK`, `business_customer_id FK null`, `type` (same enum + OTP), `to_email citext`, `provider_message_id text`, `status enum('QUEUED','SENT','DELIVERED','BOUNCED','FAILED','SUPPRESSED')`, `attempts int`, `error text`, `sent_at`, `created_at`. Index `(company_id, type, status)`.

### `exports` (tenant-scoped)
`id PK`, `company_id FK`, `requested_by uuid` (company_admin), `format enum('CSV','XLSX')`, `filter_json jsonb`, `status enum('QUEUED','RUNNING','READY','FAILED')`, `storage_key text`, `row_count int`, `expires_at`, `created_at`. Every export also writes an audit event.

### `audit_logs` (append-only)
| col | type | notes |
|-----|------|-------|
| id | uuid PK | |
| company_id | uuid FK NULL | null for platform-level events |
| actor_type | enum | `PLATFORM_ADMIN, COMPANY_ADMIN, BUSINESS_CUSTOMER, SYSTEM` |
| actor_id | uuid NULL | |
| action | text | e.g. `OTP_VERIFIED`, `FILE_UPLOADED` (see §17 list) |
| entity_type | text | |
| entity_id | uuid NULL | |
| metadata | jsonb | masked, no secrets |
| ip_address | inet | |
| user_agent | text | |
| created_at | timestamptz | |
Append-only (no UPDATE/DELETE grant). Indexes `(company_id, created_at)`, `(entity_type, entity_id)`, `(actor_type, actor_id)`. Consider monthly partitioning later.

## 9.3 Constraints & integrity rules
- FK `ON DELETE RESTRICT` for tenant data (use soft-delete/archive instead of cascade).
- `CHECK (char_length(trn_normalized) = 15)` when not null; `CHECK (char_length(tin) = 10)` when not null.
- `UNIQUE(company_id, email)` on customers and admins.
- RLS policies on all tenant tables; `BYPASSRLS` only for the platform/admin DB role used on explicit cross-tenant paths.

## 10. Status Lifecycle

### 10.1 `collection_status` (business_customers — the dashboard rollup)
```
NOT_INVITED ──invite──▶ INVITED ──open link──▶ IN_PROGRESS ──confirm submission──▶ SUBMITTED
     │                     │                          │
     │                     └── time > overdue_after ──┴──▶ OVERDUE (still actionable)
     └── archive ─▶ ARCHIVED            any ──▶ FAILED_EXTRACTION (if OCR failed & awaiting)            any ──▶ FLAGGED (has open flags)
```
Dashboard buckets (FR-022): Invited, Submitted, Pending(=INVITED+IN_PROGRESS), Overdue, Failed extraction, Flagged. `SUBMITTED` once ≥1 required cert confirmed clean; reminders stop on `SUBMITTED`.

### 10.2 `invitation_status`
`PENDING → SENT → OPENED → AUTHENTICATED → COMPLETED`; side states `EXPIRED`, `BOUNCED`, `REVOKED`. Resend creates/refreshes a token, back to `SENT`.

### 10.3 `submission_status` (per certificate)
```
DRAFT ─upload─▶ UPLOADED ─enqueue─▶ (ocr runs) ─▶ UNDER_REVIEW ─customer confirm─▶ SUBMITTED
                   │                                   │
                   │                                   ├─ open flags ─▶ FLAGGED (still confirmable per policy)
                   └─ ocr fail ─▶ EXTRACTION_FAILED ──reprocess──▶ UPLOADED
                       group cert + REJECT policy ─▶ REJECTED (terminal; user must re-upload standalone)
QUARANTINED (v1.1, pending malware scan) ─clean─▶ continue ; ─infected─▶ REJECTED
```

### 10.4 `ocr_status`
`PENDING → QUEUED → PROCESSING → COMPLETED` | `FAILED` (with `error`, retryable). Drives `submission_status` transitions via the worker.

### 10.5 Status transition ownership
- Worker transitions: `UPLOADED→PROCESSING→UNDER_REVIEW/EXTRACTION_FAILED/REJECTED`.
- Customer transitions: `UNDER_REVIEW→SUBMITTED` (confirm), re-upload after `REJECTED/FAILED`.
- System/cron: `INVITED→OVERDUE`.
- Admin: `→ARCHIVED`, resend (`invitation`), manual reprocess.
All transitions emit an audit event and are validated by a small state-machine guard in the service layer (illegal transitions rejected).
