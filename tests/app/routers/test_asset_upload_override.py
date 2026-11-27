"""The upload's extraction override: `provider` and `provider_params` form fields."""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

UPLOAD_FILE = {"file": ("will.pdf", b"%PDF-1.4 test", "application/pdf")}


@pytest.fixture
def authorize_mock():
    # Stops the upload at the Custos check, after the override has been parsed.
    mock = Mock(side_effect=HTTPException(status_code=403, detail="denied"))
    with patch("app.routers.assets.authorize_asset_action", mock):
        yield mock


def _upload(client, **data):
    return client.post(
        "/assets",
        files=UPLOAD_FILE,
        data={"project_id": str(uuid4()), "extract_data": "true", **data},
    )


def test_valid_override_passes_validation(client, authorize_mock):
    response = _upload(
        client, provider="modela", provider_params='{"model": "will-scan"}'
    )

    assert response.status_code == 403
    authorize_mock.assert_called_once()


@pytest.mark.parametrize("params", ["not json", "[1, 2]", '"will-scan"'])
def test_provider_params_must_be_a_json_object(client, authorize_mock, params):
    response = _upload(client, provider_params=params)

    assert response.status_code == 400
    assert "provider_params" in response.json()["detail"]
    authorize_mock.assert_not_called()


def test_unknown_provider_is_rejected(client, authorize_mock):
    response = _upload(client, provider="openai")

    assert response.status_code == 400
    assert "Unknown provider" in response.json()["detail"]
    authorize_mock.assert_not_called()
