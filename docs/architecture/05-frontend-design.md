# 05 — Frontend Architecture

Covers output section **12**. Next.js (App Router) + TypeScript + Tailwind. No business logic in the client — thin BFF + presentation. i18n (en default, ar) from day one; RTL-ready.

## 12.1 Three surfaces, one app
Routing is segmented by audience; each segment has its own layout/theme:
- **Customer portal** — branded per tenant `slug`, public entry via invitation.
- **Company Admin** — authenticated tenant console.
- **Platform Admin** — internal BBI console.

## 12.2 Route map (App Router)

```
app/
  [locale]/                                   # 'en' | 'ar' (next-intl); sets dir=rtl for ar
    (customer)/
      [slug]/
        invite/[token]/page.tsx               # resolve invite + branding → enter email
        otp/page.tsx                          # OTP entry (10-min countdown, attempts left)
        portal/
          layout.tsx                          # branded shell (logo/colours from tenant)
          page.tsx                            # cert type chooser + existing submissions
          upload/[certType]/page.tsx          # dropzone upload
          review/[submissionId]/page.tsx      # OCR review/correct form
          done/[submissionId]/page.tsx        # confirmation
    (admin)/
      login/page.tsx
      admin/
        layout.tsx                            # auth guard + nav
        dashboard/page.tsx                    # summary cards + charts
        customers/page.tsx                    # list, search, filter, import, add
        customers/[id]/page.tsx               # record drill-down + audit + PDF
        submissions/page.tsx                  # records list/filter
        submissions/[id]/page.tsx             # extracted/confirmed data + PDF + flags + audit
        invitations/page.tsx                  # send/resend/reminders
        branding/page.tsx                     # logo/colours/welcome/templates
        settings/page.tsx                     # reminders/retention/cert types
        users/page.tsx                        # company admin users + roles
        exports/page.tsx                      # export jobs + downloads
    (platform)/
      platform/
        layout.tsx
        companies/page.tsx                    # tenant list
        companies/[id]/page.tsx               # tenant detail/subscription
        companies/new/page.tsx                # onboard tenant
        health/page.tsx                       # ops/queue/OCR stats
        ocr-config/page.tsx
api/                                          # Next route handlers = BFF proxy to FastAPI
  auth/[...]/route.ts                         # sets httpOnly cookies
  proxy/[...path]/route.ts                    # forwards with auth, hides token from client
```

## 12.3 Component hierarchy (key screens)
- **OCR Review** (`review/[submissionId]`): `ReviewForm` → `FieldRow` (label, value input, `ConfidenceBadge`, `FlagPill`) ×N + `PdfPreviewPane` (side-by-side) + `FlagsSummary` + `ConfirmBar`. Low-confidence fields highlighted (amber) and focused first.
- **Admin Dashboard**: `SummaryCards` (invited/submitted/pending/overdue/failed/flagged) + `StatusChart` + `RecentActivity` + `QuickActions` (send reminders, export).
- **Customer List**: `CustomerTable` (server component, paginated) + `FilterBar` + `ImportCsvDialog` (+ row-error report) + `AddCustomerDialog` + `BulkInviteButton`.
- **Record drill-down**: `RecordHeader` (status, flags) + `CertDataTabs` (Extracted | Confirmed | Diff) + `PdfPreviewPane` (signed URL) + `AuditTimeline`.
- **Branding**: `LogoUploader` + `ColorPickers` + `WelcomeTextEditor` + `TemplateEditor` + `LivePreview`.

## 12.4 State management
- **Server state:** TanStack Query (React Query) for all API data — caching, polling (submission status), optimistic updates on field corrections.
- **Forms:** React Hook Form + Zod resolvers; Zod schemas mirror backend Pydantic (shared field rules: TRN length, required fields). Validation messages localized.
- **Global UI state:** minimal — React context for theme/branding + locale; no Redux.
- **Branding/theme:** fetched server-side from `slug`, injected as CSS variables (`--brand-primary`) so Tailwind utilities pick up tenant colours; logo from signed URL.

## 12.5 Upload & review flow (client)
1. Dropzone (`react-dropzone`) — client-side guard: PDF + ≤10 MB (server re-validates).
2. `POST /portal/submissions` (multipart) → 202 + `poll_url`.
3. React Query polls `GET /portal/submissions/{id}` every ~2 s while `ocr_status in (QUEUED,PROCESSING)`; shows progress.
4. On `UNDER_REVIEW`, render `ReviewForm` from `extracted_data` + `field_confidence` + `flags`.
5. Edits autosave via `PATCH` (debounced); flags recomputed server-side and re-rendered.
6. `confirm` → success → confirmation page; handle `409 GROUP_CERT_REJECTED` with the standalone-cert modal.

## 12.6 Error / loading / empty states
- Skeletons for tables/cards; query-error boundaries with retry; toast for mutations.
- OCR states: `Processing…` (spinner + reassurance), `Needs review` (form), `Extraction failed` (retry/re-upload CTA), `Locked` (OTP cooldown timer).
- Global error boundary → friendly page + correlation id (no stack traces).

## 12.7 Accessibility & responsive
- WCAG 2.1 AA target: labelled inputs, focus management on step changes, keyboard-navigable tables/dialogs, `aria-live` for OTP countdown and OCR status, colour-contrast-safe brand palette validation (warn admin if chosen colours fail contrast).
- Responsive: mobile-first Tailwind; customer portal optimized for phone (vendors upload on mobile); admin tables collapse to cards on small screens; tablet supported.
- RTL: `next-intl` + `dir` switch; logical CSS properties (`ps-`/`pe-`) so Arabic mirrors correctly.

## 12.8 Security in the frontend
- Tokens live in httpOnly cookies; the browser never reads them. The BFF (`/api/proxy`) attaches auth server-side.
- No PII in localStorage. CSP nonce-based. Forms post through same-origin BFF (CSRF-safe). Signed PDF URLs fetched on demand, never embedded long-term.
