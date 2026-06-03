# Open Technical Debt

Cross-sprint register of **outstanding** technical-debt items. Fixed items are
recorded per-sprint (e.g. [sprint-2/Fixed_Tech_Debt.md](sprint-2/Fixed_Tech_Debt.md)).

| ID | Title | Severity | Origin | Status |
|----|-------|----------|--------|--------|
| OTD-05 | One-time set-password link (vs. emailed temp password) | Low | Sprint 2 | Open (deferred to Sprint 3) |

> **Resolved since last review** — moved to
> [sprint-2/Fixed_Tech_Debt.md](sprint-2/Fixed_Tech_Debt.md):
> OTD-01 (CSRF, → TD-S2-09), OTD-02 (server-side TOTP secret, → TD-S2-10),
> OTD-03 (CI integration tests, → TD-S2-11), OTD-04 (stable dev JWT keypair,
> → TD-S2-12).

---

## OTD-05 — One-time set-password link (vs. emailed temp password)
- **Severity:** Low
- **Origin:** Sprint 2
- **Location:** `backend/app/domains/platform/service.py` (`_send_invite`),
  `backend/app/domains/admins/service.py` (`_send_admin_invite`)
- **Problem:** Invitations email a temporary password directly (captured by
  Mailpit locally). A one-time set-password link is the intended flow.
- **Why deferred:** Depends on the notification engine landing in Sprint 3.
- **Proposed fix:** Replace the temp-password email with a tokenized
  set-password link once the notification engine is available.

</content>
