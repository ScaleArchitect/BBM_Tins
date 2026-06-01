"""Aggregates all v1 domain routers under ``/api/v1``.

Sprint 2 mounts admin auth, platform tenant management, and company-admin
management (users, branding, settings). Customer portal + certificate routes
arrive in later sprints.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.domains.admins.router import router as admins_router
from app.domains.auth.router import router as auth_router
from app.domains.companies.router import router as companies_router
from app.domains.platform.router import router as platform_router

api_router = APIRouter()


@api_router.get("/", tags=["meta"], summary="API root")
async def api_root() -> dict[str, str]:
    return {"service": "tin-portal", "version": "v1"}


api_router.include_router(auth_router)
api_router.include_router(platform_router)
api_router.include_router(admins_router)
api_router.include_router(companies_router)
