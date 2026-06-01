"""Company-related enums (see docs/architecture/03 §9.2)."""

from __future__ import annotations

from enum import StrEnum


class CompanyStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"


class SubscriptionStatus(StrEnum):
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"


class GroupCertPolicy(StrEnum):
    REJECT = "REJECT"
    WARN = "WARN"
