from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.cache.asset_cache import AssetCache
from app.cache.factory import AssetCacheFactory
from app.config import get_settings
from app.db import get_db
from app.models.analysis_config import AnalysisConfig
from app.models.asset import Asset
from app.models.client import Client
from app.repositories.analysis_config_repository import AnalysisConfigRepository
from app.repositories.asset_repository import AssetRepository
from app.repositories.client_repository import ClientRepository
from app.services.analysis.base import DocumentAnalysisBackend
from app.services.analysis.factory import AnalysisFactory


def get_asset_cache() -> AssetCache:
    """Get the configured asset cache."""
    return AssetCacheFactory.get_cache()


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


def get_analysis_config_by_id(
    config_id: UUID, db: Session = Depends(get_db)
) -> AnalysisConfig:
    """Get an analysis config by ID or raise 404."""
    config = AnalysisConfigRepository(db).get_by_id(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="AnalysisConfig not found")
    return config


def get_client_by_slug(client_id: str, db: Session = Depends(get_db)) -> Client:
    """FastAPI dependency to get a client by client_id (slug).

    Args:
        client_id: The client_id slug to retrieve
        db: Database session dependency

    Returns:
        Client: The retrieved client

    Raises:
        HTTPException: If the client is not found
    """
    client = ClientRepository(db).get_client_by_client_id(client_id)
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


def resolve_analysis_config(
    config_id: Optional[UUID],
    db: Session,
) -> Optional[AnalysisConfig]:
    """Return the AnalysisConfig row for config_id, the default, or None."""
    repo = AnalysisConfigRepository(db)
    if config_id is not None:
        return get_analysis_config_by_id(config_id, db)
    return repo.get_default()


def get_analysis_backend(
    config_id: Optional[UUID],
    db: Session,
) -> Optional[DocumentAnalysisBackend]:
    """Resolve a DocumentAnalysisBackend from an optional config_id.

    If config_id is provided, fetches that AnalysisConfig row and instantiates its provider.
    If config_id is None, uses the DB default config; falls back to the settings singleton.
    Returns None only when no configuration exists at all.
    """
    config = resolve_analysis_config(config_id, db)
    if config is not None:
        return AnalysisFactory.get_backend(config.provider, config.provider_params)

    # No DB config — fall back to settings singleton
    return AnalysisFactory.get_backend()
