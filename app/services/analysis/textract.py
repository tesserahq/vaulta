import asyncio
from typing import Optional

from app.services.analysis.base import (
    AnalysisResult,
    DocumentAnalysisBackend,
    FieldValue,
    is_partial,
)
from app.services.analysis.preprocessor import AnalysisPreprocessor

_FIELD_MAP: dict[str, Optional[str]] = {
    "FIRST_NAME": "given_names",
    "LAST_NAME": "surname",
    "MIDDLE_NAME": "middle_name",
    "DATE_OF_BIRTH": "date_of_birth",
    "DATE_OF_EXPIRY": "expiration_date",
    "DOCUMENT_NUMBER": "document_number",
    "ADDRESS": "address",
    "ID_TYPE": None,  # handled separately for document_type
    "MRZ_CODE": None,
    "COUNTY": None,
}

_DOCTYPE_MAP: dict[str, str] = {
    "PASSPORT": "passport",
    "DRIVER LICENSE": "drivers_license",
    "DRIVER'S LICENSE": "drivers_license",
    "IDENTIFICATION CARD": "national_id",
    "ID CARD": "national_id",
}


class TextractAnalysisBackend(DocumentAnalysisBackend):
    """AWS Textract AnalyzeID provider."""

    def __init__(
        self,
        aws_access_key_id: Optional[str],
        aws_secret_access_key: Optional[str],
        region_name: str,
        max_image_px: int = 2048,
    ) -> None:
        import boto3

        self._client = boto3.client(
            "textract",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )
        self._preprocessor = AnalysisPreprocessor(max_image_px=max_image_px)

    async def analyze(self, file_bytes: bytes, content_type: str) -> AnalysisResult:
        jpeg_bytes = self._preprocessor.to_jpeg_bytes(file_bytes, content_type)
        response = await asyncio.to_thread(
            self._client.analyze_id,
            DocumentPages=[{"Bytes": jpeg_bytes}],
        )
        return _adapt(response)


def _adapt(response: dict) -> AnalysisResult:
    docs = response.get("IdentityDocuments", [])
    if not docs:
        return AnalysisResult(
            document_type="unknown",
            document_type_confidence=0.0,
            fields={},
            partial=True,
            provider="textract",
        )

    doc = docs[0]
    fields: dict[str, FieldValue] = {}
    doc_type = "unknown"
    doc_type_confidence = 0.0

    for item in doc.get("IdentityDocumentFields", []):
        type_text: str = item.get("Type", {}).get("Text", "")
        value_det = item.get("ValueDetection", {})
        value_text: str = value_det.get("Text", "").strip()
        confidence: float = value_det.get("Confidence", 0.0) / 100.0

        if type_text == "ID_TYPE":
            doc_type = _DOCTYPE_MAP.get(value_text.upper(), "unknown")
            doc_type_confidence = confidence
            continue

        canonical = _FIELD_MAP.get(type_text)
        if canonical and value_text:
            fields[canonical] = FieldValue(value=value_text, confidence=confidence)

    partial = is_partial(doc_type, fields)

    return AnalysisResult(
        document_type=doc_type,
        document_type_confidence=doc_type_confidence,
        fields=fields,
        partial=partial,
        provider="textract",
    )
