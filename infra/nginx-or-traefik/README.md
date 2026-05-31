# Reverse proxy

Local development uses **Traefik** (see `infra/compose/docker-compose.yml`),
configured via the **file provider** (`traefik.yml` static + `dynamic.yml`
dynamic, mounted into the container). The file provider is used instead of the
docker-socket provider because the latter is unreliable on Docker Desktop /
Windows (`Failed to retrieve information of the docker client and server host`)
and would require giving the proxy access to the docker daemon. Services are
reached by their compose DNS names (`http://api:8000`, `http://web:3000`).

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
