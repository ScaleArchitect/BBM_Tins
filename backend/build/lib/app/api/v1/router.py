"""Aggregates all v1 domain routers under ``/api/v1``.

Empty in Sprint 0 — domain routers (auth, platform, admin, portal, ...) are
mounted here as they are built in later sprints (docs/architecture/04, 06).
"""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/", tags=["meta"], summary="API root")
async def api_root() -> dict[str, str]:
    return {"service": "tin-portal", "version": "v1"}


# Later sprints:
# api_router.include_router(auth_router)
# api_router.include_router(platform_router, prefix="/platform")
# api_router.include_router(admin_router, prefix="/admin")
# api_router.include_router(portal_router, prefix="/portal")
