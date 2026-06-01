"""RBAC: role→permission matrix + a deny-by-default ``require()`` dependency.

Authorization is enforced server-side only (docs/architecture/02 §8.2). Every
protected endpoint declares the permission(s) it needs via ``Depends(require(...))``;
a role that lacks any required permission gets 403. Permissions are coarse-grained
capabilities, mapped to roles by the matrix below.
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import Depends, HTTPException, status

from app.core.security import Principal, get_current_principal


class Role(StrEnum):
    PLATFORM_OWNER = "PLATFORM_OWNER"
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    COMPANY_OWNER = "COMPANY_OWNER"
    COMPANY_ADMIN = "COMPANY_ADMIN"
    COMPANY_VIEWER = "COMPANY_VIEWER"
    BUSINESS_CUSTOMER = "BUSINESS_CUSTOMER"


class Permission(StrEnum):
    # platform
    MANAGE_COMPANIES = "manage_companies"
    VIEW_PLATFORM_HEALTH = "view_platform_health"
    MANAGE_OCR_CONFIG = "manage_ocr_config"
    # company administration (owner-only)
    MANAGE_ADMINS = "manage_admins"
    MANAGE_BRANDING = "manage_branding"
    MANAGE_SETTINGS = "manage_settings"
    # company operations
    MANAGE_CUSTOMERS = "manage_customers"
    SEND_INVITATIONS = "send_invitations"
    MANAGE_REMINDERS = "manage_reminders"
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_RECORDS = "view_records"
    EXPORT_DATA = "export_data"
    # customer
    UPLOAD_CERTIFICATE = "upload_certificate"


_PLATFORM_PERMS = {
    Permission.MANAGE_COMPANIES,
    Permission.VIEW_PLATFORM_HEALTH,
    Permission.MANAGE_OCR_CONFIG,
}

# Company operations available to both COMPANY_OWNER and COMPANY_ADMIN.
_COMPANY_OPS = {
    Permission.MANAGE_CUSTOMERS,
    Permission.SEND_INVITATIONS,
    Permission.MANAGE_REMINDERS,
    Permission.VIEW_DASHBOARD,
    Permission.VIEW_RECORDS,
    Permission.EXPORT_DATA,
}

# Tenant-administration capabilities reserved for the owner.
_COMPANY_ADMIN_ONLY = {
    Permission.MANAGE_ADMINS,
    Permission.MANAGE_BRANDING,
    Permission.MANAGE_SETTINGS,
}

ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    Role.PLATFORM_OWNER: frozenset(_PLATFORM_PERMS),
    Role.PLATFORM_ADMIN: frozenset(_PLATFORM_PERMS),
    Role.COMPANY_OWNER: frozenset(_COMPANY_OPS | _COMPANY_ADMIN_ONLY),
    Role.COMPANY_ADMIN: frozenset(_COMPANY_OPS),
    Role.COMPANY_VIEWER: frozenset({Permission.VIEW_DASHBOARD, Permission.VIEW_RECORDS}),
    Role.BUSINESS_CUSTOMER: frozenset({Permission.UPLOAD_CERTIFICATE}),
}


def permissions_for(role: str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def require(*permissions: Permission):  # noqa: ANN201 — returns a FastAPI dependency
    """Dependency factory: 403 unless the principal's role grants *all* ``permissions``."""

    required = set(permissions)

    def _dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not required.issubset(permissions_for(principal.role)):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "You do not have permission to perform this action",
            )
        return principal

    return _dependency
