# 08 — Notifications, Export & Audit

Covers output sections **15 (notification/reminder)**, **16 (export)**, **17 (audit)**.

---

## 15. Notification & Reminder Design

### 15.1 Email types
| Type | Trigger | To | Template tokens |
|------|---------|----|----|
| INVITATION | bulk/manual send, resend | business customer | brand, customer name, secure link |
| OTP | OTP request | business customer | brand, 6-digit code, 10-min expiry |
| REMINDER | cron day-X / day-2X, manual bulk | pending customers | brand, link, days outstanding |
| CONFIRMATION | submission confirmed | business customer | brand, cert type, submitted date |
| WEEKLY_SUMMARY | weekly cron | company admins | counts, overdue list link |

### 15.2 Composition & branding
- All sends go through the **notification service** (never call the email provider directly).
- Template resolution: tenant `email_templates` row for `(type, locale)` → else platform default. Rendered with brand (logo URL, colours, sender name) + safe variable substitution (autoescape).
- Locale chosen from customer/company default; Arabic templates RTL.

### 15.3 Queue, retry, delivery tracking
- Service writes a `notifications` row (`QUEUED`) → enqueues `send_email(notification_id)` → worker calls provider → stores `provider_message_id`, sets `SENT`.
- Retry: Arq backoff (e.g. 3 tries); final failure → `FAILED`. 
- **Bounce/complaint:** provider webhook (ACS Event Grid / SendGrid Event Webhook) → `/webhooks/email` → updates `notifications.status = DELIVERED|BOUNCED|SUPPRESSED`; hard bounces suppress future sends + flag the customer (bad email) on the dashboard.
- OTP emails are high-priority (separate queue/priority) and **not** retried beyond their 10-min validity.

### 15.4 Reminder engine (cron, per tenant)
```
Day 0  : INVITATION on send
Day X  : if collection_status in (INVITED,IN_PROGRESS) and auto_reminders_enabled
            and now - invited_at >= offsets[0]  -> REMINDER #1
Day 2X : offsets[1] reached -> REMINDER #2 (escalation copy)
> overdue_after_days -> collection_status = OVERDUE (dashboard flag, admin notified)
```
- `reminder_offsets_days` + `overdue_after_days` from `company_settings`.
- Increments `reminder_count`, sets `last_reminder_at`. **Stops** once `SUBMITTED`.
- Manual bulk reminder (FR-031) reuses the same path for all pending; manual single resend re-issues invitation token.
- Idempotency: a reminder for a given `(customer, offset)` is sent once (guard row/flag) to avoid duplicates on cron overlap.

### 15.5 Audit
Every notification send/bounce emits an audit event (`REMINDER_SENT`, `INVITATION_SENT`, `OTP_REQUESTED`, etc.) with `notification_id` + masked recipient.

---

## 16. Export Design

### 16.1 Flow
1. `POST /admin/exports {format, filter}` → create `exports` row (`QUEUED`) + audit `EXPORT_REQUESTED` (with filter) → enqueue `generate_export`.
2. Worker streams the filtered, tenant-scoped query (server-side cursor, no full load), writes CSV/XLSX to storage under `companies/{id}/exports/{export_id}.{ext}`.
3. Set `READY`, `row_count`, `expires_at` (e.g. 24 h). Audit `EXPORT_GENERATED`.
4. `GET /admin/exports/{id}` → short-lived signed URL; download audited (`EXPORT_DOWNLOADED`).

### 16.2 Columns (BRD export spec)
`business_customer_name, email, contact_person, cert_type, trn, tin, legal_name_en, legal_name_ar, trade_license_number, issuing_authority, registration_date, tax_period_start_date, registered_address, emirate, business_activity, legal_form, tax_group_flag, upload_date, submission_date, status, flags, ocr_confidence_summary`.

### 16.3 Rules
- Exports use **confirmed_data**-derived columns (the authoritative values), not raw OCR.
- Large exports always async (worker); small ones could stream inline but use the same path for simplicity/auditability.
- TRN/TIN included in full for legitimate compliance export (admin role required); access + generation + download all audited. Optional setting to mask for `COMPANY_VIEWER`.
- XLSX via `openpyxl` (streaming write); CSV UTF-8 BOM for Excel + Arabic correctness.

---

## 17. Audit Logging Design

### 17.1 Service
`audit.record(actor_ctx, action, entity_type, entity_id, metadata)` — called by services within the same DB transaction as the action (so audit and effect commit atomically). Append-only; the DB role has no UPDATE/DELETE on `audit_logs`.

### 17.2 Captured per event (matches BRD)
`actor_type, actor_id, company_id, action, entity_type, entity_id, timestamp, ip_address, user_agent, metadata(jsonb)`. Request middleware supplies IP/UA/correlation-id. Metadata is masked (no OTP, no full secrets; TRN/TIN policy per setting).

### 17.3 Audited actions (canonical list)
`ADMIN_LOGIN, ADMIN_LOGIN_FAILED, COMPANY_CREATED, COMPANY_UPDATED, BRANDING_UPDATED, SETTINGS_UPDATED, TEMPLATE_UPDATED, CUSTOMER_IMPORTED, CUSTOMER_CREATED, CUSTOMER_UPDATED, CUSTOMER_ARCHIVED, INVITATION_SENT, INVITATION_RESENT, OTP_REQUESTED, OTP_VERIFIED, OTP_FAILED, OTP_LOCKED, FILE_UPLOADED, OCR_COMPLETED, OCR_FAILED, FIELDS_CORRECTED, SUBMISSION_CONFIRMED, SUBMISSION_REJECTED, RECORD_VIEWED, RECORD_DOWNLOADED, EXPORT_REQUESTED, EXPORT_GENERATED, EXPORT_DOWNLOADED, REMINDER_SENT, WEEKLY_SUMMARY_SENT, RETENTION_PURGED, PLATFORM_BREAKGLASS_ACCESS`.

### 17.4 Access & retention
- Company admins read **their** tenant audit (`/admin/audit`, filterable, read-only). Platform admins read platform-level events; tenant PII access is break-glass + audited.
- Audit retained ≥ data retention; on PDPL deletion, PII in metadata anonymized but the action record (who/what/when) preserved.
- Surfaced in the record drill-down as an `AuditTimeline`.
