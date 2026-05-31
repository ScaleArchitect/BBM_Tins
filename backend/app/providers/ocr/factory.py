"""OCR provider factory — selects implementation from settings (IA-08)."""

from __future__ import annotations

from app.core.config import Settings
from app.providers.ocr.base import OCRProvider


def build_ocr_provider(settings: Settings) -> OCRProvider:
    provider = settings.ocr_provider.lower()
    if provider == "local":
        from app.providers.ocr.local import LocalOCRProvider

        return LocalOCRProvider()
    if provider == "azure":
        from app.providers.ocr.azure_doc_intelligence import AzureDocIntelligenceProvider

        return AzureDocIntelligenceProvider()
    raise ValueError(f"Unknown OCR_PROVIDER: {settings.ocr_provider!r}")
