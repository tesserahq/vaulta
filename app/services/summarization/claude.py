import asyncio
import base64
import json
import logging
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-6"

_SYSTEM_PROMPT = (
    "You are a document analysis assistant. Summarize the document clearly and concisely. "
    "Return only the summary text — no preamble, no commentary."
)

_USER_PROMPT = """\
Summarize this document in plain language. Write one paragraph per major section or topic. \
Focus on the key facts, parties involved, obligations, and any important dates or conditions. \
Do not use bullet points or headers — write in flowing prose."""


class SummaryResult(BaseModel):
    text: str
    provider: str
    model: str


class ClaudeSummarizationService:
    """Summarizes documents by sending them natively to Claude.

    PDFs are sent as document blocks (full content, no JPEG conversion).
    Images are sent as image blocks.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        bedrock_region: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        from app.config import get_settings

        settings = get_settings()
        self._bedrock_region = bedrock_region or settings.bedrock_region
        self._model = model or _DEFAULT_MODEL

        if self._bedrock_region:
            import boto3

            self._client = boto3.client(
                "bedrock-runtime", region_name=self._bedrock_region
            )
        else:
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=api_key or settings.anthropic_api_key
            )

    async def summarize(self, file_bytes: bytes, content_type: str) -> SummaryResult:
        logger.info(
            "summarization started content_type=%s input_bytes=%d model=%s",
            content_type,
            len(file_bytes),
            self._model,
        )
        content_block = _build_content_block(file_bytes, content_type)
        messages = [
            {
                "role": "user",
                "content": [
                    content_block,
                    {"type": "text", "text": _USER_PROMPT},
                ],
            }
        ]

        if self._bedrock_region:
            text = await asyncio.to_thread(self._call_bedrock, messages)
        else:
            text = await asyncio.to_thread(self._call_anthropic, messages)

        logger.info("summarization complete chars=%d", len(text))
        return SummaryResult(text=text, provider="claude", model=self._model)

    def _call_anthropic(self, messages: list[dict[str, Any]]) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=messages,
        )
        return message.content[0].text

    def _call_bedrock(self, messages: list[dict[str, Any]]) -> str:
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2048,
                "system": _SYSTEM_PROMPT,
                "messages": messages,
            }
        )
        response = self._client.invoke_model(modelId=self._model, body=body)
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]


def _build_content_block(file_bytes: bytes, content_type: str) -> dict[str, Any]:
    """Return the Claude content block for the given file."""
    b64 = base64.standard_b64encode(file_bytes).decode()
    if content_type == "application/pdf":
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": b64,
            },
        }
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": content_type,
            "data": b64,
        },
    }
