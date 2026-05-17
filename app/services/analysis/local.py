import asyncio

from app.processing.document_analyzer import DocumentAnalyzer
from app.providers import AnalysisProvider
from app.services.analysis.base import (
    AnalysisResult,
    DocumentAnalysisBackend,
    FieldValue,
)

# Maps DocumentAnalyzer attribute names to canonical field names.
# Listed in priority order per canonical name: first source that is present wins.
_CANONICAL_SOURCES: dict[str, list[str]] = {
    "given_names": ["given_names", "first_name"],  # DCT (combined) preferred over DAC
    "surname": ["surname"],
    "middle_name": ["middle_name"],
    "date_of_birth": ["date_of_birth"],
    "expiration_date": ["expiration_date"],
    "document_number": ["document_number", "license_number"],
    "address": ["address1"],
    "city": ["city"],
    "state": ["state"],
    "postal_code": ["postal_code"],
    "sex": ["sex"],
    "nationality": ["nationality"],
    "issuing_state": ["issuing_state"],
    "ssn": ["ssn"],
}


class LocalAnalysisBackend(DocumentAnalysisBackend):
    """Wraps the deterministic local DocumentAnalyzer, adapting its output to AnalysisResult."""

    def __init__(self) -> None:
        self._analyzer = DocumentAnalyzer()

    async def analyze(self, file_bytes: bytes, content_type: str) -> AnalysisResult:
        raw = await asyncio.to_thread(self._analyzer.analyze, file_bytes)
        return _adapt(raw)


def _adapt(raw: dict) -> AnalysisResult:
    doc_type = raw.get("document_type", "unknown")
    confidences = raw.get("confidences", {})
    attributes = raw.get("attributes", {})

    if "barcode" in confidences:
        doc_type_confidence = confidences["barcode"]
        field_confidence = confidences["barcode"]
    elif "mrz_valid_score" in confidences:
        doc_type_confidence = min(1.0, float(confidences["mrz_valid_score"]))
        field_confidence = doc_type_confidence
    elif "ocr" in confidences:
        doc_type_confidence = confidences["ocr"]
        field_confidence = confidences["ocr"]
    else:
        doc_type_confidence = 0.0
        field_confidence = 0.0

    fields: dict[str, FieldValue] = {}
    for canonical, sources in _CANONICAL_SOURCES.items():
        for src in sources:
            if src in attributes and attributes[src] is not None:
                fields[canonical] = FieldValue(
                    value=str(attributes[src]),
                    confidence=field_confidence,
                )
                break

    return AnalysisResult(
        document_type=doc_type,
        document_type_confidence=doc_type_confidence,
        fields=fields,
        provider=AnalysisProvider.LOCAL,
    )
