"""OCRProvider interface + extraction models (docs/architecture/07, IA-08).

Providers return a provider-agnostic ``OCRExtraction``; domain parsers map it to
canonical certificate fields. Raw provider output is preserved for audit/repro.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from pydantic import BaseModel


class CertType(str, Enum):
    VAT = "VAT"
    CT = "CT"


class FieldValue(BaseModel):
    value: str | None = None
    confidence: float | None = None
    bbox: list[float] | None = None


class OCRExtraction(BaseModel):
    provider: str
    model_version: str | None = None
    raw: dict = {}
    text: str | None = None
    fields: dict[str, FieldValue] = {}
    overall_confidence: float | None = None
    pages: int = 0
    duration_ms: int = 0


class OCRProvider(Protocol):
    async def extract(self, pdf_bytes: bytes, cert_type: CertType) -> OCRExtraction: ...
