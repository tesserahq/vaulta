import logging
from typing import Any

from app.services.analysis.base import DocumentAnalysisBackend
from app.services.processors.base import AssetProcessor

logger = logging.getLogger(__name__)


class AnalysisProcessor(AssetProcessor):
    def __init__(self, backend: DocumentAnalysisBackend) -> None:
        self._backend = backend

    async def process(
        self, file_bytes: bytes, content_type: str, asset_url: str
    ) -> dict[str, Any]:
        try:
            result = await self._backend.analyze(file_bytes, content_type)
            return {"extracted_data": result.model_dump()}
        except Exception:
            logger.exception("document analysis failed")
            return {}
