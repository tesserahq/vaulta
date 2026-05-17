## Problem Statement

Legal and estate documents such as Wills can be tens of pages long. Once uploaded to Vaulta, the existing analysis pipeline extracts structured fields (names, dates, document number) and raw OCR lines — useful for identity documents, but not meaningful for dense prose documents where the value is the narrative content. There is currently no way to get a high-level, human-readable summary of what a document says without reading the entire file manually.

Google Document AI offered a summarization processor that appeared to fill this gap, but it is being deprecated (February 2026 release notes). The capability needs to live inside Vaulta itself, tied to providers it already controls.

## Solution

Add an optional `summarize=true` flag to the `POST /assets` upload endpoint, mirroring the existing `extract_data=true` pattern. When set, Vaulta generates a free-form prose summary of the document using Claude and stores it in a new encrypted `summary` column on the `assets` table. The summary is generated once at upload time and cached — subsequent reads return the stored text without re-calling Claude. Summaries are surfaced on the asset response alongside `extracted_data`.

Claude receives PDFs as native document blocks (no JPEG conversion) and images as image blocks, so the full content of multi-page documents is available in a single API call.

## User Stories

1. As an API consumer, I want to pass `summarize=true` when uploading a Will, so that I receive a summary of its contents without reading the full document.
2. As an API consumer, I want the summary to be available on the `GET /assets/{id}` response, so that I can retrieve it later without triggering a new Claude call.
3. As an API consumer, I want the summary to be generated in the same synchronous upload call as the file storage and analysis, so that I don't need to implement polling or webhooks to obtain it.
4. As an API consumer uploading a JPEG scan of a document, I want `summarize=true` to work the same way as for PDFs, so that I don't have to convert files before uploading.
5. As an API consumer, I want the summary to be a readable prose narrative (not a list of structured fields), so that I can pass it directly to an LLM downstream without further parsing.
6. As an API consumer, I want the upload to still succeed even if summary generation fails, so that a transient Claude API error does not cause me to lose the uploaded file.
7. As an API consumer, I want `summarize=true` and `extract_data=true` to be independently combinable, so that I can get both structured fields and a prose summary from a single upload.
8. As an API consumer, I want the summary to be encrypted at rest, so that sensitive legal content (beneficiaries, asset values) is protected in the same way as `extracted_data`.
9. As an LLM pipeline consuming the summary, I want a section-by-section prose summary, so that I can use it to answer questions about the document without processing the raw file.
10. As an LLM pipeline, I want the summary to be under the `summary` key on the asset response, so that I can distinguish it from the structured `extracted_data` fields.
11. As a developer uploading a large PDF Will, I want the system to send the PDF natively to Claude (not convert it to images), so that no content is truncated due to single-page JPEG conversion.
12. As a developer, I want `summarize=true` to reuse the same Claude API credentials already configured in `AnalysisConfig` or environment variables, so that I don't need to configure a second set of secrets.
13. As a developer, I want the summarization logic encapsulated in its own service module with a clean interface, so that I can test it without calling live APIs.

## Implementation Decisions

### New database column

- Add a `summary` column to the `assets` table using the same `EncryptedJSONB` type as `extracted_data`. Store the result as `{"text": "<prose>", "provider": "claude", "model": "<model-id>"}` to preserve provenance alongside the text.
- Column is nullable; `null` means no summary has been generated.
- Requires an Alembic migration.

### New summarization service

- Create a dedicated summarization service module (separate from the analysis pipeline) with a single async method: `summarize(file_bytes, content_type) -> SummaryResult`.
- `SummaryResult` is a Pydantic model with fields: `text: str`, `provider: str`, `model: str`.
- The service uses the Anthropic SDK directly (not the `ClaudeVisionAnalysisBackend`), because:
  - PDFs are sent as document blocks (`{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "..."}}`), bypassing the JPEG preprocessor entirely.
  - Images are sent as image blocks (same as the existing vision backend).
  - The prompt and output shape are different from the analysis prompt.
- The service is instantiated with an API key and model ID (sourced from existing Claude config). No new config table is needed.
- The summarization prompt instructs Claude to write a section-by-section prose summary in plain language. The prompt is hardcoded (not user-configurable in this iteration).

### Upload endpoint changes

- Add `summarize: bool = Form(False)` to `POST /assets`.
- After the existing analysis block, add a parallel try/except block for summarization. A summary failure must not fail the upload — mirror the `extract_data` error-handling pattern exactly.
- If `summarize=True`, instantiate the summarization service using the Claude credentials from the active `AnalysisConfig` (or fall back to `ANTHROPIC_API_KEY` env var). No separate `config_id` is needed — Claude credentials are shared.
- On success, call `asset_repository.update_asset(asset.id, AssetUpdate(summary=result.model_dump()))`.

### Asset model and schema changes

- Add `summary` column to the `Asset` ORM model.
- Add `summary: Optional[dict] = None` to the `Asset` Pydantic schema and `AssetUploadResponse`.
- `AssetUpdate` gains an optional `summary` field.

### No changes to

- `AnalysisConfig` table or factory — Claude credentials are reused as-is.
- The JPEG preprocessor — summarization bypasses it entirely for PDFs.
- The existing analysis pipeline — `extract_data` and `summarize` are independent.

### Claude PDF and image limits

- Claude accepts PDFs up to 32 MB and approximately 100 pages per document block.
- Files exceeding these limits will cause the Claude API call to fail. The try/except wrapper in the upload endpoint ensures the upload still succeeds; `summary` will be `null` on the asset.
- No automatic chunking is implemented in this iteration.

## Testing Decisions

Good tests for this feature call the summarization service's core function directly with fixture data, without invoking live APIs. They verify the output `SummaryResult` shape and that the Claude client receives the correct request structure.

**What makes a good test here:**
- Mock the Claude client (`anthropic.Anthropic` or the boto3 bedrock client) and assert that the message payload sent to Claude contains the correct content block type (document block for PDFs, image block for images).
- Assert that the returned `SummaryResult` has a non-empty `text` field and the expected `provider` and `model` values.
- Test that a non-PDF `content_type` produces an image block, not a document block.
- Do not test the specific wording of the summary or the Claude response — mock the response as a fixed string.

**Modules to test:**

- The summarization service's core adapt/build function — verify block type selection (PDF vs image) and result parsing from a mocked Claude response.
- The upload endpoint — verify that a summary failure does not change the HTTP response status and that `summary` is `null` when generation fails.

**Prior art:** `tests/app/services/test_analysis_adapters.py` shows the pattern for testing service-layer functions with fixture/mock data. `tests/app/services/test_asset_upload.py` shows how to test upload-level error handling with a mock storage backend.

## Out of Scope

- Re-generating a summary after initial creation (no `?refresh=true` or update endpoint in this iteration).
- Configurable summarization prompts per document type or per client.
- Asynchronous/background summarization (task queue, webhooks, polling endpoint).
- Chunking or summarization of PDFs larger than Claude's 32 MB / ~100 page limit.
- A separate `SummaryConfig` table or per-upload model/provider selection for summarization.
- Summarization of documents already uploaded (retroactive summarization via a dedicated endpoint).
- Streaming the summary response to the caller.

## Further Notes

- The Google Document AI summarization processor that prompted this feature is deprecated as of February 2026. This implementation does not depend on Google DAI at all.
- Claude's native PDF support means the full document text is available to the model in a single call — no page-by-page iteration or OCR preprocessing is needed for PDFs.
- Wills and estate documents contain highly sensitive information (beneficiary names, asset values, conditions). The encrypted-at-rest requirement is non-negotiable; the `EncryptedJSONB` column type satisfies this with the existing key management setup.
- The `model` field in `SummaryResult` should record the exact model ID used (e.g. `claude-sonnet-4-6`), so the provenance of any given summary is traceable even if the default model changes in future.
- If `summarize=true` is passed without Claude credentials configured (no `ANTHROPIC_API_KEY` and no Claude `AnalysisConfig`), the service should raise immediately so the try/except wrapper logs the misconfiguration and sets `summary` to `null`.
