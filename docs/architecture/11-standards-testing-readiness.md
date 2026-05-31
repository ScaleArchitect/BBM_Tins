# 11 — Standards, Testing, Production Readiness & Risks

Covers output sections **21 (testing strategy)**, **22 (production-readiness checklist)**, **23 (risks & mitigations)**, plus the development-standards guidance (requested section N).

---

## N. Development Standards

### Coding standards
- **Backend:** Python 3.12, `ruff` (lint+format), `mypy --strict` on domain code, type hints everywhere, Pydantic v2 at boundaries. Functions small; business rules in `validation/` are pure. No business logic in routers or providers.
- **Frontend:** TypeScript `strict`, ESLint + Prettier, no `any`, Zod at API boundaries, components ≤ ~200 lines, server components for data fetch.
- Naming: snake_case (Py), camelCase (TS), kebab-case files (TS), table/column snake_case.

### Git branching
- Trunk-based: short-lived `feature/*`, `fix/*` off `main`; PR required; squash-merge; conventional commits (`feat:`, `fix:`, `chore:`…). `main` always deployable. Protected branch + required CI + 1 review.

### Environment variable strategy
- 12-factor; all config via env (Pydantic Settings). `.env.example` committed; real `.env` git-ignored. Local = `.env`; Azure = Key Vault refs via managed identity. Same key names across environments; only values/providers differ.

### Testing strategy → see §21.

### CI/CD → see [09-devops-deployment.md](09-devops-deployment.md) §18.6.

### Database migration rules
- Alembic only; **forward-only, expand/contract** (add nullable → backfill → enforce → drop later) so rolling deploys never break the prior revision. Every migration reviewed; never edit a merged migration; migrations run as a pre-deploy job. RLS policies created/altered in migrations.

### Logging standards
- Structured JSON, correlation id per request, levels used consistently. Never log secrets/PII (mask TRN/TIN to last 4, no OTP/JWT/password). Distinguish app logs (App Insights) from business audit (DB).

### API versioning
- URL prefix `/api/v1`. Backwards-incompatible changes → `/v2`. Additive changes within a version. OpenAPI published per version.

### Error-handling conventions
- RFC 7807 problem+json; never leak stack traces/internal messages to clients; include correlation id. Domain errors mapped to HTTP codes centrally (`core/errors.py`). Workers: typed retryable vs terminal errors.

### Security review checklist
- See [02-security-compliance.md §8.12](02-security-compliance.md) — run before every release.

---

## 21. Testing Strategy

| Layer | Scope | Tools |
|-------|-------|-------|
| **Unit** | `validation/` (TRN/TIN/group/integrity), services with mocked deps, parsers against fixtures | pytest |
| **Provider contract** | one shared suite run against every storage/OCR/email/queue impl (local **and** Azure) to guarantee interchangeability | pytest, testcontainers |
| **Integration** | API + ephemeral Postgres + fake providers; **RLS cross-tenant negative tests**; auth/RBAC matrix; rate-limit/lockout | pytest, httpx, testcontainers |
| **E2E** | full invite→OTP→upload→OCR(local)→review→confirm; group-cert rejection; export | Playwright + compose stack |
| **Frontend** | component tests + form validation parity with backend | Vitest/RTL, Playwright |
| **Security** | dependency/image/secret scans; auth abuse cases; file-upload abuse | pip-audit, npm audit, gitleaks, Trivy |
| **Performance/load** | NFR-001 (<2s pages), NFR-002 (<30s cloud OCR), NFR-003 (100/500 concurrency); queue backlog behaviour | k6/Locust |

- **OCR accuracy harness:** a labelled fixture set of real VAT/CT certificates; measure per-field extraction accuracy each change; gate regressions. Track the BRD's 95% expectation as a metric.
- Coverage targets: ≥85% on domain/validation/services; happy + key edge paths on every endpoint. CI fails under threshold.
- **Test data:** factories (`factory_boy`); synthetic certificates only — no real PII in repo/CI.

---

## 22. Production Readiness Checklist

**Security**
- [ ] RLS enforced on all tenant tables; cross-tenant tests pass.
- [ ] All endpoints deny-by-default with declared permission + scope.
- [ ] OTP hashing+pepper, TTL/attempts/lockout verified; admin MFA on.
- [ ] Secrets in Key Vault via managed identity; none in code/logs/images; gitleaks clean.
- [ ] Security headers/CSP/HSTS/CORS allow-list in place; rate limits on auth/OTP/upload/export.
- [ ] File upload: MIME/magic/size/hash/PDF-sanity; signed-URL-only access; (malware scan if v1.1).
- [ ] Dependency + image scans clean; pen-test findings resolved.

**Reliability & data**
- [ ] Postgres HA + automated backups + 30-day PITR; **restore drill performed**.
- [ ] Blob soft-delete + versioning; GRS to UAE Central.
- [ ] Worker retries + dead-letter; failed-OCR + failed-email handled and visible.
- [ ] Retention purge + PDPL deletion/anonymization jobs tested.
- [ ] Migrations expand/contract; rollback plan; migration job in CD.

**Observability & ops**
- [ ] App Insights + Log Analytics; dashboards (latency, OCR, queue, OTP, email, errors).
- [ ] Alerts (5xx, queue backlog, OCR failure, DB, auth anomaly, TLS/domain expiry).
- [ ] `/health` + `/ready` probes; auto-rollback on failed probes.
- [ ] Runbooks: restore, incident response, OCR-template update, tenant onboarding.

**Compliance**
- [ ] UAE North residency confirmed for all data services; OCR residency decision (OQ4) implemented.
- [ ] PDPL: retention policy, data-subject rights flows, breach process documented.
- [ ] Audit coverage complete; audit append-only enforced at DB grant level.

**Performance**
- [ ] Load test meets NFR-001/002/003; autoscale rules validated.

---

## 23. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| Arabic / scanned-cert OCR accuracy below target | High | Med | Digital-text-first; Tesseract `ara` + preprocessing; confidence highlighting + mandatory human review; accuracy harness gating; Azure custom model in cloud. |
| **Document Intelligence not in UAE North** (OQ4) | High | Med | Keep self-hosted OCR worker in-region; treat cloud OCR as enhancement, not dependency; decision documented before S12. |
| "Group data" integrity rule undefined (OQ1) | Med | High | Build as soft-flag; isolate in `integrity.py`; confirm rule with client before S6. |
| Multi-tenant data leak | High | Low | RLS + repository guard + claim-bound context (triple layer); cross-tenant negative tests in CI; break-glass audited. |
| Email deliverability / OTP not received | Med | Med | Reputable provider + SPF/DKIM/DMARC; bounce tracking + dashboard flag; OTP resend; consider SMS provider (interface ready). |
| FTA changes certificate format | Med | Low | Parser registry by `format_version`; add parser without pipeline change; OCR accuracy alerts. |
| Customers ignore invitations | Med | High | Automated escalating reminders, overdue flags, manual bulk reminder, admin visibility. |
| Scope creep into v2 features early | Med | Med | MoSCoW enforced; "future" items designed-for but not built; abstractions keep them cheap later. |
| Large export / OCR load spikes | Med | Low | Async workers + queue + autoscale (KEDA on queue length); export streaming, not full load. |
| PDPL non-compliance | High | Low | Residency, encryption, audit, retention, deletion rights all designed in; reviewed before go-live. |
| Synchronous-OCR / DB-stored-PDF anti-patterns creeping in | Med | Low | Explicitly prohibited in standards; code review + architecture tests assert async + object-storage. |

---

## Where this leaves us
All 24 requested output sections are covered across `docs/architecture/00`–`11`. The design is implementation-ready: a developer can start at **Sprint 0** using [06-backend-structure.md](06-backend-structure.md), [09-devops-deployment.md](09-devops-deployment.md), and [03-data-model.md](03-data-model.md). Open questions OQ1–OQ8 have safe defaults so work is unblocked, but should be confirmed with the client (capture in `/observations/02-clarifications.md`).
