# TIN Collection Portal

White-label B2B portal that lets subscribing UAE companies collect Tax
Identification Number (TIN) data from their business customers by having them
upload UAE **VAT** and **Corporate Tax** registration certificates (PDF). The
system extracts fields via OCR/AI, lets the customer review/correct, validates
TRN/TIN rules, stores the original PDF + structured data, and gives the company
an admin dashboard for monitoring, reminders, search/filter, and export.

- **Local-first** (Docker Compose), **Azure-ready** (Azure Container Apps, UAE North).
- Controlled multi-tenant; provider abstractions for storage / OCR / email / queue.

> **Status: Sprint 0 — skeleton only.** The technical spine runs end to end
> (`docker compose up`, health probes, CI), but no business features are
> implemented yet. See the roadmap in
> [`docs/architecture/10-backlog-sprints.md`](docs/architecture/10-backlog-sprints.md).

## Documentation

- Architecture: [`docs/architecture/`](docs/architecture/) (start at `00-index.md`)
- Analysis & decisions: [`observations/`](observations/)
  - `01-brd-initial-analysis.md` — BRD review
  - `02-clarifications.md` — open questions + decision log
  - `03-assumptions.md` — **implementation baseline** for current development

## Prerequisites

- **Docker** + Docker Compose v2 (for the full local stack)
- For working on a single service directly:
  - **Python 3.12+** (backend)
  - **Node 20+** (frontend)

## Quick start (full stack)

```bash
# 1. Create the backend env file from the template
cp backend/.env.example backend/.env        # or: make env

# 2. Start everything (build on first run)
docker compose -f infra/compose/docker-compose.yml up --build
#    or simply: make up
```

### Local URLs

| Service | URL | Notes |
|---------|-----|-------|
| Frontend (web) | http://localhost/ | Next.js app shell |
| API health (via proxy) | http://localhost/api/v1/health | `{"status":"ok"}` |
| API root | http://localhost/api/v1/ | service/version |
| API docs (OpenAPI) | http://localhost/api/v1/docs *(direct: http://localhost:8000/docs if api port exposed)* | FastAPI Swagger UI |
| Mailpit (email inbox) | http://localhost:8025 | captures all outgoing mail |
| MinIO console | http://localhost:9001 | `minioadmin` / `minioadmin` |
| Traefik dashboard | http://localhost:8090 | routing overview |

The landing page shows a live **API reachable** indicator that calls the backend
health endpoint through the proxy — a green dot means the spine is wired correctly.

## Environment

All configuration is via environment variables (12-factor). Defaults live in
[`backend/.env.example`](backend/.env.example); copy it to `backend/.env`.
Provider selection is env-driven so the **same images** run locally and on Azure:

| Var | Local default | Azure |
|-----|---------------|-------|
| `STORAGE_PROVIDER` | `minio` | `azure_blob` |
| `OCR_PROVIDER` | `local` | `azure` |
| `EMAIL_PROVIDER` | `smtp` | `acs` / `sendgrid` |
| `QUEUE_PROVIDER` | `arq_redis` | `service_bus` |

Never commit real secrets — `.env` is git-ignored.

## Working on the backend (without Docker)

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install ".[dev]"
ruff check app alembic tests      # lint
pytest -q                         # tests (3 health/spine tests)
uvicorn app.main:app --reload     # needs Postgres/Redis for /ready; /health works standalone
```

Background workers (need Redis running):

```bash
arq app.worker.WorkerSettings       # job worker
arq app.scheduler.SchedulerSettings # cron scheduler
```

Database migrations (baseline; first real migration arrives in Sprint 1):

```bash
cd backend
alembic revision --autogenerate -m "message"
alembic upgrade head
```

## Working on the frontend (without Docker)

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # production build (also typechecks)
npm run typecheck
```

## Repository layout

```
backend/    FastAPI modular monolith (API + worker + scheduler, same image)
frontend/   Next.js (TypeScript + Tailwind)
infra/
  compose/            docker-compose.yml (local stack)
  nginx-or-traefik/   reverse-proxy notes
  azure/              IaC placeholder (Sprint 12)
  docker/             shared docker assets
docs/architecture/    solution architecture (24-section design)
observations/         analysis, clarifications, assumptions
.github/workflows/    CI (backend lint+test, frontend build, image build)
```

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on push/PR:

- **backend**: `ruff check` + `pytest`
- **frontend**: `tsc --noEmit` + `next build`
- **docker-build**: validates compose config and builds both images

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `api`/`worker` exit immediately | Ensure `backend/.env` exists (`make env`); check `DATABASE_URL`/`REDIS_URL` hostnames match compose service names (`db`, `redis`). |
| Landing page shows "API unreachable" | API container not healthy yet — check `docker compose logs api`; wait for the DB healthcheck. |
| Port already in use (80/5432/6379/9000/8025) | Stop the conflicting local service or change the published port in the compose file. |
| `/ready` returns 503 | Expected until Postgres/Redis are up; `/health` (liveness) is independent. |
| Frontend build fails on `public` | The `frontend/public/` dir must exist (kept via `.gitkeep`). |
| Compose can't find env_file | It is marked optional; copy `backend/.env.example` to `backend/.env` for real values. |

## License / confidentiality

Confidential — BBI Consultancy. Internal project artifact.
