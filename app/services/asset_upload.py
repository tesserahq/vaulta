from typing import Optional, Dict, Any
from uuid import UUID
from fastapi import UploadFile, HTTPException
from app.repositories.asset_repository import AssetRepository
from app.schemas.asset import (
    AssetCreate,
    AssetUpdate,
    AssetUploadResponse,
)
from app.storage.base import StorageBackend
from app.constants.asset import AssetState
from app.config import get_settings
from app.processing.document_analyzer import DocumentAnalyzer


async def upload_asset(
    file: UploadFile,
    user_id: UUID,
    asset_repository: AssetRepository,
    storage: StorageBackend,
    name: Optional[str] = None,
    labels: Optional[Dict[str, Any]] = None,
    extract_data: bool = False,
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
        extract_data: If True, extract data from the document using DocumentAnalyzer

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
        if extract_data:
            try:
                # Read file content for analysis
                file.file.seek(0)  # Reset file pointer
                file_content = await file.read()

                # Analyze the document
                analyzer = DocumentAnalyzer()
                extracted_data = analyzer.analyze(file_content)

                # Reset file pointer for storage.save()
                file.file.seek(0)
            except Exception as e:
                # Log error but don't fail the upload
                # extracted_data will remain None
                file.file.seek(0)  # Reset file pointer even on error
                pass

        # Save file to storage
        await storage.save(asset.id, file)

        # Update asset with extracted data if we have it
        if extracted_data is not None:
            asset_repository.update_asset(
                asset.id,
                AssetUpdate(extracted_data=extracted_data),
            )

        # Get URL for accessing the file
        url = await storage.get_url(asset.id)

        # Generate serve URL for public access
        if hasattr(storage, "generate_serve_token"):
            serve_token = storage.generate_serve_token(str(file.id))
            serve_url = f"/serve/{serve_token}"
        else:
            serve_url = url  # Fallback to regular URL if serve token not supported

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
