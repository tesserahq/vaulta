"""Celery task: run data extraction and summarization for an uploaded asset.

`POST /assets` stores the file, leaves the asset in `processing`, and enqueues
this task. The task reads the bytes back from storage, runs the processors the
upload asked for, saves their output, and moves the asset to `completed`, or to
`processing_failed` if anything requested produced no result. Clients poll
`GET /assets/{id}` until the state leaves `processing`.
"""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.commands.assets.update_asset_command import UpdateAssetCommand
from app.constants.asset import AssetState
from app.core.celery_app import celery_app
from app.db import session_scope
from app.repositories.analysis_config_repository import AnalysisConfigRepository
from app.repositories.asset_repository import AssetRepository
from app.schemas.asset import AssetUpdate
from app.services.processors.base import ProcessorContext
from app.services.processors.factory import build_processors
from app.storage.base import StorageBackend
from app.storage.factory import StorageFactory

logger = logging.getLogger(__name__)


def _process_asset(
    db: Session,
    storage: StorageBackend,
    asset_id: UUID,
    extract_data: bool,
    summarize: bool,
    config_id: Optional[UUID],
    ctx: ProcessorContext,
) -> None:
    asset = AssetRepository(db).get_asset(asset_id)
    if asset is None:
        logger.warning("Asset %s was deleted before processing ran", asset_id)
        return
    if asset.state != AssetState.PROCESSING.value:
        # A redelivered message for an asset that already finished.
        logger.info("Asset %s is %s, skipping processing", asset_id, asset.state)
        return

    config = None
    if config_id is not None:
        config = AnalysisConfigRepository(db).get_by_id(config_id)
        if config is None:
            raise ValueError(f"AnalysisConfig {config_id} no longer exists")

    processors = build_processors(config, extract_data, summarize)
    file_bytes = storage.read(str(asset_id))
    url = storage.get_url(asset_id)

    updates: Dict[str, Any] = {}
    for processor in processors:
        updates.update(processor.process(file_bytes, asset.mime_type, url, ctx))

    # Processors log and swallow their own errors, returning nothing.
    missing = []
    if extract_data and not updates.get("extracted_data"):
        missing.append("data extraction")
    if summarize and not updates.get("summary"):
        missing.append("summary")

    if missing:
        state = AssetState.PROCESSING_FAILED.value
        state_message = f"Processing failed: no result from {', '.join(missing)}"
    else:
        state = AssetState.COMPLETED.value
        state_message = "File upload and processing completed successfully"

    UpdateAssetCommand(db).execute(
        asset_id, AssetUpdate(**updates, state=state, state_message=state_message)
    )


def _mark_processing_failed(db: Session, asset_id: UUID, error: str) -> None:
    UpdateAssetCommand(db).execute(
        asset_id,
        AssetUpdate(
            state=AssetState.PROCESSING_FAILED.value,
            state_message=f"Processing failed: {error}",
        ),
    )


@celery_app.task(name="app.tasks.process_asset.process_asset_task")
def process_asset_task(
    asset_id: str,
    extract_data: bool,
    summarize: bool,
    config_id: Optional[str],
    user_id: str,
    project_id: str,
) -> None:
    """Celery entry point: opens its own session and delegates to _process_asset."""
    asset_uuid = UUID(asset_id)
    try:
        with session_scope() as db:
            _process_asset(
                db,
                StorageFactory.get_backend(),
                asset_uuid,
                extract_data,
                summarize,
                UUID(config_id) if config_id else None,
                ProcessorContext(user_id=UUID(user_id), project_id=project_id),
            )
    except Exception as e:
        logger.exception("Processing failed for asset %s", asset_id)
        # The failed session rolled back; record the failure in a fresh one so
        # pollers don't wait on `processing` forever.
        with session_scope() as db:
            _mark_processing_failed(db, asset_uuid, str(e))
        raise
