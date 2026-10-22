"""Upload scope checks: a project_id must be authorized by Custos (PRD 0006)."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

UPLOAD_FILE = {"file": ("doc.pdf", b"%PDF-1.4 test", "application/pdf")}


@pytest.fixture
def authorize_mock():
    """Replace the Custos check and record the domain it was asked about.

    The mock raises 403 so the upload stops before storage and cache, which need
    running services. The allowed path is covered by the integration suite.
    """
    mock = AsyncMock(side_effect=HTTPException(status_code=403, detail="denied"))
    with patch("app.routers.assets.authorize_asset_create", mock):
        yield mock


def test_explicit_project_is_authorized_in_that_domain(client, authorize_mock):
    project_id = str(uuid4())

    response = client.post(
        "/assets", files=UPLOAD_FILE, data={"project_id": project_id}
    )

    assert response.status_code == 403
    authorize_mock.assert_awaited_once()
    assert authorize_mock.await_args.args[2] == project_id


def test_global_scope_is_authorized_on_wildcard_domain(client, authorize_mock):
    response = client.post("/assets", files=UPLOAD_FILE, data={"project_id": "*"})

    assert response.status_code == 403
    authorize_mock.assert_awaited_once()
    assert authorize_mock.await_args.args[2] == "*"


def test_invalid_project_id_is_rejected_before_custos(client, authorize_mock):
    response = client.post(
        "/assets", files=UPLOAD_FILE, data={"project_id": "not-a-uuid"}
    )

    assert response.status_code == 400
    authorize_mock.assert_not_awaited()


def test_invalid_visibility_is_rejected_before_custos(client, authorize_mock):
    response = client.post("/assets", files=UPLOAD_FILE, data={"visibility": "public"})

    assert response.status_code == 400
    authorize_mock.assert_not_awaited()
