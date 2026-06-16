# Modela

Modela is the Tessera-native provider for both document analysis and summarization. Unlike the other providers, it receives the file via a URL rather than raw bytes, and all API calls are attributed to the requesting user through a delegated token.

## When to use Modela

- You need Tessera-internal audit trails (calls appear under the user's identity in Modela, not as a service account).
- You want a single provider that handles both analysis and summarization through one SDK client.
- The file is already accessible at a public URL (Modela fetches it remotely; the file bytes are not sent by Vaulta).

## Token exchange

Every Modela API call performs a machine-to-machine token exchange before calling the client:

```
1. M2MTokenClient.get_token_sync()
      → Base M2M access token (service-level credential)

2. IdentiesClient.exchange_token(user_id, audience, scope)
      → Delegated access token scoped to the uploading user

3. ModelaClient(api_token=delegated_token).scan_file(...) / .summarize_file(...)
```

This ensures the Modela API call is attributed to `ctx.user_id`, not to the Vaulta service account.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `MODELA_AUDIENCE` | Yes | Token exchange audience (e.g. `https://modela.tessera.com`). |
| `MODELA_SCOPE` | Yes | Scopes to request (e.g. `scan:file summarize:file`). |

M2M credentials must also be configured in the `tessera-sdk` settings (typically `SERVICE_ACCOUNT_CLIENT_ID` and `SERVICE_ACCOUNT_CLIENT_SECRET`). These are not Vaulta settings; they are read by the SDK directly.

## Analysis via Modela

Select Modela for analysis by creating an `AnalysisConfig` with `provider="modela"` and marking it as default (or passing its `config_id` on upload).

```bash
curl -X POST http://localhost:8000/analysis-configs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Modela Analysis", "provider": "modela", "is_default": true}'
```

Then upload with `extract_data=true`:

```bash
curl -X POST http://localhost:8000/assets \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@passport.jpg" \
  -F "extract_data=true"
```

The processor calls `ModelaClient.scan_file(file_url, mime_type, project_id)`. Modela fetches the file from `file_url` (the presigned S3 URL or local serve URL). The response's `.data` dict is stored directly as `asset.extracted_data`.

## Summarization via Modela

Set `summarization_provider="modela"` on an `AnalysisConfig` and upload with `summarize=true`:

```bash
curl -X POST http://localhost:8000/assets \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@contract.pdf" \
  -F "summarize=true"
```

The processor calls `ModelaClient.summarize_file(file_url, mime_type, project_id)`. The response's `.summary` and `.model` are stored as `asset.summary`.

## Mixing providers

Analysis and summarization providers are independent fields on `AnalysisConfig`. You can mix them:

```json
{
  "name": "Modela summarization + Textract analysis",
  "provider": "textract",
  "summarization_provider": "modela"
}
```

A single upload with `extract_data=true&summarize=true` would run `AnalysisProcessor` (Textract) and `ModelaSummarizationProcessor` in sequence.

## File URL requirement

Modela fetches the file remotely. The `asset_url` passed to the processor is the URL returned by the storage backend:

- **S3:** a presigned URL valid for a short window. Modela must call it before expiry.
- **Local storage:** a signed `/serve/<token>` URL served by Vaulta itself. The Vaulta server must be reachable from the Modela service.

If Modela cannot reach the file URL, the processor logs the exception and returns `{}`, leaving the asset without `extracted_data` or `summary`.
