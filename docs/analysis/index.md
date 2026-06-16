# Analysis

Analysis extracts structured data from an uploaded document — fields like given name, surname, date of birth, document number — along with raw OCR lines. It is triggered by passing `extract_data=true` on `POST /assets`.

## Output shape

A successful extraction populates `asset.extracted_data`:

```json
{
  "document_type": "passport",
  "document_type_confidence": 0.98,
  "provider": "textract",
  "fields": {
    "given_names":     { "value": "Jane",       "confidence": 0.99 },
    "surname":         { "value": "Smith",       "confidence": 0.99 },
    "date_of_birth":   { "value": "1990-05-15",  "confidence": 0.97 },
    "expiration_date": { "value": "2030-05-14",  "confidence": 0.98 },
    "document_number": { "value": "AB1234567",   "confidence": 0.99 }
  },
  "ocr_lines": [
    { "text": "JANE SMITH",  "confidence": 0.99 },
    { "text": "1990-05-15", "confidence": 0.97 }
  ]
}
```

- **`fields`** — structured key/value pairs with confidence. Provider-specific field names are normalized to canonical names (see [Providers](providers.md#canonical-field-names)). Only non-empty values are included.
- **`ocr_lines`** — every line of text detected on the document, in detection order. Captures values that may not appear in `fields` (card numbers, free-form text, etc.).
- **`document_type`** — normalized to a canonical string where known (`"DRIVER LICENSE FRONT"` → `"drivers_license"`); unknown types are passed through as snake_case.

## How the provider is selected

1. The caller optionally passes `config_id` (UUID) on upload.
2. The router calls `resolve_analysis_config(config_id, db)` to load the `AnalysisConfig` row, falling back to the default config when `config_id` is omitted.
3. If `config.provider == "modela"`, a `ModelaAnalysisProcessor` is used — see [Modela](../modela.md).
4. Otherwise, `AnalysisFactory.get_backend(config.provider, config.provider_params)` returns the right `DocumentAnalysisBackend`, which is wrapped in an `AnalysisProcessor`.

## Image preprocessing

Before calling any provider, the image is:

1. Decoded from its original format (JPEG, PNG, GIF, PDF).
2. Resized so its longest side is at most `ANALYSIS_MAX_IMAGE_PX` (default 2048 px).
3. Re-encoded as JPEG.

PDFs are rasterized to JPEG from the first page (requires `pdf2image` and `poppler`).

## Supported input formats

| Format | Notes |
|---|---|
| JPEG / JPG | Native; no conversion. |
| PNG | Converted to JPEG before submission. |
| GIF | First frame extracted and converted to JPEG. |
| PDF | First page rendered at 300 DPI. Requires `pdf2image` and `poppler`. |
