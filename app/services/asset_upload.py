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
from app.services.processors.base import AssetProcessor, ProcessorContext


def _validate_file_size(asset_size: int) -> None:
    settings = get_settings()
    if asset_size > settings.max_file_size:
        max_size_mb = settings.max_file_size // (1024 * 1024)
        file_size_mb = asset_size // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size allowed is {max_size_mb}MB. File size: {file_size_mb}MB",
        )


async def upload_asset(
    file: UploadFile,
    user_id: UUID,
    asset_repository: AssetRepository,
    storage: StorageBackend,
    name: Optional[str] = None,
    labels: Optional[Dict[str, Any]] = None,
    processors: Optional[list[AssetProcessor]] = None,
    ctx: Optional[ProcessorContext] = None,
) -> AssetUploadResponse:
    # Measure size without reading content yet
    file.file.seek(0, 2)
    asset_size = file.file.tell()
    file.file.seek(0)

    _validate_file_size(asset_size)

    asset_data = AssetCreate(
        name=name or file.filename,
        filename=file.filename,
        mime_type=file.content_type or "application/octet-stream",
        size=asset_size,
        labels=labels or {},
        state=AssetState.PENDING.value,
        state_message="Asset record created, waiting for upload",
    )
    asset = asset_repository.create_asset(asset_data, user_id)

    try:
        asset_repository.update_asset(
            asset.id,
            AssetUpdate(
                state=AssetState.UPLOADING.value,
                state_message="File upload in progress",
            ),
        )

        # Read bytes once; reset so storage can stream from the same file object
        file_bytes = await file.read()
        file.file.seek(0)

        await storage.save(asset.id, file)
        url = await storage.get_url(asset.id)

        # Run all processors and merge their partial updates
        effective_ctx = ctx or ProcessorContext(user_id=user_id, project_id="*")
        updates: Dict[str, Any] = {}
        for processor in processors or []:
            updates.update(
                await processor.process(
                    file_bytes,
                    file.content_type or "application/octet-stream",
                    url,
                    effective_ctx,
                )
            )

        if updates:
            asset_repository.update_asset(asset.id, AssetUpdate(**updates))

        from app.storage.local import LocalStorageBackend

        if isinstance(storage, LocalStorageBackend) and hasattr(
            storage, "generate_serve_token"
        ):
            serve_url = f"/serve/{storage.generate_serve_token(str(asset.id))}"
        else:
            serve_url = url

        asset_repository.update_asset(
            asset.id,
            AssetUpdate(
                state=AssetState.COMPLETED.value,
                state_message="File upload completed successfully",
            ),
        )

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
        asset_repository.update_asset(
            asset.id,
            AssetUpdate(
                state=AssetState.FAILED.value,
                state_message=f"Upload failed: {str(e)}",
            ),
        )
        raise
