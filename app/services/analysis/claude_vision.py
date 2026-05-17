import asyncio
import base64
import json
from typing import Any, Optional

from app.services.analysis.base import (
    AnalysisResult,
    DocumentAnalysisBackend,
    FieldValue,
    is_partial,
)
from app.services.analysis.preprocessor import AnalysisPreprocessor

_DEFAULT_DIRECT_MODEL = "claude-sonnet-4-6"
_DEFAULT_BEDROCK_MODEL = "anthropic.claude-sonnet-4-5-20251001-v1:0"

_SYSTEM_PROMPT = (
    "You are a document analysis assistant. Analyze the identity document image and extract "
    "structured data. Return only a JSON object — no markdown, no explanation."
)

_USER_PROMPT = """\
Extract data from this identity document and return a JSON object with this exact structure:
{
  "document_type": "<passport|drivers_license|national_id|social_security_card|unknown>",
  "document_type_confidence": <0.0-1.0>,
  "fields": {
    "<field_name>": {"value": "<extracted value or null>", "confidence": <0.0-1.0>}
  }
}

Valid field names: surname, given_names, middle_name, date_of_birth, expiration_date,
document_number, address, city, state, postal_code, sex, nationality, issuing_state, ssn

Rules:
- Dates in YYYY-MM-DD format
- Only include fields that are visible on the document
- Return only the JSON object"""


class ClaudeVisionAnalysisBackend(DocumentAnalysisBackend):
    """Claude vision provider supporting both Anthropic direct API and AWS Bedrock."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        bedrock_region: Optional[str] = None,
        model: Optional[str] = None,
        max_image_px: int = 2048,
    ) -> None:
        self._bedrock_region = bedrock_region
        self._model = model or (
            _DEFAULT_BEDROCK_MODEL if bedrock_region else _DEFAULT_DIRECT_MODEL
        )
        self._preprocessor = AnalysisPreprocessor(max_image_px=max_image_px)

        # Construct the appropriate client once at initialization.
        if bedrock_region:
            import boto3

            self._client = boto3.client("bedrock-runtime", region_name=bedrock_region)
        else:
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key)

    async def analyze(self, file_bytes: bytes, content_type: str) -> AnalysisResult:
        jpeg_bytes = self._preprocessor.to_jpeg_bytes(file_bytes, content_type)
        b64 = base64.standard_b64encode(jpeg_bytes).decode()

        if self._bedrock_region:
            raw = await asyncio.to_thread(self._call_bedrock, b64)
        else:
            raw = await asyncio.to_thread(self._call_anthropic, b64)

        return _adapt(raw)

    def _build_messages(self, b64: str) -> list[dict[str, Any]]:
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": _USER_PROMPT},
                ],
            }
        ]

    def _call_anthropic(self, b64: str) -> dict:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=self._build_messages(b64),
        )
        return json.loads(message.content[0].text)

    def _call_bedrock(self, b64: str) -> dict:
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": _SYSTEM_PROMPT,
                "messages": self._build_messages(b64),
            }
        )
        response = self._client.invoke_model(modelId=self._model, body=body)
        result = json.loads(response["body"].read())
        return json.loads(result["content"][0]["text"])


def _adapt(raw: dict) -> AnalysisResult:
    doc_type = raw.get("document_type", "unknown")
    fields: dict[str, FieldValue] = {}

    for name, fv in raw.get("fields", {}).items():
        if isinstance(fv, dict):
            fields[name] = FieldValue(
                value=fv.get("value"),
                confidence=float(fv.get("confidence", 0.8)),
            )

    return AnalysisResult(
        document_type=doc_type,
        document_type_confidence=float(raw.get("document_type_confidence", 0.0)),
        fields=fields,
        partial=is_partial(doc_type, fields),
        provider="claude",
    )
