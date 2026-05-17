from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class FieldValue(BaseModel):
    value: str | None
    confidence: float


class OcrLine(BaseModel):
    text: str
    confidence: float


class AnalysisResult(BaseModel):
    document_type: str
    document_type_confidence: float
    fields: dict[str, FieldValue]
    ocr_lines: list[OcrLine] = []
    provider: str
    raw_response: dict[str, Any] | None = None


class DocumentAnalysisBackend(ABC):
    @abstractmethod
    async def analyze(self, file_bytes: bytes, content_type: str) -> AnalysisResult:
        pass
