"""Local OCR provider (Sprint 0 stub).

Implemented in Sprint 6: PyMuPDF/pdfplumber for digital-native text with a
Tesseract (eng+ara) fallback for scanned pages. Runs fully offline in the worker.
"""

from __future__ import annotations

from app.providers.ocr.base import CertType, OCRExtraction


class LocalOCRProvider:
    async def extract(self, pdf_bytes: bytes, cert_type: CertType) -> OCRExtraction:
        raise NotImplementedError("LocalOCRProvider — implemented in Sprint 6.")
