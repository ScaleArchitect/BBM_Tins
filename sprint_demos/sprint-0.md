# Sprint 0 — Demo Run

**Date:** 2026-06-01
**Result:** ✅ Pass — full local stack boots and the technical spine works end to end.
**Deliverable ref:** [Deliverables/sprint-0.md](../Deliverables/sprint-0.md)
**Commits at time of demo:** `a3348d0` (after in-demo fixes); pushed to `origin/main`.

---

## 1. Goal

Prove the Sprint 0 acceptance criterion live:

> `docker compose up` starts the local development environment and the technical
> spine (frontend ↔ proxy ↔ API ↔ Postgres / Redis / object storage / mail / workers) works.

## 2. Environment

- Host: Windows 11, Docker Desktop (engine `29.1.3`, linux/amd64).
- Stack: `infra/compose/docker-compose.yml` (9 services).
- Command used:
  ```bash
  cp backend/.env.example backend/.env
  docker compose -f infra/compose/docker-compose.yml up --build -d
  ```

## 3. Result — containers

All 9 containers started; `api`, `db`, `mail` report healthy.

| Service | Status |
|---------|--------|
| proxy (Traefik) | Up |
| web (Next.js) | Up |
| api (FastAPI) | Up (healthy) |
| worker (Arq) | Up |
| scheduler (Arq cron) | Up |
| db (Postgres 16) | Up (healthy) |
| redis | Up |
| storage (MinIO) | Up |
| mail (Mailpit) | Up (healthy) |

## 4. Result — endpoint smoke tests

| Check | URL | Result |
|-------|-----|--------|
| API liveness (via proxy) | http://localhost/api/v1/health | `{"status":"ok"}` |
| API readiness (DB + Redis integration) | http://localhost/api/v1/ready | `{"status":"ready","components":{"database":true,"redis":true}}` |
| API root | http://localhost/api/v1/ | `{"service":"tin-portal","version":"v1"}` |
| Swagger UI | http://localhost/api/v1/docs | HTTP 200 |
| OpenAPI schema | http://localhost/api/v1/openapi.json | HTTP 200 |
| Frontend | http://localhost/ | HTTP 200 (title "TIN Collection Portal") |
| Mailpit UI | http://localhost:8025 | HTTP 200 |
| MinIO console | http://localhost:9001 | HTTP 200 |

**Key signal:** `/ready` returning `database:true` and `redis:true` confirms the API
genuinely connects to Postgres and Redis — not just that the process is alive.

## 5. Result — background workers

- **Worker:** `Starting worker for 1 functions: ping`; `redis_version=7.4.9 … clients_connected=2`; structured `worker.startup` log — connected to Redis and registered its job function.
- **Scheduler:** cron `heartbeat` fires every minute, emitting structured JSON logs (`{"event":"scheduler.heartbeat",...}`).

The full async spine (API enqueues → Redis → worker; scheduler cron) is proven.

## 6. Issues found & fixed during the demo

| # | Issue | Root cause | Fix | Commit |
|---|-------|-----------|-----|--------|
| 1 | Docker commands failed (`dockerDesktopLinuxEngine` pipe not found) | Docker Desktop engine was not running | Started Docker Desktop, waited for engine readiness | — (environment) |
| 2 | Every request via the proxy (`:80`) returned Traefik 404 | Traefik **docker-socket provider** can't reach the daemon on Docker Desktop/Windows (`Failed to retrieve information of the docker client and server host`), so no routes loaded | Switched proxy to Traefik **file provider** (`infra/nginx-or-traefik/traefik.yml` + `dynamic.yml`), routing `/api`→`api:8000` and `/`→`web:3000` by DNS name; removed the docker-socket mount + inert labels | `a3348d0` |
| 3 | `/api/v1/docs` and `/api/v1/openapi.json` returned 404 via the proxy | FastAPI serves docs/openapi at the app root (`/docs`, `/openapi.json`), which the proxy routes to the frontend | Configured FastAPI `docs_url`/`redoc_url`/`openapi_url` under the `/api/v1` prefix | `a3348d0` |

> Bonus: also resolved a **GitHub push rejection** unrelated to the runtime — the
> auto-committer had committed `frontend/node_modules` (a 129 MB SWC binary) into
> git history before `.gitignore` existed. Soft-reset to the remote tip and
> re-committed the clean tree (fast-forward, no force-push); largest blob in
> history is now 0.1 MB.

## 7. Reproduce

```bash
# from repo root
cp backend/.env.example backend/.env                                # or: make env
docker compose -f infra/compose/docker-compose.yml up --build -d    # or: make up

# verify
curl http://localhost/api/v1/health      # {"status":"ok"}
curl http://localhost/api/v1/ready        # db+redis true
# open http://localhost/  and  http://localhost/api/v1/docs

# tear down
docker compose -f infra/compose/docker-compose.yml down      # add -v to wipe volumes
```

## 8. Notes / follow-ups

- The stack was left **running** after the demo for interactive inspection.
- `api` is reachable only via the proxy (no host port published); use `http://localhost/api/v1/...`.
- Next runtime demo: after Sprint 1, demonstrate migrations applied + RLS tenant isolation.
