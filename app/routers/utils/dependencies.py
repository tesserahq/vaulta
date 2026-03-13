from fastapi import Depends, HTTPException, UploadFile
from app.config import get_settings
from app.models.asset import Asset
from app.models.client import Client
from app.repositories.asset_repository import AssetRepository
from app.repositories.client_repository import ClientRepository
from app.db import get_db
from sqlalchemy.orm import Session
from uuid import UUID


def get_asset_by_id(asset_id: UUID, db: Session = Depends(get_db)) -> Asset:
    """Get an asset by ID or raise 404."""
    asset_repository = AssetRepository(db)
    asset = asset_repository.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


def get_client_by_id(client_id: UUID, db: Session = Depends(get_db)) -> Client:
    """FastAPI dependency to get a client by ID.

    Args:
        client_id: The UUID of the client to retrieve
        db: Database session dependency

    Returns:
        Client: The retrieved client

    Raises:
        HTTPException: If the client is not found
    """
    client = ClientRepository(db).get_client(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


def validate_file_size(file: UploadFile) -> UploadFile:
    """Validate that the uploaded file size is within limits."""
    settings = get_settings()

    # Check if file size is known (some files might not have size info)
    if hasattr(file, "size") and file.size:
        if file.size > settings.max_file_size:
            max_size_mb = settings.max_file_size // (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size allowed is {max_size_mb}MB. File size: {file.size // (1024 * 1024)}MB",
            )

    return file


def get_validated_file(file: UploadFile = Depends(validate_file_size)) -> UploadFile:
    """Get a validated file that passes size checks."""
    return file
