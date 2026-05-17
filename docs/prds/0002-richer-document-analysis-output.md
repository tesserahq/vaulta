## Problem Statement

When a document is analyzed by any of the pluggable providers (AWS Textract, Google Document AI, Claude Vision), the service throws away most of the data the provider returns. Only a small, hardcoded set of field names survives into `extracted_data.fields`. Fields outside that whitelist are silently dropped — regardless of the document type. For a credit card scan via Textract, for example, 21 fields are returned by the provider but only 3 are surfaced; the card number, expiration date, and CVV are lost entirely because they appear in the raw OCR layer (`Blocks`), not in `IdentityDocumentFields`.

This matters because the primary consumer of `extracted_data` is an LLM pipeline. LLMs can tolerate heterogeneous field names and interpret raw OCR text — they do not need a rigid, closed schema. The current approach optimises for schema stability at the cost of completeness, which is the wrong trade-off for this use case.

There are two compounding issues:

1. **Field filtering** — each provider adapter maintains a `_FIELD_MAP` and silently drops any field the provider returns that is not in the map.
2. **OCR layer ignored** — Textract (and similar providers) also return raw OCR lines with positional data. These lines often contain values — card numbers, phone numbers, dates — that are never present in the structured field layer. They are discarded.

Additionally, the `document_type` field is constrained to a closed enum. When Textract returns `"DRIVER LICENSE FRONT"` as the ID type, the adapter maps it to `"unknown"` because the exact string is not in the map. Similarly, the `partial` flag is computed from a hardcoded list of "expected" fields per document type, which is meaningless for unsupported document types and misleading for LLM consumers that can judge completeness themselves.

## Solution

Extend the `AnalysisResult` schema and update each provider adapter to surface all data the provider returns, with no silent dropping:

- **Fields**: pass every non-empty field through. Where a canonical mapping exists (e.g. `FIRST_NAME` → `given_names`), apply it. For any field the adapter does not recognise, use the raw provider key (lowercased, snake_cased) as the field name.
- **OCR lines**: add an `ocr_lines` list to `AnalysisResult`. Each element is a `{text, confidence}` pair. Textract populates this from `Blocks[LINE]`; Google DAI from its text segments; Claude Vision from a prompt addition.
- **`document_type`**: remove the closed enum constraint. Pass the provider's raw classification string through (applying a best-effort normalisation map, but not falling back to `"unknown"` when the map has no match).
- **`partial` flag**: drop it. Consumers (LLM pipelines) can decide completeness based on whichever fields they require.

All changes are backward-compatible in deployment terms — all existing consumers are internal.

## User Stories

1. As a developer consuming `extracted_data`, I want all non-empty fields the provider detected to appear in `fields`, so that the LLM downstream has access to the full document data without me having to parse `raw_response`.
2. As a developer consuming `extracted_data`, I want fields that have no canonical name to appear under their raw provider key (e.g. `expiration_date`, `class`, `state_in_address`), so that no data is silently lost.
3. As a developer consuming `extracted_data`, I want a top-level `ocr_lines` list of detected text with confidence scores, so that values present only in the raw OCR layer (card numbers, phone numbers, free-form addresses) are accessible without parsing `raw_response`.
4. As a developer consuming `extracted_data`, I want `document_type` to reflect what the provider actually detected (e.g. `"drivers_license_front"`, `"credit_card"`), not collapsed to `"unknown"` when the exact string is not in a hardcoded map.
5. As a developer consuming `extracted_data`, I want the `partial` flag removed, so that I am not misled by a flag computed from a hardcoded expected-field list that has no meaning for unsupported document types.
6. As an LLM pipeline receiving extracted data, I want complete field coverage, so that I can perform operations (name verification, expiry checks, address extraction) without instructing users to re-upload documents that were already successfully scanned.
7. As an LLM pipeline receiving extracted data, I want `ocr_lines` available, so that I can extract values like card numbers or insurance IDs that structured field extraction misses.
8. As an LLM pipeline receiving extracted data, I want `document_type` to be descriptive rather than `"unknown"`, so that I can branch my processing logic correctly without having to infer the type from field names.
9. As a developer adding a new provider adapter, I want a clear contract in `base.py` that requires passing all fields through, so that future adapters do not accidentally replicate the silent-drop pattern.
10. As a developer maintaining the Textract adapter, I want `"DRIVER LICENSE FRONT"` to map to a meaningful `document_type` string instead of `"unknown"`, so that credit-card and driving-licence scans are correctly identified.
11. As a developer maintaining the Claude Vision adapter, I want the extraction prompt updated to request all visible fields and an `ocr_lines` array, so that Claude returns richer data without me needing to parse the image myself.
12. As a developer maintaining the Google DAI adapter, I want all entity types surfaced, not just those in `_FIELD_MAP`, so that provider-specific fields (e.g. `sex`, `issuing_country`, `mrz_code`) survive into the response.
13. As a QA engineer, I want unit tests for each provider adapter's `_adapt` function using real fixture responses, so that I can verify field pass-through and OCR extraction without calling live APIs.

## Implementation Decisions

### Schema changes (`AnalysisResult`)

- Add `OcrLine` model: `{ text: str, confidence: float }`.
- Add `ocr_lines: list[OcrLine]` field to `AnalysisResult`, defaulting to an empty list.
- Change `document_type: str` — remove any enum constraint. The field is already typed as `str`; enforce no closed vocabulary at the model level.
- Remove the `partial: bool` field from `AnalysisResult`.
- Remove `EXPECTED_FIELDS_BY_TYPE` dict and `is_partial()` function from `base.py`.

### Textract adapter

- Replace the `_FIELD_MAP` whitelist approach with a pass-through: iterate all `IdentityDocumentFields`, apply the canonical mapping where it exists, otherwise snake_case the raw `Type.Text` value as the field name. Skip fields where `ValueDetection.Text` is empty.
- Expand `_DOCTYPE_MAP` to use prefix/substring matching (e.g. `"DRIVER LICENSE"` matches `"DRIVER LICENSE FRONT"`), and for unrecognised types pass the raw value through as a normalised snake_case string rather than `"unknown"`.
- Extract `Blocks` where `BlockType == "LINE"` into `ocr_lines`, mapping `Text` and `Confidence / 100.0`.

### Google DAI adapter

- Replace the `_FIELD_MAP` whitelist with pass-through: for each entity, apply canonical mapping where it exists, otherwise use `entity.type_` (already lowercased) as the field name. Keep `document_type` entity handling unchanged.
- For `ocr_lines`: use the document's raw text split into lines (Google DAI exposes `document.text`); confidence can be 1.0 as a placeholder since per-line confidence is not natively available.

### Claude Vision adapter

- Update `_USER_PROMPT` to: (a) remove the fixed list of valid field names, (b) instruct Claude to extract all visible fields using snake_case names, (c) add an `ocr_lines` key to the expected JSON structure (array of `{ text, confidence }` objects for all visible text lines).
- Update `_adapt` to read `ocr_lines` from the response and populate `AnalysisResult.ocr_lines`.

### `is_partial` removal

- Delete `is_partial()` from `base.py` and all call sites in adapters.
- Remove `partial` from all `AnalysisResult(...)` constructor calls.

### No changes to

- `StorageFactory`, `AnalysisFactory`, routers, repositories, or the upload service — the `AnalysisResult` is consumed opaquely by callers.
- The `raw_response` field — it stays as-is.

## Testing Decisions

Good tests for this feature test the `_adapt()` function in each provider adapter in isolation, using fixture data (real provider responses saved as JSON/dict), without calling live APIs. They assert on the output `AnalysisResult` fields — not on internal implementation details like which map was consulted.

**What makes a good test here:**
- Feed a realistic fixture response into `_adapt()` and assert that specific expected fields appear in `result.fields` and `result.ocr_lines`.
- Assert that fields the provider returned but had no canonical mapping still appear (using their raw key).
- Assert that empty-value fields are excluded.
- Assert that `document_type` reflects the provider's classification, not `"unknown"`, for known-but-previously-unmapped types like `"DRIVER LICENSE FRONT"`.
- Do not assert on internal state (`_FIELD_MAP`, iteration order, etc.).

**Modules to test:**

- `TextractAnalysisBackend._adapt()` — use the `docs/data/aws_textract.json` fixture as the input; this is the response for the credit card scan and provides full coverage of the new pass-through and OCR extraction logic.
- `GoogleDAIAnalysisBackend._adapt()` — use a minimal synthetic fixture mirroring the Google DAI entity structure.
- `ClaudeVisionAnalysisBackend._adapt()` — use a synthetic dict mirroring the updated JSON structure Claude will return (including `ocr_lines`).

**Prior art:** `tests/app/services/test_asset_upload.py` shows the pattern: construct dependencies (or mock them) directly in the test, call the function, assert on the result. Follow the same style — no `TestClient`, no DB, pure unit tests for the adapter layer.

## Out of Scope

- Surfacing `ocr_lines` in the API response schema documentation or OpenAPI spec update (follow-up).
- Adding support for new document types beyond what providers already detect (e.g. insurance cards, tax forms).
- Confidence thresholds or field filtering based on confidence score.
- Multi-page document support (Textract currently receives a single JPEG page).
- Changes to how `raw_response` is stored or exposed.
- Changes to the `AnalysisConfig` model, provider factory, or router layer.
- Per-word bounding-box data from Textract `Blocks[WORD]` — line-level OCR is sufficient.

## Further Notes

- The `docs/data/aws_textract.json` file contains a real Textract response for a credit card scan (CaixaBank Visa). It should be promoted to a test fixture under `tests/fixtures/` or `tests/app/services/` so that the Textract adapter unit test can load it directly.
- The Claude Vision prompt change carries a small regression risk: removing the fixed field-name list may produce inconsistent key casing across calls. The updated prompt should explicitly instruct Claude to use `snake_case` for all field names.
- Google DAI does not expose per-line OCR confidence scores natively. Using `1.0` as a placeholder is acceptable since the text content (not confidence) is what the LLM consumes.
- Once `partial` is removed from the schema, any existing assets in the database with `extracted_data.partial` in their JSON column will still have the key — this is harmless since the field is simply no longer read by the application.
