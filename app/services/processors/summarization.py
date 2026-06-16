import logging
from typing import Any

from app.services.processors.base import AssetProcessor, ProcessorContext
from app.services.summarization.claude import ClaudeSummarizationService

logger = logging.getLogger(__name__)


class SummarizationProcessor(AssetProcessor):
    def __init__(self, service: ClaudeSummarizationService) -> None:
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
            logger.exception("summarization failed")
            return {}
