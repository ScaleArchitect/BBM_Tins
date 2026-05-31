# 07 — OCR Processing Design

Covers output section **14**. Provider-abstracted, async, separates raw OCR from parsed fields from customer-confirmed values.

## 14.1 Provider interface

```python
# providers/ocr/base.py
class OCRExtraction(BaseModel):
    provider: str
    model_version: str | None
    raw: dict                       # full provider response (-> ocr_results.raw_json)
    text: str | None                # concatenated text (local path)
    fields: dict[str, FieldValue]   # normalized field map (key -> value+confidence+bbox)
    overall_confidence: float | None
    pages: int
    duration_ms: int

class FieldValue(BaseModel):
    value: str | None
    confidence: float | None        # 0..1, None if provider gives none
    bbox: list[float] | None

class OCRProvider(Protocol):
    async def extract(self, pdf_bytes: bytes, cert_type: CertType) -> OCRExtraction: ...
```

The **parser** (domain) maps `OCRExtraction.fields` (provider-specific keys) → canonical cert fields. Providers never know about our domain schema; parsers never call providers.

## 14.2 Pipeline (worker task `ocr_extract`)

```
1. Load submission (system ctx, set company_id), set ocr_status=PROCESSING.
2. storage.get(file.storage_key) -> pdf_bytes.
3. extraction = ocr_provider.extract(pdf_bytes, cert_type)
4. persist ocr_results row (raw_json, provider, confidence, duration); mark is_current.
5. parsed = parser_registry[cert_type, format_version].parse(extraction)
        -> canonical field map + per-field confidence
6. validation:
     trn_norm   = normalize_trn(parsed.trn)            # strip non-digits
     trn_valid  = validate_trn(trn_norm)               # 15 digits, prefix rule
     tin        = derive_tin(trn_norm)                 # first 10 digits
     is_group   = detect_group_cert(extraction, parsed)
     dup        = repo.find_duplicates(company_id, trn_norm, tin, exclude=submission_id)
     mismatch   = integrity_check(parsed, business_customer.expected_*)
7. write submission.extracted_data = parsed, field_confidence, derived(trn_norm,tin),
   is_group_certificate, flags=[...]
8. decide status:
     group cert & policy REJECT -> status=REJECTED (+flag GROUP_CERT)
     trn invalid                -> flag INVALID_TRN (still UNDER_REVIEW for manual fix)
     else                       -> status=UNDER_REVIEW, ocr_status=COMPLETED
9. audit OCR_COMPLETED. (on exception -> ocr_status=FAILED, retry; final -> EXTRACTION_FAILED)
```

## 14.3 Local OCR strategy (`local.py`)
- **Digital-native first:** PyMuPDF / pdfplumber extract embedded text + layout. Most FTA certs are digital PDFs → high accuracy, no image OCR needed, fast.
- **Scanned fallback:** if extracted text is empty/low, rasterize pages (PyMuPDF) → Tesseract OCR with `eng+ara` traineddata. Arabic requires the `ara` pack + proper preprocessing (deskew, threshold).
- **Confidence:** Tesseract word confidences aggregated per field; pdfplumber path assigns high confidence to anchored regex matches, lower to fuzzy. Confidence is best-effort; UI treats `None` as "verify".
- Runs fully offline inside the worker container.

## 14.4 Azure Document Intelligence strategy (`azure_doc_intelligence.py`)
- Use a **custom model** trained on FTA VAT + CT certificate samples (one model per type/format) for keyed field extraction with native confidence + bounding boxes; fall back to the prebuilt `read`/`layout` model + parser for unknown layouts.
- Returns the same `OCRExtraction` shape; `raw_json` keeps the full Azure response for audit/repro.
- Region per OQ4 (keep in UAE / in-region or self-hosted fallback).

## 14.5 Field extraction & template parsing
- **Parser registry** keyed by `(cert_type, format_version)`. Each parser:
  - knows the labels/anchors for that certificate format (EN + AR labels),
  - extracts via labelled-region (Azure) or anchor+regex (local),
  - returns canonical fields: `trn, legal_name_en, legal_name_ar, trade_license_number, issuing_authority/trade_license_authority, registration_date, tax_period_start_date(CT), registered_address, emirate, business_activity(VAT), legal_form(CT), tax_group`.
- **Modular templates** address the BRD risk "FTA changes certificate format": add a new parser/format_version without touching the pipeline.

## 14.6 Validation logic (canonical, in `validation/`)
```python
def normalize_trn(raw: str | None) -> str | None:
    return re.sub(r"\D", "", raw) if raw else None      # strip spaces/dashes

def validate_trn(trn: str | None) -> bool:
    return bool(trn) and len(trn) == 15 and trn.isdigit() # (+ optional '100' prefix rule per OQ3)

def derive_tin(trn: str | None) -> str | None:
    return trn[:10] if trn and len(trn) == 15 else None   # business rule (OQ3)

def detect_group_cert(extraction, parsed) -> bool:
    # heuristic (OQ2): tax-group section / member list / title keywords
    return parsed.tax_group_present or has_keywords(extraction.text, GROUP_CERT_MARKERS)

def integrity_check(parsed, expected) -> list[Flag]:
    # OQ1: soft compare confirmed vs master data; returns warn flags, never blocks
```
All pure, deterministic, unit-tested with real certificate fixtures.

## 14.7 Confidence handling & low-confidence warnings
- Per-field confidence stored in `field_confidence` (JSONB). UI highlights fields `< 0.85` (configurable) in amber and pre-focuses them.
- Flag `LOW_CONFIDENCE` added per low field; surfaced in `flags` and dashboard `flagged` bucket if any critical field (TRN/legal name) is low.

## 14.8 Customer correction workflow
- Review form is seeded from `extracted_data`. Edits write to `confirmed_data` via `PATCH` (extracted is never mutated).
- On each save, server **recomputes** TRN/TIN/duplicate/integrity flags from `confirmed_data` so warnings reflect the latest values.
- On `confirm`, searchable typed columns (`trn_normalized`, `tin`, `legal_name_*`, dates) are populated from `confirmed_data`; `submitted_at` set; status → `SUBMITTED` (or `FLAGGED` if open critical flags + policy allows confirm with flags).

## 14.9 Failed OCR & reprocessing
- `EXTRACTION_FAILED` shows the customer a clear retry CTA; admin can also trigger reprocess.
- Reprocess re-enqueues `ocr_extract`; inserts a new `ocr_results` row (`is_current`), preserving prior raw output.
- Persistent failures: customer may still enter fields manually (form starts blank) and confirm — nothing is lost; the original PDF is always stored.

## 14.10 Group VAT certificate handling (FR-028)
- On detection: if `company_settings.group_cert_policy = REJECT` → submission `REJECTED`, API returns `409 GROUP_CERT_REJECTED`, UI shows the standalone-cert modal. If `WARN` → allow with a prominent `GROUP_CERT` flag. Default REJECT.
