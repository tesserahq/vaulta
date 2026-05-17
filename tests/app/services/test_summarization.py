"""Unit tests for the Claude summarization service.

Tests call _build_content_block() and SummaryResult directly, and verify
that ClaudeSummarizationService sends the right payload to Claude without
making live API calls (Anthropic client is mocked).
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.summarization.claude import (
    ClaudeSummarizationService,
    SummaryResult,
    _build_content_block,
)

# ---------------------------------------------------------------------------
# _build_content_block
# ---------------------------------------------------------------------------


class TestBuildContentBlock:
    def test_pdf_produces_document_block(self):
        block = _build_content_block(b"PDF_BYTES", "application/pdf")
        assert block["type"] == "document"
        assert block["source"]["media_type"] == "application/pdf"

    def test_image_produces_image_block(self):
        block = _build_content_block(b"IMG_BYTES", "image/jpeg")
        assert block["type"] == "image"
        assert block["source"]["media_type"] == "image/jpeg"

    def test_png_produces_image_block(self):
        block = _build_content_block(b"PNG_BYTES", "image/png")
        assert block["type"] == "image"

    def test_pdf_block_has_base64_data(self):
        import base64

        data = b"hello pdf"
        block = _build_content_block(data, "application/pdf")
        assert block["source"]["type"] == "base64"
        assert block["source"]["data"] == base64.standard_b64encode(data).decode()

    def test_image_block_has_base64_data(self):
        import base64

        data = b"hello img"
        block = _build_content_block(data, "image/jpeg")
        assert block["source"]["type"] == "base64"
        assert block["source"]["data"] == base64.standard_b64encode(data).decode()


# ---------------------------------------------------------------------------
# ClaudeSummarizationService (mocked Anthropic client)
# ---------------------------------------------------------------------------


def _make_service(mock_message_text: str = "This is a summary.") -> tuple:
    """Return (service, mock_client) with the Anthropic client mocked."""
    mock_content = MagicMock()
    mock_content.text = mock_message_text
    mock_message = MagicMock()
    mock_message.content = [mock_content]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    return mock_client, mock_message_text


class TestClaudeSummarizationService:
    def _service_with_mock(self, response_text: str = "Summary here."):
        mock_client, _ = _make_service(response_text)
        with patch("anthropic.Anthropic", return_value=mock_client):
            service = ClaudeSummarizationService(api_key="test-key")
        service._client = mock_client
        return service, mock_client

    @pytest.mark.asyncio
    async def test_returns_summary_result(self):
        service, _ = self._service_with_mock("A full summary of the will.")
        result = await service.summarize(b"PDF", "application/pdf")
        assert isinstance(result, SummaryResult)
        assert result.text == "A full summary of the will."

    @pytest.mark.asyncio
    async def test_provider_is_claude(self):
        service, _ = self._service_with_mock()
        result = await service.summarize(b"PDF", "application/pdf")
        assert result.provider == "claude"

    @pytest.mark.asyncio
    async def test_model_recorded_in_result(self):
        service, _ = self._service_with_mock()
        result = await service.summarize(b"PDF", "application/pdf")
        assert result.model == service._model

    @pytest.mark.asyncio
    async def test_pdf_sends_document_block(self):
        service, mock_client = self._service_with_mock()
        await service.summarize(b"PDF_CONTENT", "application/pdf")
        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        content = messages[0]["content"]
        assert content[0]["type"] == "document"

    @pytest.mark.asyncio
    async def test_image_sends_image_block(self):
        service, mock_client = self._service_with_mock()
        await service.summarize(b"IMG_CONTENT", "image/jpeg")
        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        content = messages[0]["content"]
        assert content[0]["type"] == "image"

    @pytest.mark.asyncio
    async def test_max_tokens_is_reasonable(self):
        service, mock_client = self._service_with_mock()
        await service.summarize(b"DATA", "application/pdf")
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["max_tokens"] >= 1024

    def test_summary_result_model_dump(self):
        result = SummaryResult(
            text="A prose summary.", provider="claude", model="claude-sonnet-4-6"
        )
        d = result.model_dump()
        assert d["text"] == "A prose summary."
        assert d["provider"] == "claude"
        assert d["model"] == "claude-sonnet-4-6"
