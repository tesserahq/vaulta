import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from uuid import UUID
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.commands.assets.create_asset_command import CreateAssetCommand
from app.commands.assets.update_asset_command import UpdateAssetCommand
from app.repositories.asset_repository import AssetRepository

logger = logging.getLogger(__name__)
from app.schemas.asset import (
    AssetCreate,
    AssetUpdate,
    AssetUploadResponse,
)
from app.storage.base import StorageBackend
from app.constants.asset import AssetClassification, AssetState
from app.config import get_settings
from app.services.processors.base import ProcessorContext
from app.utils.token_utils import sign_serve_url, derive_secret

# client_id embedded in server-minted serve_url tokens. verify_signed_url
# re-derives the secret from whatever client_id is in the payload, so this
# only needs to stay consistent between mint and verify, not match a real
# Client row.
_INTERNAL_SERVE_CLIENT_ID = "vaulta-internal"


@dataclass
class ProcessingRequest:
    """What the worker should run after the file is stored."""

    extract_data: bool
    summarize: bool
    config_id: Optional[UUID]
    ctx: ProcessorContext

    @property
    def requested(self) -> bool:
        return self.extract_data or self.summarize


def _enqueue_processing(asset_id: UUID, processing: ProcessingRequest) -> None:
    from app.tasks.process_asset import process_asset_task

    process_asset_task.delay(
        str(asset_id),
        processing.extract_data,
        processing.summarize,
        str(processing.config_id) if processing.config_id else None,
        str(processing.ctx.user_id),
        processing.ctx.project_id,
    )


def _validate_file_size(asset_size: int) -> None:
    settings = get_settings()
    if asset_size > settings.max_file_size:
        max_size_mb = settings.max_file_size // (1024 * 1024)
        file_size_mb = asset_size // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size allowed is {max_size_mb}MB. File size: {file_size_mb}MB",
        )


def upload_asset(
    file: UploadFile,
    user_id: UUID,
    db: Session,
    storage: StorageBackend,
    name: Optional[str] = None,
    labels: Optional[Dict[str, Any]] = None,
    processing: Optional[ProcessingRequest] = None,
    expires_in: Optional[int] = None,
    project_id: Optional[UUID] = None,
    classification: str = AssetClassification.PRIVATE.value,
) -> AssetUploadResponse:
    asset_repository = AssetRepository(db)
    create_command = CreateAssetCommand(db)
    update_command = UpdateAssetCommand(db)

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
        project_id=project_id,
        classification=classification,
    )
    asset = create_command.execute(asset_data, user_id)

    try:
        update_command.execute(
            asset.id,
            AssetUpdate(
                state=AssetState.UPLOADING.value,
                state_message="File upload in progress",
            ),
        )

        storage.save(asset.id, file)
        url = storage.get_url(asset.id)

        from app.storage.local import LocalStorageBackend

        if isinstance(storage, LocalStorageBackend) and hasattr(
            storage, "generate_serve_token"
        ):
            serve_url = f"/serve/{storage.generate_serve_token(str(asset.id))}"
        elif expires_in is not None:
            settings = get_settings()
            capped_expires_in = min(expires_in, settings.max_serve_url_expiry)
            derived_secret = derive_secret(
                _INTERNAL_SERVE_CLIENT_ID, settings.master_secret_key
            )
            serve_url = sign_serve_url(
                str(asset.id),
                _INTERNAL_SERVE_CLIENT_ID,
                capped_expires_in,
                derived_secret,
            )
        else:
            serve_url = url

        if processing is not None and processing.requested:
            state = AssetState.PROCESSING.value
            state_message = "File stored; processing queued"
        else:
            state = AssetState.COMPLETED.value
            state_message = "File upload completed successfully"
        update_command.execute(
            asset.id, AssetUpdate(state=state, state_message=state_message)
        )

        if state == AssetState.PROCESSING.value:
            try:
                _enqueue_processing(asset.id, processing)
            except Exception:
                # The file is stored, so the upload still succeeds; say why
                # nothing will be extracted instead of leaving it `processing`.
                # The error (it can name the broker host) stays in the logs.
                logger.exception("Could not queue processing for asset %s", asset.id)
                state = AssetState.PROCESSING_FAILED.value
                state_message = "Processing could not be queued"
                update_command.execute(
                    asset.id, AssetUpdate(state=state, state_message=state_message)
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
            state=state,
            state_message=state_message,
            extracted_data=None,
            summary=None,
        )

    except Exception as e:
        update_command.execute(
            asset.id,
            AssetUpdate(
                state=AssetState.FAILED.value,
                state_message=f"Upload failed: {str(e)}",
            ),
        )
        raise
