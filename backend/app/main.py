"""FastAPI application factory + health/readiness probes (Sprint 0).

Wires logging, CORS, problem+json error handling, and mounts the v1 API router.
No business endpoints yet — those arrive in later sprints.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.db import check_db
from app.core.errors import add_exception_handlers
from app.core.logging import configure_logging, get_logger

health_router = APIRouter(tags=["health"])


@health_router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@health_router.get("/ready", summary="Readiness probe")
async def ready() -> JSONResponse:
    components = {"database": await check_db(), "redis": await _check_redis()}
    all_ok = all(components.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "degraded", "components": components},
    )


async def _check_redis() -> bool:
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(get_settings().redis_url)
        try:
            await client.ping()
            return True
        finally:
            await client.aclose()
    except Exception:  # noqa: BLE001 - readiness probe must not raise
        return False


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    get_logger("app").info("starting", app_env=settings.app_env)

    # Serve OpenAPI/Swagger under the API prefix so they are reachable through
    # the reverse proxy (which routes /api -> backend, / -> frontend).
    app = FastAPI(
        title="TIN Collection Portal API",
        version="0.0.0",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    add_exception_handlers(app)

    # Probes at root (for container/orchestrator) and under the API prefix (for the proxied UI).
    app.include_router(health_router)
    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
