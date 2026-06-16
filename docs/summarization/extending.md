# Adding a Summarization Provider

Summarization does not use the `DocumentAnalysisBackend` ABC. Instead, it runs through the `AssetProcessor` abstraction directly. To add a new summarization provider:

## 1. Create a service class

```python
# app/services/summarization/my_provider.py
from pydantic import BaseModel


class SummaryResult(BaseModel):
    text: str
    provider: str
    model: str


class MyProviderSummarizationService:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def summarize(self, file_bytes: bytes, content_type: str) -> SummaryResult:
        # Call external API ...
        text = await _call_my_api(file_bytes, content_type, self._api_key)
        return SummaryResult(text=text, provider="my_provider", model="my-model-v1")
```

## 2. Create a processor

```python
# app/services/processors/my_summarization.py
import logging
from typing import Any

from app.services.processors.base import AssetProcessor, ProcessorContext
from app.services.summarization.my_provider import MyProviderSummarizationService

logger = logging.getLogger(__name__)


class MyProviderSummarizationProcessor(AssetProcessor):
    def __init__(self, service: MyProviderSummarizationService) -> None:
        self._service = service

    async def process(
        self,
        file_bytes: bytes,
        content_type: str,
        asset_url: str,
        ctx: ProcessorContext,
    ) -> dict[str, Any]:
        try:
            result = await self._service.summarize(file_bytes, content_type)
            return {"summary": result.model_dump()}
        except Exception:
            logger.exception("my_provider summarization failed")
            return {}
```

## 3. Wire it into the router

In `app/routers/assets.py`, add a condition inside the `summarize` block:

```python
if summarize:
    if config and config.summarization_provider == "my_provider":
        from app.services.summarization.my_provider import MyProviderSummarizationService
        from app.services.processors.my_summarization import MyProviderSummarizationProcessor
        processors.append(
            MyProviderSummarizationProcessor(MyProviderSummarizationService(api_key=...))
        )
    elif config and config.summarization_provider == AnalysisProvider.MODELA:
        processors.append(ModelaSummarizationProcessor())
    else:
        processors.append(SummarizationProcessor(ClaudeSummarizationService()))
```

## 4. Add to `AnalysisProvider` (if persisting in DB)

If `summarization_provider` is stored on `AnalysisConfig`, add the new key to the `AnalysisProvider` enum in `app/providers.py` so it can be stored and validated.
