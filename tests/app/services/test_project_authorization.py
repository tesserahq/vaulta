"""Custos check for project-scoped uploads: fails closed (PRD 0006)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request

from app.services.project_authorization import authorize_asset_create


def _request(token: str = "tok") -> Request:
    return Request(
        {"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]}
    )


def _custos(allowed=None, error=None) -> MagicMock:
    custos = MagicMock()
    if error is not None:
        custos.authorize.side_effect = error
    else:
        custos.authorize.return_value = SimpleNamespace(allowed=allowed)
    return custos


@pytest.mark.asyncio
async def test_allowed_returns_without_error():
    custos = _custos(allowed=True)
    with patch("app.services.project_authorization.CustosClient", return_value=custos):
        await authorize_asset_create(_request(), uuid4(), "some-domain")

    custos.authorize.assert_called_once()
    assert custos.authorize.call_args.kwargs["domain"] == "some-domain"
    assert custos.authorize.call_args.kwargs["action"] == "create"
    assert custos.authorize.call_args.kwargs["resource"] == "vaulta.asset"


@pytest.mark.asyncio
async def test_denied_raises_403():
    custos = _custos(allowed=False)
    with (
        patch("app.services.project_authorization.CustosClient", return_value=custos),
        pytest.raises(HTTPException) as exc,
    ):
        await authorize_asset_create(_request(), uuid4(), "some-domain")

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_custos_unavailable_fails_closed_with_503():
    custos = _custos(error=ConnectionError("custos down"))
    with (
        patch("app.services.project_authorization.CustosClient", return_value=custos),
        pytest.raises(HTTPException) as exc,
    ):
        await authorize_asset_create(_request(), uuid4(), "some-domain")

    assert exc.value.status_code == 503
