# Sprint 0 — Setup & Architecture

**Status:** ✅ Complete
**Date:** 2026-06-01
**Goal:** Create a running monorepo skeleton where `docker compose up` starts the
local development environment and proves the technical spine works — no business
features.
**Baseline:** [observations/03-assumptions.md](../observations/03-assumptions.md) ·
**Plan ref:** [docs/architecture/10-backlog-sprints.md](../docs/architecture/10-backlog-sprints.md) (Sprint 0)

---

## 1. Scope delivered

- Monorepo structure (`backend/`, `frontend/`, `infra/`, `docs/`, `observations/`, `Deliverables/`, `.github/`).
- FastAPI backend skeleton (modular-monolith layout) with liveness/readiness probes.
- Next.js + TypeScript + Tailwind frontend shell with a live API-health indicator.
- Provider **interfaces + stubs + factories** for storage / OCR / email / queue (no Azure SDKs yet).
- Worker + scheduler entrypoints (same image as API).
- Alembic baseline (engine wired to settings; no concrete models yet).
- Docker Compose stack (proxy, web, api, worker, scheduler, db, redis, storage, mail).
- CI workflow (backend lint+test, frontend typecheck+build, compose-config + image builds).
- README, Makefile, `.gitignore`, `.env.example`.

**Explicitly NOT built (per scope):** full auth, RLS policies, OCR logic, customer
management, upload flow, dashboard, export, Azure deployment. All such modules are
present as placeholders that raise `NotImplementedError` with the target sprint noted.

## 2. Artifacts

### Backend (`backend/`)
| File | Purpose |
|------|---------|
| [app/main.py](../backend/app/main.py) | App factory; `/health`, `/ready`, `/api/v1/health`; CORS; error handlers |
| [app/core/config.py](../backend/app/core/config.py) | Pydantic settings (env-driven, provider selection) |
| [app/core/db.py](../backend/app/core/db.py) | Lazy async engine/session + `set_current_company` RLS helper + `check_db` |
| [app/core/tenancy.py](../backend/app/core/tenancy.py) | Tenant ContextVar (IA-01) |
| [app/core/logging.py](../backend/app/core/logging.py) · [errors.py](../backend/app/core/errors.py) | structlog JSON logging · RFC 7807 problem+json |
| [app/core/security.py](../backend/app/core/security.py) · [rbac.py](../backend/app/core/rbac.py) · [rate_limit.py](../backend/app/core/rate_limit.py) · [pagination.py](../backend/app/core/pagination.py) | Placeholders w/ defined interfaces |
| [app/providers/](../backend/app/providers/) | `storage`, `ocr`, `email`, `queue` — `base.py` Protocol + impl stubs + `factory.py` |
| [app/domains/](../backend/app/domains/) | 13 domain packages (auth, platform, companies, admins, customers, invitations, certificates, ocr, validation, notifications, exports, audit, dashboard) |
| [app/models/base.py](../backend/app/models/base.py) | `Base`, `TimestampMixin`, `TenantMixin(company_id)` |
| [app/api/v1/router.py](../backend/app/api/v1/router.py) | v1 router aggregator |
| [app/worker.py](../backend/app/worker.py) · [app/scheduler.py](../backend/app/scheduler.py) | Arq worker (`ping`) · scheduler (`heartbeat`) |
| [alembic/](../backend/alembic/) + [alembic.ini](../backend/alembic.ini) | Async migration baseline |
| [tests/test_health.py](../backend/tests/test_health.py) | 3 spine tests |
| [pyproject.toml](../backend/pyproject.toml) · [Dockerfile](../backend/Dockerfile) · [.env.example](../backend/.env.example) | Deps/ruff/pytest · image · env template |

### Frontend (`frontend/`)
| File | Purpose |
|------|---------|
| [app/layout.tsx](../frontend/app/layout.tsx) · [app/page.tsx](../frontend/app/page.tsx) | RTL-ready shell · Sprint 0 landing |
| [components/ApiHealth.tsx](../frontend/components/ApiHealth.tsx) | Live API-reachability indicator |
| [lib/api.ts](../frontend/lib/api.ts) · [lib/config.ts](../frontend/lib/config.ts) | Fetch helper · API base config |
| [tailwind.config.ts](../frontend/tailwind.config.ts) · [tsconfig.json](../frontend/tsconfig.json) · [next.config.js](../frontend/next.config.js) · [Dockerfile](../frontend/Dockerfile) | Tailwind (brand CSS vars) · TS strict · standalone output · image |

### Infra / CI / root
| File | Purpose |
|------|---------|
| [infra/compose/docker-compose.yml](../infra/compose/docker-compose.yml) | Local stack: proxy·web·api·worker·scheduler·db·redis·storage·mail |
| [infra/nginx-or-traefik/README.md](../infra/nginx-or-traefik/README.md) · [infra/azure/README.md](../infra/azure/README.md) | Proxy routing notes · Azure IaC placeholder (Sprint 12) |
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | CI pipeline |
| [README.md](../README.md) · [Makefile](../Makefile) · [.gitignore](../.gitignore) | Setup/run docs · convenience targets · ignore rules |

## 3. Acceptance criteria — met

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `docker compose config` valid | ✅ | `docker compose -f infra/compose/docker-compose.yml config` → valid |
| Backend lints clean | ✅ | `ruff check app alembic tests` → All checks passed |
| Backend tests pass | ✅ | `pytest -q` → **3 passed** (`/health`, `/api/v1/health`, `/api/v1/`) |
| Frontend builds + typechecks | ✅ | `next build` → compiled, types valid, 4 routes generated |
| Provider interfaces exist (storage/ocr/email/queue) | ✅ | `providers/*/base.py` + `factory.py` |
| Worker/scheduler entrypoints | ✅ | `arq app.worker.WorkerSettings` / `app.scheduler.SchedulerSettings` |
| Alembic baseline | ✅ | `alembic/env.py` wired to settings, `Base.metadata` target |
| CI skeleton | ✅ | `.github/workflows/ci.yml` |
| README | ✅ | root `README.md` with URLs + troubleshooting |

> Note: the stack was **config-validated and unit/build-validated** in this environment;
> a full `docker compose up` runtime boot is the first smoke test on a Docker host.

## 4. How to run

```bash
cp backend/.env.example backend/.env                                   # or: make env
docker compose -f infra/compose/docker-compose.yml up --build          # or: make up
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost/ |
| API health (via proxy) | http://localhost/api/v1/health |
| Mailpit | http://localhost:8025 |
| MinIO console | http://localhost:9001 (`minioadmin`/`minioadmin`) |
| Traefik dashboard | http://localhost:8090 |

Single-service: `cd backend && pip install ".[dev]" && pytest -q` · `cd frontend && npm install && npm run dev`.

## 5. Validation evidence (summary)

- Backend: `ruff` clean; `pytest` **3 passed in ~0.05s**.
- Frontend: `next build` ✓ compiled, ✓ types valid, 4 static routes.
- Compose: `config` valid.

## 6. Gaps & follow-ups (carried into later sprints)

1. **Full `docker compose up` not yet booted** in a runtime — validate on a Docker host as the true smoke test.
2. **Repo housekeeping:** pre-existing auto-commits exist on `main` (outside our commit convention); build artifacts (node_modules/`__pycache__`/`build`/egg-info/`next-env.d.ts`) had been committed before `.gitignore` existed and were removed from tracking. Tree is now ~107 clean source files. Decide branch strategy + commit convention going forward.
3. **Cosmetic:** `observations/` is tracked by git as `Observations/` (capital O) on the case-insensitive filesystem.
4. All business modules are stubs raising `NotImplementedError` — implemented in Sprints 1–12 per the plan.

## 7. Sign-off

Sprint 0 complete. **Next:** Sprint 1 — Foundation (core models + migrations for
`companies`/`company_admins`/`audit_logs`, `TenantMixin`/`TenantRepository` + RLS
policies, audit service, logging/correlation middleware). Awaiting go-ahead before
starting Sprint 1.
