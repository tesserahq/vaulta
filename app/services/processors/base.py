from abc import ABC, abstractmethod
from typing import Any


class AssetProcessor(ABC):
    @abstractmethod
    async def process(
        self, file_bytes: bytes, content_type: str, asset_url: str
    ) -> dict[str, Any]:
        """Run processing on an uploaded asset. Returns a partial AssetUpdate payload."""
