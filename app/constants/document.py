from enum import Enum


class DocumentState(Enum):
    """Document states throughout its lifecycle."""

    PENDING = "pending"  # Document record created, file upload not started
    UPLOADING = "uploading"  # File upload in progress
    COMPLETED = "completed"  # File upload completed successfully
    FAILED = "failed"  # File upload failed
