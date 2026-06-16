# Handoff: Modela Analysis Provider — Vaulta

**Project:** `/Users/emiliano.jankowski/sites/linden-family/vaulta`
**Date:** 2026-06-11
**Next focus:** Implement Modela as a new `DocumentAnalysisBackend` + `AssetProcessor`

---

## What was shipped (PR #108)

The upload pipeline was refactored to use an `AssetProcessor` abstraction.
See: https://github.com/tesserahq/vaulta/pull/108

Key new files:
- `app/services/processors/base.py` — `AssetProcessor` ABC: `process(file_bytes, content_type, asset_url) -> dict`
- `app/services/processors/analysis.py` — `AnalysisProcessor(DocumentAnalysisBackend)`
- `app/services/processors/summarization.py` — `SummarizationProcessor(ClaudeSummarizationService)`

`upload_asset` now reads file bytes once, stores, gets a URL, then runs a `list[AssetProcessor]` and merges their partial `AssetUpdate` payloads in one DB write.

---

## Modela integration — what was discussed

### The plan
Add Modela as a new image analysis provider. It sits alongside the existing providers (`local`, `textract`, `google_dai`, `claude`) in `app/services/analysis/`.

### SDK location
`/Users/emiliano.jankowski/sites/linden-family/tessera-sdk-py`

Relevant SDK files:
- `tessera_sdk/clients/modela/client.py` — `ModelaClient`
  - `scan_file(file_url, mime_type, model, project_id) -> ScanResponse`
  - `ScanResponse.data: dict` (raw result), `.model: str`, `.request_id: str`
- `tessera_sdk/clients/identies/client.py` — `IdentiesClient.exchange_token(...) -> TokenExchangeResponse`
- `tessera_sdk/infra/m2m_token.py` — `get_m2m_token_sync()` / `M2MTokenClient`

### Token exchange requirement
Modela calls must use a **delegated user token** (not a bare M2M token) so usage is attributed to the requesting user. The pattern:

```python
m2m_token = M2MTokenClient().get_token_sync().access_token
identies = IdentiesClient(api_token=m2m_token)
response = identies.exchange_token(
    user_id=str(user_id),
    requested_audience=<modela_audience>,
    requested_scope=<scopes>,
    context=<optional audit dict>,
)
# response.access_token → pass to ModelaClient(api_token=...)
```

### The file_url problem (unresolved)
`ModelaClient.scan_file` needs a **URL**, but `DocumentAnalysisBackend.analyze` receives raw `file_bytes`. The `AssetProcessor.process` interface now exposes `asset_url` (the storage URL generated after upload), which solves this — Modela can use `asset_url` directly instead of bytes.

This means `ModelaProcessor` should implement `AssetProcessor` directly (not go through `AnalysisProcessor` / `DocumentAnalysisBackend`), or the `DocumentAnalysisBackend.analyze` interface should be extended to accept an optional URL.

### user_id threading
The token exchange needs a `user_id`. Currently `AssetProcessor.process(file_bytes, content_type, asset_url)` does **not** include `user_id`. Options discussed but not decided:
1. Extend the `process` signature to `process(file_bytes, content_type, asset_url, user_id)` — clean but breaks existing processors
2. Pass `user_id` at construction time in `ModelaProcessor.__init__` — simpler, avoids interface change

Option 2 is recommended: the router already has `current_user.id` when building the processors list, so `ModelaProcessor(user_id=current_user.id)` fits naturally.

### New env vars needed
- `MODELA_API_URL` (already in tessera-sdk `get_settings()`)
- M2M credentials: `IDENTIES_CLIENT_ID` + `IDENTIES_CLIENT_SECRET` or Auth0 M2M config (already handled by `AuthTokenProvider` in the SDK)
- Modela audience/scope strings (confirm with Modela service docs)

---

## Suggested next steps

1. Decide on `user_id` in `ModelaProcessor` — constructor injection (option 2) is the recommendation
2. Create `app/services/processors/modela.py` implementing `AssetProcessor`:
   - Constructor takes `user_id: UUID`
   - Exchanges M2M token for delegated user token via `IdentiesClient`
   - Calls `ModelaClient(api_token=delegated_token).scan_file(asset_url, mime_type)`
   - Maps `ScanResponse.data` → `{"extracted_data": {...}}`
3. Add `MODELA` to `AnalysisProvider` enum in `app/providers.py` if it also needs to be a named backend (optional — depends on whether it plugs into `AnalysisFactory` too)
4. Wire up in the router (alongside the existing `AnalysisProcessor`)
5. Add env vars to `.env.example` / docs

---

## Suggested skills

- `/feature-dev:feature-dev` — for implementing the Modela processor end-to-end
- `/python-tests` — for writing tests around token exchange and the new processor
- `/grill-me` — if you want to stress-test the `user_id` threading decision before coding
