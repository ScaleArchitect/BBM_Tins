# Reverse proxy

Local development uses **Traefik** (see `infra/compose/docker-compose.yml`),
configured entirely via container labels + command flags — no static config file
is required for Sprint 0.

## Routing

| Path prefix | Routed to | Priority |
|-------------|-----------|----------|
| `/api`      | `api` (FastAPI, :8000) | 10 (higher) |
| `/`         | `web` (Next.js, :3000) | 1 (fallback) |

- The FastAPI backend serves the API under `/api/v1` and exposes `/health` and
  `/ready` at the root for container/orchestrator probes; the proxied UI reaches
  health via `/api/v1/health`.
- Traefik dashboard (local only): http://localhost:8090

## Azure

In Azure this role is played by **Azure Front Door + WAF** (OWASP ruleset, TLS,
custom domains / tenant subdomains) in front of the Azure Container Apps ingress
(see `docs/architecture/09-devops-deployment.md`). TLS is terminated at the proxy
in both environments.
