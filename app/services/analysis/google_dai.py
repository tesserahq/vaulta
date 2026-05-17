import asyncio
import logging
from typing import Optional

from app.providers import AnalysisProvider
from app.services.analysis.base import (
    AnalysisResult,
    DocumentAnalysisBackend,
    FieldValue,
    OcrLine,
)
from app.services.analysis.preprocessor import AnalysisPreprocessor

logger = logging.getLogger(__name__)

# Canonical mappings for well-known Google DAI entity types.
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

        logger.info(
            "Google DAI analyze started content_type=%s input_bytes=%d processor=%s",
            content_type,
            len(file_bytes),
            self._processor_id,
        )

        jpeg_bytes = self._preprocessor.to_jpeg_bytes(file_bytes, content_type)
        logger.debug("Google DAI preprocessed image to JPEG bytes=%d", len(jpeg_bytes))

        raw_document = documentai.RawDocument(
            content=jpeg_bytes, mime_type="image/jpeg"
        )
        request = documentai.ProcessRequest(
            name=self._processor_id, raw_document=raw_document
        )
        try:
            response = await asyncio.to_thread(
                self._client.process_document, request=request
            )
        except Exception:
            logger.exception(
                "Google DAI process_document failed processor=%s",
                self._processor_id,
            )
            raise

        doc = response.document
        entity_count = len(doc.entities) if doc.entities else 0
        text_len = len(getattr(doc, "text", "") or "")
        logger.info(
            "Google DAI process_document succeeded entities=%d text_chars=%d",
            entity_count,
            text_len,
        )
        return _adapt(doc)


def _adapt(doc) -> AnalysisResult:
    fields: dict[str, FieldValue] = {}
    doc_type = "unknown"
    doc_type_confidence = 0.0
    entities = doc.entities or []

    if not entities:
        logger.warning("Google DAI returned no entities for document")

    for entity in entities:
        entity_type: str = entity.type_.lower()
        mention_text = entity.mention_text or ""
        confidence = entity.confidence

        if entity_type == "document_type":
            raw = mention_text.lower().replace(" ", "_")
            doc_type = _DOCTYPE_MAP.get(raw, raw)
            doc_type_confidence = confidence
            logger.debug(
                "Google DAI document_type entity raw=%r mapped=%s confidence=%.3f",
                mention_text,
                doc_type,
                confidence,
            )
            continue

        value_text = mention_text.strip()
        if not value_text:
            logger.debug(
                "Google DAI skipping entity type=%s (empty mention_text) confidence=%.3f",
                entity_type,
                confidence,
            )
            continue

        canonical = _FIELD_MAP.get(entity_type, entity_type)
        fields[canonical] = FieldValue(
            value=value_text,
            confidence=confidence,
        )
        logger.debug(
            "Google DAI mapped entity type=%s -> %s value=%r confidence=%.3f",
            entity_type,
            canonical,
            value_text,
            confidence,
        )

    # Google DAI exposes the full document text; split into lines for ocr_lines.
    # Per-line confidence is not natively available, so we use 1.0 as a placeholder.
    raw_text: str = getattr(doc, "text", "") or ""
    ocr_lines = [
        OcrLine(text=line, confidence=1.0)
        for line in raw_text.splitlines()
        if line.strip()
    ]

    logger.info(
        "Google DAI adapt complete document_type=%s fields=%d ocr_lines=%d",
        doc_type,
        len(fields),
        len(ocr_lines),
    )
    if not fields and not ocr_lines:
        logger.warning(
            "Google DAI produced no fields and no OCR lines; "
            "check processor type (ID proofing vs OCR) and document content"
        )

    return AnalysisResult(
        document_type=doc_type,
        document_type_confidence=doc_type_confidence,
        fields=fields,
        ocr_lines=ocr_lines,
        provider=AnalysisProvider.GOOGLE_DAI,
    )
