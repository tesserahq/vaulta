# Adding a Processor

A processor can do anything with the file bytes, content type, asset URL, and context. It returns a partial dict that gets merged into the final `AssetUpdate`.

## 1. Implement `AssetProcessor`

```python
# app/services/processors/my_processor.py
import logging
from typing import Any

from app.services.processors.base import AssetProcessor, ProcessorContext

logger = logging.getLogger(__name__)


class MyProcessor(AssetProcessor):
    def __init__(self, some_config: str) -> None:
        self._config = some_config

    async def process(
        self,
        file_bytes: bytes,
        content_type: str,
        asset_url: str,
        ctx: ProcessorContext,
    ) -> dict[str, Any]:
        try:
            result = await _do_something(file_bytes, self._config)
            # Return keys that match fields on AssetUpdate
            return {"labels": {"my_processor_result": result}}
        except Exception:
            logger.exception("my_processor failed")
            return {}
```

**Rules:**
- Always catch exceptions and return `{}` on failure. The upload must not fail because a processor errored.
- Only return keys that exist on `AssetUpdate`. Unknown keys will cause a validation error when `upload_asset()` tries to construct the update.
- If your processor needs a publicly accessible file URL (e.g. to pass to an external API), use `asset_url`. This is a presigned S3 URL or local serve URL depending on the storage backend.

## 2. Wire it in the router

In `app/routers/assets.py`, add the processor to the list built inside the upload endpoint:

```python
from app.services.processors.my_processor import MyProcessor

# Inside upload_asset_endpoint:
processors = []
# ... existing logic ...
if some_condition:
    processors.append(MyProcessor(some_config="value"))
```

Processors run in the order they appear in the list. Results are merged left to right, so a later processor can overwrite a key written by an earlier one.

## Notes on `ProcessorContext`

`ctx.user_id` is the authenticated user's UUID. `ctx.project_id` is the `project_id` form field from the upload request, defaulting to `"*"` when omitted. Use these when your processor needs to scope API calls or audit logs to the requesting user.
