## Problem Statement

Vaulta's document analysis capability is implemented as a single, monolithic `DocumentAnalyzer` class that is tightly coupled to a deterministic, local-only pipeline (PDF417 barcode → MRZ parsing → OCR heuristics via PaddleOCR). This pipeline cannot be swapped for a different provider without touching the core service logic. There is no way to route documents to a privacy-conscious provider (e.g. AWS Bedrock), use a specialized document AI service like AWS Textract for higher accuracy, or experiment with new providers without modifying shared code. Adding or removing a provider requires understanding the entire analyzer codebase rather than following a well-known extension point.

The output schema is also tightly coupled to the pipeline internals, mixing confidence signals from different detection mechanisms (barcode, MRZ, OCR) in a way that is difficult for callers to interpret uniformly.

## Solution

Replace the `DocumentAnalyzer` class with a pluggable provider architecture that mirrors the existing storage backend pattern (`app/storage/`). Each document analysis provider implements a shared abstract interface. A factory selects the active provider at runtime based on a database-backed `AnalysisConfig` model, which supports a global default and per-request overrides via a `config_id`. Providers ship as first-class modules (AWS Textract, Google Document AI, Claude vision) and can be added or removed by implementing the interface, adding a factory branch, and adding config fields — no other code changes required.

The output schema is redesigned as a flat, provider-agnostic structure with per-field confidence scores inline, making results consistent regardless of which provider produced them.

## User Stories

1. As a developer integrating Vaulta's document analysis, I want a consistent output schema regardless of which provider extracted the data, so that I don't need to write provider-specific parsing logic in my application.
2. As a developer, I want each extracted field to carry its own confidence score, so that I can decide which fields to trust without inspecting a separate confidence map.
3. As a developer, I want to upload a document and receive `partial: true` in the response when the provider could not extract all fields with high confidence, so that I know to prompt the user to verify the result.
4. As a developer, I want to upload a document with `extract_data=false` and skip analysis entirely, so that I can control when the latency cost of analysis is incurred.
5. As a developer, I want to upload a document with `extract_data=true` and receive the extracted fields inline in the upload response, so that I don't need a separate polling call for simple use cases.
6. As an API consumer, I want to pass an optional `config_id` at upload time to override the default analysis configuration, so that I can route sensitive documents to a privacy-conscious provider without changing the default for all uploads.
7. As a platform administrator, I want a default `AnalysisConfig` row in the database that all uploads use when no `config_id` is specified, so that the system works out of the box without per-request configuration.
8. As a platform administrator, I want to create additional `AnalysisConfig` rows pointing to different providers (Textract, Google Document AI, Claude on Bedrock), so that callers can opt into a specific provider for specific document types or compliance requirements.
9. As a platform administrator, I want to update or delete non-default `AnalysisConfig` rows without affecting the default, so that I can iterate on provider selection without disrupting existing integrations.
10. As a platform administrator, I want exactly one `AnalysisConfig` marked as `is_default=true` at all times, so that there is always a well-defined fallback when no `config_id` is provided.
11. As a developer adding a new provider, I want a clear, minimal extension point — implement one interface, add one factory branch, add config fields — so that I can ship a new provider without modifying the core upload or analysis logic.
12. As a developer removing a deprecated provider, I want to delete the provider module and remove the factory branch without touching anything else, so that the removal is contained and safe.
13. As a developer, I want to classify uploaded documents as passport, driver's license, national ID, social security card, or unknown, so that downstream consumers can apply document-type-specific business logic.
14. As a developer, I want the analysis result to include a `document_type_confidence` score alongside the classified type, so that I can handle low-confidence classifications differently (e.g. prompt for manual review).
15. As a developer, I want the provider that produced the result identified in the output (e.g. `"provider": "textract"`), so that I can correlate results to the configuration used and debug provider-specific issues.
16. As a developer uploading a large file (e.g. a 15MB passport scan), I want the system to automatically resize the image before sending it to the provider, so that the upload does not fail due to provider input size limits.
17. As a developer uploading a multi-page PDF, I want the system to extract only the first page for analysis, so that analysis is fast and focused on the document identity page.
18. As a developer writing tests for my integration, I want to inject a mock `DocumentAnalysisBackend` through the same dependency injection mechanism used for storage backends, so that I can test my upload flows without making real provider API calls.
19. As a developer, I want the upload to succeed even if document analysis fails (analysis errors are non-fatal), so that a transient provider outage does not prevent users from uploading files.
20. As a developer, I want `extracted_data` to be `null` in the upload response when analysis was skipped or failed, so that I can distinguish a successful extraction from a missing one without inspecting error fields.
21. As a developer, I want image files (PNG, JPG, GIF) and PDFs to all be supported as analysis inputs, so that I don't need to pre-convert files before uploading.

## Implementation Decisions

### New module: `app/services/analysis/`

> **Implementation note (2026-05-17)**: A `"local"` provider that wraps the existing `DocumentAnalyzer` is included alongside the three cloud providers. It adapts the legacy output schema to `AnalysisResult` and serves as a development fallback. `settings.analysis_backend` defaults to `"local"`; the DB-seeded default config uses `"textract"` for production. HTTP CRUD routes for `AnalysisConfig` management are implemented at `/analysis-configs`. `google-cloud-documentai` and `anthropic` have been added to `pyproject.toml`.

A new module under `app/services/`, with the same layout as `app/storage/` (base, providers, factory):

- **`base.py`** — defines the `DocumentAnalysisBackend` ABC with a single abstract method `analyze(file_bytes: bytes, content_type: str) -> AnalysisResult`, plus the `AnalysisResult` and `FieldValue` output schema types as Pydantic models. This is the only contract that providers and callers depend on.
- **`preprocessor.py`** — a standalone, stateless module that normalizes any supported input (PNG, JPG, GIF, PDF) into a JPEG byte payload ready for the provider. Handles PDF first-page extraction and image resizing to a configurable maximum resolution (default: 2048px longest side). This logic is ported and simplified from the existing `DocumentAnalyzer._iter_pages_to_jpegs()`.
- **`local.py`** — Local provider wrapping the existing `DocumentAnalyzer`. Adapts its `{document_type, attributes, confidences, signals}` output to the `AnalysisResult` schema. Provider key: `"local"`. Used for development without cloud credentials; `settings.analysis_backend` defaults to `"local"`.
- **`textract.py`** — AWS Textract provider implementation. Uses the Textract `AnalyzeID` API for identity document analysis. Reuses existing `aws_access_key_id`, `aws_secret_access_key`, and `s3_region_name` settings.
- **`google_dai.py`** — Google Document AI provider implementation. Uses the Document AI `process_document` API with an ID proofing or form parser processor.
- **`claude_vision.py`** — Claude vision LLM provider implementation. Supports both Anthropic direct API and AWS Bedrock routing, selected by whether a `bedrock_region` is configured.
- **`factory.py`** — `AnalysisFactory` singleton. Mirrors `StorageFactory` exactly: `get_backend(provider: str | None = None) -> DocumentAnalysisBackend`, `reset()` for test isolation. When `provider` is `None`, returns the singleton default (from `analysis_backend` config). When `provider` is provided (e.g. from an `AnalysisConfig` row), creates an instance of that specific provider.
- **`__init__.py`** — re-exports `DocumentAnalysisBackend`, `AnalysisResult`, `FieldValue`, and all concrete providers.

### Output schema (`AnalysisResult`)

```
document_type: str              # "passport" | "drivers_license" | "national_id" | "social_security_card" | "unknown"
document_type_confidence: float # 0.0–1.0
fields: dict[str, FieldValue]   # extracted fields, keyed by field name
partial: bool                   # true when one or more fields could not be extracted
provider: str                   # provider identifier, e.g. "textract"
```

`FieldValue`:
```
value: str | None    # normalized value, or null if not extracted
confidence: float    # 0.0–1.0
```

Field name vocabulary (providers must map to these canonical names):
`surname`, `given_names`, `middle_name`, `date_of_birth`, `expiration_date`, `document_number`, `address`, `city`, `state`, `postal_code`, `sex`, `nationality`, `issuing_state`, `ssn`

Not all fields are present for all document types. Providers omit fields that are not applicable rather than returning null.

### `AnalysisConfig` DB model

New table `analysis_configs` with columns:
- `id` — UUID primary key
- `name` — human-readable label
- `provider` — string matching a factory key (e.g. `"textract"`, `"google_dai"`, `"claude"`)
- `is_default` — boolean; exactly one row must be true at all times (enforced at the repository layer)
- `provider_params` — JSONB; optional provider-specific overrides (e.g. specific model name, processor ID, region)
- `created_at`, `updated_at` — timestamps (via `TimestampMixin`)

A new `AnalysisConfigRepository` provides: `get_default()`, `get_by_id(id)`, `create(data)`, `update(id, data)`, `delete(id)`. Setting a new default atomically unsets the previous default row in the same transaction.

A database migration creates the table and inserts the initial default row (`provider="textract"`, `is_default=true`).

### Upload service changes

`upload_asset()` gains an `analysis_backend: DocumentAnalysisBackend | None = None` parameter (injected like `storage`). When `extract_data=True` and `analysis_backend` is not `None`, the service calls `await analysis_backend.analyze(file_bytes, content_type)` and stores the serialized `AnalysisResult` in `Asset.extracted_data`. Analysis failures are caught and logged; the upload continues with `extracted_data=null`.

### Upload router changes

The `/assets/upload` endpoint gains an optional `config_id: UUID | None = Form(None)` parameter. When provided, the router resolves the `AnalysisConfig` row and passes the corresponding backend to `upload_asset()`. When absent, the global default config is used. A `get_analysis_backend(config_id, db)` helper in `app/routers/utils/dependencies.py` encapsulates the resolution logic (DB default → settings singleton fallback). The backend is only resolved when `extract_data=true`; otherwise `None` is passed and analysis is skipped.

### Analysis config admin routes

`GET/POST /analysis-configs` and `GET/PATCH/DELETE /analysis-configs/{id}` provide full CRUD for `AnalysisConfig` rows, authenticated via `get_current_user`.

### Config additions

New settings in `app/config.py`:
- `analysis_backend: str` — default provider key (`"local"` for dev, override to `"textract"` in prod via env), maps to env `ANALYSIS_BACKEND`
- `analysis_max_image_px: int` — resize ceiling in pixels (`2048`), maps to env `ANALYSIS_MAX_IMAGE_PX`
- `google_dai_processor_id: Optional[str]` — Google Document AI processor resource name
- `google_application_credentials: Optional[str]` — path to GCP service account JSON
- `anthropic_api_key: Optional[str]` — Anthropic direct API key
- `bedrock_region: Optional[str]` — if set, Claude provider routes through AWS Bedrock instead of Anthropic direct

AWS credentials (`aws_access_key_id`, `aws_secret_access_key`, `s3_region_name`) are reused for Textract.

### Deprecation

`app/processing/document_analyzer.py` is kept intact but no longer called by `upload_asset()`. It will be removed in a follow-up once callers have migrated to the new schema and no existing `extracted_data` records depend on its output format.

## Testing Decisions

Good tests verify observable behavior through the public interface — they do not assert on internal implementation details (private methods, intermediate state, specific library calls). Each test should be readable as a specification: given this input, assert this output or this side effect.

### `DocumentAnalysisBackend` (base interface + mock)

Test that a `MockDocumentAnalysisBackend` implementing the interface correctly satisfies the contract: `analyze()` returns a well-formed `AnalysisResult`, field values are accessible, `partial` is set correctly when fields are missing. This also serves as a reference implementation for other test suites that need to inject a fake backend.

Prior art: `MockStorageBackend` in `tests/app/services/test_asset_upload.py`.

### `AnalysisPreprocessor`

Test the preprocessing module in isolation with real byte payloads:
- A large image above the resize ceiling is downsampled to ≤ max_image_px on its longest side.
- A small image below the ceiling passes through unchanged.
- A GIF input produces a valid JPEG output.
- A single-page PDF produces a valid JPEG output.
- A multi-page PDF produces a JPEG from the first page only.
- An unsupported format raises a well-typed exception (not a silent failure).

### `AnalysisFactory`

Test factory instantiation behavior:
- `get_backend(provider="textract")` returns a `TextractBackend` instance.
- `get_backend(provider="google_dai")` returns a `GoogleDAIBackend` instance.
- `get_backend(provider=None)` returns the backend matching `settings.analysis_backend`.
- `get_backend(provider="unknown")` raises a `ValueError`.
- The singleton is reused across calls; `reset()` clears it.
- Provider instances are not created until `get_backend()` is called (lazy initialization).

### `AnalysisConfigRepository`

Test CRUD operations and invariants:
- `get_default()` returns the row marked `is_default=true`.
- Setting a new default atomically unsets the previous default (no two rows with `is_default=true`).
- `delete()` of a non-default row succeeds.
- `delete()` of the default row raises an error (cannot delete the active default).
- `get_by_id()` of a non-existent ID raises a well-typed not-found exception.

Prior art: `tests/app/repositories/test_asset_repository.py` for repository test patterns.

## Out of Scope

- **Async analysis path** (`extract_data="async"` returning a job ID and writing results back later). The upload will remain synchronous; async job queue integration is a separate PRD.
- **Migration of existing `extracted_data` records**. Old records written by the legacy `DocumentAnalyzer` are left as-is. No schema migration of existing data.
- **Provider-level confidence calibration** (normalizing confidence scores across providers to a common scale).
- **Multi-page PDF analysis** (analyzing more than the first page per document).
- **Webhook or polling API for analysis status**. Analysis result is always returned inline in the upload response.
- **UI changes** to display extracted fields or configure `AnalysisConfig` rows from the front end.
- **Rate limiting or quota management** per provider.
- **Automatic fallback** from a failing provider to another provider at runtime.

## Further Notes

- The `AnalysisConfig.provider_params` JSONB field is intentionally loose-typed to allow provider-specific configuration (e.g. a specific Document AI processor version, or a non-default Claude model) without requiring schema changes when new providers are added.
- Textract's `AnalyzeID` API is purpose-built for US identity documents and is the accuracy-first default. For international documents or novel document types, the `claude_vision` provider config should be used via `config_id` override.
- The `preprocessor.py` module should be dependency-injectable in tests (accept `max_image_px` as a constructor argument, not read from settings directly), to allow testing resize behavior at arbitrary thresholds without mocking the settings layer.
- The legacy `DocumentAnalyzer` uses synchronous blocking calls to PaddleOCR and passporteye. The new `analyze()` method is async throughout; providers that use synchronous SDKs (e.g. boto3 for Textract) must wrap calls in `asyncio.to_thread()` to avoid blocking the event loop.
