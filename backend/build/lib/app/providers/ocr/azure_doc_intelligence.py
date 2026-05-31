"""Azure AI Document Intelligence OCR provider (Sprint 0 stub).

Implemented for Azure (Sprint 12), subject to the UAE-North residency decision
(OQ4). Custom FTA VAT/CT models with prebuilt read/layout fallback.
"""

from __future__ import annotations

from app.providers.ocr.base import CertType, OCRExtraction


class AzureDocIntelligenceProvider:
    def __init__(self, endpoint: str = "") -> None:
        self.endpoint = endpoint

    async def extract(self, pdf_bytes: bytes, cert_type: CertType) -> OCRExtraction:
        raise NotImplementedError("AzureDocIntelligenceProvider — implemented in Sprint 12.")
