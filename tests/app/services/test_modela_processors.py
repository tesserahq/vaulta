"""Unit tests for ModelaAnalysisProcessor and ModelaSummarizationProcessor.

All external calls (M2MTokenClient, IdentiesClient, ModelaClient) are mocked
so no live API calls are made.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.processors.base import ProcessorContext
from app.services.processors.modela import (
    ModelaAnalysisProcessor,
    ModelaSummarizationProcessor,
    _get_delegated_token,
)

USER_ID = uuid.uuid4()
PROJECT_ID = "proj-123"
ASSET_URL = "https://storage.example.com/assets/file.pdf"
CONTENT_TYPE = "application/pdf"

CTX = ProcessorContext(user_id=USER_ID, project_id=PROJECT_ID)


# ---------------------------------------------------------------------------
# _get_delegated_token
# ---------------------------------------------------------------------------


def _mock_m2m_client(access_token: str = "m2m-token"):
    client = MagicMock()
    client.get_token_sync.return_value = MagicMock(access_token=access_token)
    return client


def _mock_identies_client(delegated_token: str = "delegated-token"):
    client = MagicMock()
    client.exchange_token.return_value = MagicMock(access_token=delegated_token)
    return client


@patch("tessera_sdk.infra.m2m_token.M2MTokenClient")
@patch("tessera_sdk.clients.identies.client.IdentiesClient")
def test_get_delegated_token_calls_exchange(mock_identies_cls, mock_m2m_cls):
    mock_m2m_cls.return_value = _mock_m2m_client("base-token")
    mock_identies = _mock_identies_client("user-token")
    mock_identies_cls.return_value = mock_identies

    with patch("app.config.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            modela_audience="https://modela.example.com",
            modela_scope="scan:file summarize:file",
        )
        token = _get_delegated_token(CTX)

    assert token == "user-token"
    mock_identies.exchange_token.assert_called_once_with(
        user_id=str(USER_ID),
        requested_audience="https://modela.example.com",
        requested_scope="scan:file summarize:file",
    )


# ---------------------------------------------------------------------------
# ModelaAnalysisProcessor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.services.processors.modela._get_delegated_token", return_value="tok")
@patch("tessera_sdk.clients.modela.client.ModelaClient")
async def test_analysis_processor_happy_path(mock_client_cls, mock_token):
    scan_data = {"document_type": "driver_license", "confidence": 0.94, "fields": []}
    mock_client = MagicMock()
    mock_client.scan_file.return_value = MagicMock(data=scan_data)
    mock_client_cls.return_value = mock_client

    result = await ModelaAnalysisProcessor().process(
        b"bytes", CONTENT_TYPE, ASSET_URL, CTX
    )

    assert result == {"extracted_data": scan_data}
    mock_client_cls.assert_called_once_with(api_token="tok", timeout=20)
    mock_client.scan_file.assert_called_once_with(
        file_url=ASSET_URL,
        mime_type=CONTENT_TYPE,
        project_id=PROJECT_ID,
    )


@pytest.mark.asyncio
@patch(
    "app.services.processors.modela._get_delegated_token",
    side_effect=Exception("auth error"),
)
async def test_analysis_processor_token_failure_returns_empty(mock_token):
    result = await ModelaAnalysisProcessor().process(
        b"bytes", CONTENT_TYPE, ASSET_URL, CTX
    )
    assert result == {}


@pytest.mark.asyncio
@patch("app.services.processors.modela._get_delegated_token", return_value="tok")
@patch("tessera_sdk.clients.modela.client.ModelaClient")
async def test_analysis_processor_scan_failure_returns_empty(
    mock_client_cls, mock_token
):
    mock_client_cls.return_value.scan_file.side_effect = Exception("scan error")

    result = await ModelaAnalysisProcessor().process(
        b"bytes", CONTENT_TYPE, ASSET_URL, CTX
    )
    assert result == {}


# ---------------------------------------------------------------------------
# ModelaSummarizationProcessor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.services.processors.modela._get_delegated_token", return_value="tok")
@patch("tessera_sdk.clients.modela.client.ModelaClient")
async def test_summarization_processor_happy_path(mock_client_cls, mock_token):
    mock_client = MagicMock()
    mock_client.summarize_file.return_value = MagicMock(
        summary="A California driver license.", model="modela-v1", request_id="req-1"
    )
    mock_client_cls.return_value = mock_client

    result = await ModelaSummarizationProcessor().process(
        b"bytes", CONTENT_TYPE, ASSET_URL, CTX
    )

    assert result == {
        "summary": {
            "text": "A California driver license.",
            "provider": "modela",
            "model": "modela-v1",
        }
    }
    mock_client.summarize_file.assert_called_once_with(
        file_url=ASSET_URL,
        mime_type=CONTENT_TYPE,
        project_id=PROJECT_ID,
    )


@pytest.mark.asyncio
@patch(
    "app.services.processors.modela._get_delegated_token",
    side_effect=Exception("auth error"),
)
async def test_summarization_processor_token_failure_returns_empty(mock_token):
    result = await ModelaSummarizationProcessor().process(
        b"bytes", CONTENT_TYPE, ASSET_URL, CTX
    )
    assert result == {}


@pytest.mark.asyncio
@patch("app.services.processors.modela._get_delegated_token", return_value="tok")
@patch("tessera_sdk.clients.modela.client.ModelaClient")
async def test_summarization_processor_api_failure_returns_empty(
    mock_client_cls, mock_token
):
    mock_client_cls.return_value.summarize_file.side_effect = Exception("api error")

    result = await ModelaSummarizationProcessor().process(
        b"bytes", CONTENT_TYPE, ASSET_URL, CTX
    )
    assert result == {}


# ---------------------------------------------------------------------------
# ProcessorContext threading
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.services.processors.modela._get_delegated_token", return_value="tok")
@patch("tessera_sdk.clients.modela.client.ModelaClient")
async def test_project_id_forwarded_to_scan(mock_client_cls, mock_token):
    """project_id from ctx must reach ModelaClient.scan_file, not be hardcoded."""
    mock_client = MagicMock()
    mock_client.scan_file.return_value = MagicMock(data={})
    mock_client_cls.return_value = mock_client

    custom_ctx = ProcessorContext(user_id=USER_ID, project_id="custom-project")
    await ModelaAnalysisProcessor().process(
        b"bytes", CONTENT_TYPE, ASSET_URL, custom_ctx
    )

    mock_client.scan_file.assert_called_once_with(
        file_url=ASSET_URL, mime_type=CONTENT_TYPE, project_id="custom-project"
    )
