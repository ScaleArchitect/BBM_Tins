"""Unit tests for tenant context + repository guard (no DB required)."""

from __future__ import annotations

import uuid

import pytest

from app.core.repository import TenantRepository
from app.core.tenancy import get_current_company_id, require_company_id, set_current_company_id
from app.domains.admins.models import CompanyAdmin


class _AdminRepo(TenantRepository[CompanyAdmin]):
    model = CompanyAdmin


def test_require_company_id_raises_without_context() -> None:
    set_current_company_id(None)
    with pytest.raises(RuntimeError):
        require_company_id()


def test_set_and_get_company_id() -> None:
    cid = uuid.uuid4()
    set_current_company_id(cid)
    try:
        assert get_current_company_id() == cid
    finally:
        set_current_company_id(None)


def test_repository_company_id_requires_context() -> None:
    set_current_company_id(None)
    repo = _AdminRepo(session=None)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        _ = repo.company_id


def test_repository_rejects_non_tenant_model() -> None:
    from app.domains.companies.models import Company

    class _BadRepo(TenantRepository):  # Company is not tenant-scoped
        model = Company

    with pytest.raises(TypeError):
        _BadRepo(session=None)  # type: ignore[arg-type]
