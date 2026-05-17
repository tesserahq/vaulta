import asyncio
from typing import Optional

from app.services.analysis.base import (
    AnalysisResult,
    DocumentAnalysisBackend,
    FieldValue,
    is_partial,
)
from app.services.analysis.preprocessor import AnalysisPreprocessor

_FIELD_MAP: dict[str, str] = {
    "given_names": "given_names",
    "family_name": "surname",
    "date_of_birth": "date_of_birth",
    "expiration_date": "expiration_date",
    "document_id": "document_number",
    "address": "address",
    "sex": "sex",
    "nationality": "nationality",
    "issuing_country": "issuing_state",
}

_DOCTYPE_MAP: dict[str, str] = {
    "passport": "passport",
    "driver_license": "drivers_license",
    "national_id": "national_id",
    "id_card": "national_id",
}


class GoogleDAIAnalysisBackend(DocumentAnalysisBackend):
    """Google Document AI provider."""

    def __init__(
        self,
        processor_id: str,
        credentials_path: Optional[str] = None,
        max_image_px: int = 2048,
    ) -> None:
        from google.cloud import documentai

        kwargs: dict = {}
        if credentials_path:
            from google.oauth2 import service_account

            kwargs["credentials"] = (
                service_account.Credentials.from_service_account_file(credentials_path)
            )
        self._client = documentai.DocumentProcessorServiceClient(**kwargs)
        self._processor_id = processor_id
        self._preprocessor = AnalysisPreprocessor(max_image_px=max_image_px)

    async def analyze(self, file_bytes: bytes, content_type: str) -> AnalysisResult:
        from google.cloud import documentai

        jpeg_bytes = self._preprocessor.to_jpeg_bytes(file_bytes, content_type)
        raw_document = documentai.RawDocument(
            content=jpeg_bytes, mime_type="image/jpeg"
        )
        request = documentai.ProcessRequest(
            name=self._processor_id, raw_document=raw_document
        )
        response = await asyncio.to_thread(
            self._client.process_document, request=request
        )
        return _adapt(response.document)


def _adapt(doc) -> AnalysisResult:
    fields: dict[str, FieldValue] = {}
    doc_type = "unknown"
    doc_type_confidence = 0.0

    for entity in doc.entities:
        entity_type: str = entity.type_.lower()
        if entity_type == "document_type":
            raw = entity.mention_text.lower().replace(" ", "_")
            doc_type = _DOCTYPE_MAP.get(raw, raw)
            doc_type_confidence = entity.confidence
            continue
        canonical = _FIELD_MAP.get(entity_type)
        if canonical:
            fields[canonical] = FieldValue(
                value=entity.mention_text,
                confidence=entity.confidence,
            )

    partial = is_partial(doc_type, fields)

    return AnalysisResult(
        document_type=doc_type,
        document_type_confidence=doc_type_confidence,
        fields=fields,
        partial=partial,
        provider="google_dai",
    )
