from enum import Enum


class AssetState(Enum):
    """Asset states throughout its lifecycle."""

    PENDING = "pending"  # Asset record created, asset upload not started
    UPLOADING = "uploading"  # Asset upload in progress
    COMPLETED = "completed"  # Asset upload completed successfully
    FAILED = "failed"  # Asset upload failed
