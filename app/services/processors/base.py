from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass
class ProcessorContext:
    user_id: UUID
    project_id: str


class AssetProcessor(ABC):
    @abstractmethod
    async def process(
        self,
        file_bytes: bytes,
        content_type: str,
        asset_url: str,
        ctx: ProcessorContext,
    ) -> dict[str, Any]:
        """Run processing on an uploaded asset. Returns a partial AssetUpdate payload."""
