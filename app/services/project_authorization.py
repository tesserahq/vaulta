"""Custos checks for project-scoped asset uploads (PRD 0006).

An upload may only attach an asset to a project the caller can create assets in.
The global scope ("*", stored as NULL) is a Custos check on the wildcard domain,
which only administrators hold. Failures close the request: if Custos cannot answer,
the upload is refused rather than accepted without a check.
"""

import asyncio
from uuid import UUID

from fastapi import HTTPException, Request, status
from tessera_sdk.clients.custos import CustosClient
from tessera_sdk.config import get_settings

ASSET_RESOURCE = "vaulta.asset"
GLOBAL_DOMAIN = "*"


async def authorize_asset_action(
    request: Request, user_id: UUID, domain: str, action: str
) -> None:
    """Raise 403 unless Custos allows the caller to ``action`` assets in ``domain``.

    ``create`` covers uploads. ``publish`` covers shareable media, which is reachable
    without login, so it is a separate grant (PRD 0006).
    """
    settings = get_settings()
    if not settings.custos_api_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Custos service not configured",
        )

    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    custos = CustosClient(base_url=settings.custos_api_url, api_token=token)
    try:
        response = await asyncio.to_thread(
            custos.authorize,
            user_id=str(user_id),
            action=action,
            resource=ASSET_RESOURCE,
            domain=domain,
        )
    except Exception:  # noqa: BLE001 - any Custos failure must fail closed
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authorization service unavailable",
        )

    if not response.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to upload to this project",
        )
