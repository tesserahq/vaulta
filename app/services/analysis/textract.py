import asyncio
import re
from typing import Optional

from app.providers import AnalysisProvider
from app.services.analysis.base import (
    AnalysisResult,
    DocumentAnalysisBackend,
    FieldValue,
    OcrLine,
)
from app.services.analysis.preprocessor import AnalysisPreprocessor

# Canonical mappings for well-known Textract field names.
_FIELD_MAP: dict[str, str] = {
    "FIRST_NAME": "given_names",
    "LAST_NAME": "surname",
    "MIDDLE_NAME": "middle_name",
    "DATE_OF_BIRTH": "date_of_birth",
    "DATE_OF_EXPIRY": "expiration_date",
    "EXPIRATION_DATE": "expiration_date",
    "DOCUMENT_NUMBER": "document_number",
    "ADDRESS": "address",
    "CITY_IN_ADDRESS": "city",
    "STATE_IN_ADDRESS": "state",
    "ZIP_CODE_IN_ADDRESS": "postal_code",
    "STATE_NAME": "state_name",
    "COUNTY": "county",
    "PLACE_OF_BIRTH": "place_of_birth",
    "SUFFIX": "suffix",
    "CLASS": "class",
    "RESTRICTIONS": "restrictions",
    "ENDORSEMENTS": "endorsements",
    "VETERAN": "veteran",
    "MRZ_CODE": "mrz_code",
}

# Prefix-based mapping: longest matching prefix wins. Keys are uppercase.
_DOCTYPE_PREFIXES: list[tuple[str, str]] = [
    ("PASSPORT", "passport"),
    ("DRIVER'S LICENSE", "drivers_license"),
    ("DRIVER LICENSE", "drivers_license"),
    ("IDENTIFICATION CARD", "national_id"),
    ("ID CARD", "national_id"),
]


def _normalise_doc_type(raw: str) -> str:
    upper = raw.upper().strip()
    for prefix, canonical in _DOCTYPE_PREFIXES:
        if upper.startswith(prefix):
            return canonical
    # Fall back to snake_case of whatever the provider returned.
    return re.sub(r"[^a-z0-9]+", "_", raw.lower().strip()).strip("_")


def _to_snake(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower().strip()).strip("_")


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
            ocr_lines=[],
            provider=AnalysisProvider.TEXTRACT,
            raw_response=response,
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
            doc_type = _normalise_doc_type(value_text) if value_text else "unknown"
            doc_type_confidence = confidence
            continue

        if not value_text:
            continue

        canonical = _FIELD_MAP.get(type_text) or _to_snake(type_text)
        fields[canonical] = FieldValue(value=value_text, confidence=confidence)

    ocr_lines = [
        OcrLine(
            text=block["Text"],
            confidence=block.get("Confidence", 0.0) / 100.0,
        )
        for block in doc.get("Blocks", [])
        if block.get("BlockType") == "LINE" and block.get("Text", "").strip()
    ]

    return AnalysisResult(
        document_type=doc_type,
        document_type_confidence=doc_type_confidence,
        fields=fields,
        ocr_lines=ocr_lines,
        provider=AnalysisProvider.TEXTRACT,
        raw_response=response,
    )
