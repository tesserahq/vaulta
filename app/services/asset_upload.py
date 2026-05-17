import logging
from typing import Optional, Dict, Any
from uuid import UUID
from fastapi import UploadFile, HTTPException
from app.repositories.asset_repository import AssetRepository

logger = logging.getLogger(__name__)
from app.schemas.asset import (
    AssetCreate,
    AssetUpdate,
    AssetUploadResponse,
)
from app.storage.base import StorageBackend
from app.constants.asset import AssetState
from app.config import get_settings
from app.services.analysis.base import DocumentAnalysisBackend
from app.services.summarization.claude import ClaudeSummarizationService


async def upload_asset(
    file: UploadFile,
    user_id: UUID,
    asset_repository: AssetRepository,
    storage: StorageBackend,
    name: Optional[str] = None,
    labels: Optional[Dict[str, Any]] = None,
    extract_data: bool = False,
    analysis_backend: Optional[DocumentAnalysisBackend] = None,
    summarize: bool = False,
    summarization_service: Optional[ClaudeSummarizationService] = None,
) -> AssetUploadResponse:
    """
    Upload an asset and create an asset record.

    Args:
        file: The asset to upload
        user_id: The ID of the user uploading the asset
        asset_repository: AssetRepository instance
        storage: StorageBackend instance
        name: Optional custom name for the asset (defaults to original filename)
        labels: Optional dictionary of labels to attach to the asset
        extract_data: If True and analysis_backend is provided, extract data from the document
        analysis_backend: Optional DocumentAnalysisBackend to use for extraction

    Returns:
        AssetUploadResponse: Asset information including ID and URL
    """
    # Get file metadata and validate size
    asset_size = 0
    file.file.seek(0, 2)  # Seek to end of asset
    asset_size = file.file.tell()
    file.file.seek(0)  # Reset file pointer

    # Validate file size
    settings = get_settings()
    if asset_size > settings.max_file_size:
        max_size_mb = settings.max_file_size // (1024 * 1024)
        file_size_mb = asset_size // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size allowed is {max_size_mb}MB. File size: {file_size_mb}MB",
        )

    # Create file record in pending state
    asset_data = AssetCreate(
        name=name or file.filename,
        filename=file.filename,
        mime_type=file.content_type or "application/octet-stream",
        size=asset_size,
        labels=labels or {},
        state=AssetState.PENDING.value,
        state_message="Asset record created, waiting for upload",
    )

    # Save file to database
    asset = asset_repository.create_asset(asset_data, user_id)

    try:
        # Update state to uploading
        asset_repository.update_asset(
            asset.id,
            AssetUpdate(
                state=AssetState.UPLOADING.value,
                state_message="File upload in progress",
            ),
        )

        # Extract data from document if requested (before saving to storage)
        extracted_data = None
        file_content_cache: Optional[bytes] = None
        if extract_data and analysis_backend is not None:
            try:
                file.file.seek(0)
                file_content_cache = await file.read()
                result = await analysis_backend.analyze(
                    file_content_cache, file.content_type or "application/octet-stream"
                )
                extracted_data = result.model_dump()
                file.file.seek(0)
            except Exception:
                file.file.seek(0)  # Reset file pointer even on error

        # Generate summary if requested (reuses cached file bytes when available)
        summary = None
        if summarize and summarization_service is not None:
            try:
                if file_content_cache is None:
                    file.file.seek(0)
                    file_content_cache = await file.read()
                    file.file.seek(0)
                result = await summarization_service.summarize(
                    file_content_cache, file.content_type or "application/octet-stream"
                )
                summary = result.model_dump()
            except Exception:
                logger.exception(
                    "summarization failed for asset %s — summary will be null", asset.id
                )

        # Save file to storage
        await storage.save(asset.id, file)

        # Update asset with extracted data and/or summary if we have them
        if extracted_data is not None or summary is not None:
            asset_repository.update_asset(
                asset.id,
                AssetUpdate(extracted_data=extracted_data, summary=summary),
            )

        # Get URL for accessing the file
        url = await storage.get_url(asset.id)

        # serve_url is the backend-native access URL.
        # Local storage: a /serve/{token} path served by this API.
        # S3 and other backends: the direct presigned URL (no server hop needed).
        from app.storage.local import LocalStorageBackend

        if isinstance(storage, LocalStorageBackend):
            if hasattr(storage, "generate_serve_token"):
                serve_token = storage.generate_serve_token(str(asset.id))
                serve_url = f"/serve/{serve_token}"
            else:
                serve_url = url
        else:
            serve_url = url

        # Update state to completed
        asset_repository.update_asset(
            asset.id,
            AssetUpdate(
                state=AssetState.COMPLETED.value,
                state_message="File upload completed successfully",
            ),
        )

        # Refresh asset to get latest extracted_data
        asset = asset_repository.get_asset(asset.id)

        return AssetUploadResponse(
            asset_id=asset.id,
            url=url,
            serve_url=serve_url,
            name=asset.name,
            filename=asset.filename,
            mime_type=asset.mime_type,
            size=asset.size,
            human_readable_size=asset.human_readable_size,
            labels=asset.labels,
            state=AssetState.COMPLETED.value,
            state_message="File upload completed successfully",
            extracted_data=asset.extracted_data if asset.extracted_data else None,
            summary=asset.summary if asset.summary else None,
        )

    except Exception as e:
        # Update state to failed
        asset_repository.update_asset(
            asset.id,
            AssetUpdate(
                state=AssetState.FAILED.value,
                state_message=f"Upload failed: {str(e)}",
            ),
        )
        raise
