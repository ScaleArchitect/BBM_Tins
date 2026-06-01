"""Unit tests for the RBAC permission matrix + require() dependency (no DB)."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.core.rbac import Permission, Role, permissions_for, require
from app.core.security import COMPANY, PLATFORM, Principal


def _principal(role: str, *, platform: bool = False) -> Principal:
    return Principal(
        principal_type=PLATFORM if platform else COMPANY,
        id=uuid.uuid4(),
        role=role,
        company_id=None if platform else uuid.uuid4(),
    )


def test_matrix_owner_vs_admin_vs_viewer() -> None:
    owner = permissions_for(Role.COMPANY_OWNER)
    admin = permissions_for(Role.COMPANY_ADMIN)
    viewer = permissions_for(Role.COMPANY_VIEWER)
    # Owner-only capabilities.
    assert Permission.MANAGE_ADMINS in owner and Permission.MANAGE_ADMINS not in admin
    assert Permission.MANAGE_BRANDING in owner and Permission.MANAGE_BRANDING not in admin
    # Shared operations.
    assert Permission.MANAGE_CUSTOMERS in admin and Permission.MANAGE_CUSTOMERS in owner
    # Viewer is read-only.
    assert viewer == frozenset({Permission.VIEW_DASHBOARD, Permission.VIEW_RECORDS})
    assert Permission.EXPORT_DATA not in viewer


def test_platform_cannot_manage_tenant_resources() -> None:
    perms = permissions_for(Role.PLATFORM_ADMIN)
    assert Permission.MANAGE_COMPANIES in perms
    assert Permission.MANAGE_BRANDING not in perms
    assert Permission.MANAGE_CUSTOMERS not in perms


def test_require_allows_when_permitted() -> None:
    dep = require(Permission.MANAGE_BRANDING)
    principal = _principal(Role.COMPANY_OWNER)
    assert dep(principal=principal) is principal


def test_require_denies_when_missing_permission() -> None:
    dep = require(Permission.MANAGE_BRANDING)
    with pytest.raises(HTTPException) as exc:
        dep(principal=_principal(Role.COMPANY_ADMIN))
    assert exc.value.status_code == 403


def test_require_denies_unknown_role() -> None:
    dep = require(Permission.VIEW_DASHBOARD)
    with pytest.raises(HTTPException) as exc:
        dep(principal=_principal("NONSENSE"))
    assert exc.value.status_code == 403
