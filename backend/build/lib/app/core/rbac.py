"""RBAC primitives (placeholder for Sprint 0).

Permission enum + a deny-by-default ``require(permission)`` FastAPI dependency are
implemented in Sprint 2 (see docs/architecture/02 §8.2). Defined here so routers
can declare required permissions as they are built.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    PLATFORM_OWNER = "PLATFORM_OWNER"
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    COMPANY_OWNER = "COMPANY_OWNER"
    COMPANY_ADMIN = "COMPANY_ADMIN"
    COMPANY_VIEWER = "COMPANY_VIEWER"
    BUSINESS_CUSTOMER = "BUSINESS_CUSTOMER"


class Permission(str, Enum):
    MANAGE_COMPANIES = "manage_companies"
    MANAGE_CUSTOMERS = "manage_customers"
    SEND_INVITATIONS = "send_invitations"
    VIEW_DASHBOARD = "view_dashboard"
    EXPORT_DATA = "export_data"
    UPLOAD_CERTIFICATE = "upload_certificate"


def require(permission: Permission):  # noqa: ANN201 - returns a FastAPI dependency in Sprint 2
    """Return a dependency enforcing ``permission``. Placeholder until Sprint 2."""

    def _dependency() -> None:
        raise NotImplementedError("RBAC enforcement — implemented in Sprint 2.")

    return _dependency
