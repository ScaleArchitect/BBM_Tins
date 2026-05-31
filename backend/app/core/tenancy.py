"""Request-scoped tenant context (see docs/architecture/02 §8.3, IA-01).

The current company/tenant id is stored in a ContextVar set by auth middleware
(added in Sprint 2). Tenant-aware repositories read it to scope every query and
to issue the RLS ``SET LOCAL``. Placeholder for Sprint 0.
"""

from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID

current_company_id: ContextVar[UUID | None] = ContextVar("current_company_id", default=None)


def set_current_company_id(company_id: UUID | None) -> None:
    current_company_id.set(company_id)


def get_current_company_id() -> UUID | None:
    return current_company_id.get()


def require_company_id() -> UUID:
    cid = current_company_id.get()
    if cid is None:
        raise RuntimeError("Tenant context is not set; refusing tenant-scoped operation.")
    return cid
