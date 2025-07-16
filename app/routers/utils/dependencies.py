from app.db import get_db
from app.models.client import Client
from app.services.asset_service import AssetService
from app.schemas.asset import Asset
from fastapi import Depends, HTTPException
from app.services.client_service import ClientService
from uuid import UUID
from sqlalchemy.orm import Session


def get_asset_by_id(
    asset_id: UUID,
    db: Session = Depends(get_db),
) -> Asset:
    """FastAPI dependency to get an asset by ID.

    Args:
        asset_id: The UUID of the asset to retrieve
        db: Database session dependency

    Returns:
        Asset: The retrieved asset

    Raises:
        HTTPException: If the asset is not found
    """
    asset = AssetService(db).get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


def get_client_by_id(
    client_id: UUID,
    db: Session = Depends(get_db),
) -> Client:
    """FastAPI dependency to get a client by ID.

    Args:
        client_id: The UUID of the client to retrieve
        db: Database session dependency

    Returns:
        Client: The retrieved client

    Raises:
        HTTPException: If the client is not found
    """
    client = ClientService(db).get_client(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
