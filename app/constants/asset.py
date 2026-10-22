from enum import Enum


class AssetState(Enum):
    """Asset states throughout its lifecycle."""

    PENDING = "pending"  # Asset record created, asset upload not started
    UPLOADING = "uploading"  # Asset upload in progress
    COMPLETED = "completed"  # Asset upload completed successfully
    FAILED = "failed"  # Asset upload failed


class AssetClassification(Enum):
    """Access class for an asset (PRD 0006).

    Legacy rows created before classification existed have a NULL value and are
    treated as shareable by the serve endpoint only.
    """

    PRIVATE = "private"  # Requires an authorized project member to read
    SHAREABLE = "shareable"  # Intentionally reachable by signed serve URL
