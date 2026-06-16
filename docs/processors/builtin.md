# Built-in Processors

## `AnalysisProcessor`

`app/services/processors/analysis.py`

Wraps a `DocumentAnalysisBackend` and writes the result to `asset.extracted_data`.

```python
class AnalysisProcessor(AssetProcessor):
    def __init__(self, backend: DocumentAnalysisBackend) -> None: ...

    async def process(...) -> dict:
        result = await self._backend.analyze(file_bytes, content_type)
        return {"extracted_data": result.model_dump()}
```

The `backend` instance is created by `AnalysisFactory` and injected by the router. On failure, logs the exception and returns `{}`.

---

## `SummarizationProcessor`

`app/services/processors/summarization.py`

Wraps `ClaudeSummarizationService` and writes the result to `asset.summary`.

```python
class SummarizationProcessor(AssetProcessor):
    def __init__(self, service: ClaudeSummarizationService) -> None: ...

    async def process(...) -> dict:
        result = await self._service.summarize(file_bytes, content_type)
        return {"summary": result.model_dump()}
```

A new `ClaudeSummarizationService` instance is created per request in the router. On failure, logs and returns `{}`.

---

## `ModelaAnalysisProcessor`

`app/services/processors/modela.py`

Uses the Tessera SDK `ModelaClient.scan_file()` to extract structured data. Performs a delegated token exchange before each call so the API call is attributed to the uploading user.

```python
async def process(...) -> dict:
    token = _get_delegated_token(ctx)
    response = ModelaClient(api_token=token).scan_file(
        file_url=asset_url,
        mime_type=content_type,
        project_id=ctx.project_id,
    )
    return {"extracted_data": response.data}
```

Requires `asset_url` to be a publicly accessible URL (the presigned URL or serve URL returned by the storage backend). See [Modela](../modela.md) for token exchange details.

---

## `ModelaSummarizationProcessor`

`app/services/processors/modela.py`

Uses `ModelaClient.summarize_file()` with the same delegated token pattern.

```python
async def process(...) -> dict:
    token = _get_delegated_token(ctx)
    response = ModelaClient(api_token=token).summarize_file(
        file_url=asset_url,
        mime_type=content_type,
        project_id=ctx.project_id,
    )
    return {"summary": {"text": response.summary, "provider": "modela", "model": response.model}}
```
