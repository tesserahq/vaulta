# Processors

A processor is the unit of work that runs on an uploaded file before the asset record is finalized. All processors share the `AssetProcessor` ABC and are composed in the upload pipeline via `upload_asset()`.

## `AssetProcessor` ABC

```python
# app/services/processors/base.py
class AssetProcessor(ABC):
    @abstractmethod
    async def process(
        self,
        file_bytes: bytes,
        content_type: str,
        asset_url: str,
        ctx: ProcessorContext,
    ) -> dict[str, Any]:
        """Returns a partial AssetUpdate payload."""
```

The return value is a dict whose keys must match fields on `AssetUpdate`. `upload_asset()` calls each processor in order and merges results with `dict.update()` — later processors overwrite earlier ones for the same key.

If a processor fails it should catch its exception, log it, and return `{}` so the upload still completes. All built-in processors follow this pattern.

## `ProcessorContext`

```python
@dataclass
class ProcessorContext:
    user_id: UUID
    project_id: str
```

Carries per-request context that processors may need. `project_id` defaults to `"*"` when the caller does not pass `project_id` on upload; Modela processors use it to scope API calls.

## How processors are composed

In `app/routers/assets.py`, the upload endpoint builds a list of processors based on the form flags:

```
extract_data=true  →  append AnalysisProcessor (or ModelaAnalysisProcessor)
summarize=true     →  append SummarizationProcessor (or ModelaSummarizationProcessor)
```

The list is passed to `upload_asset()`, which runs them sequentially after the file is saved to storage. Both can be requested in the same upload.
