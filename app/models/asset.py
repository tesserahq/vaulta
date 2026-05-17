from app.models.mixins import TimestampMixin
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db import Base
from app.models.encrypted_types import EncryptedJSONB


class Asset(Base, TimestampMixin):
    """Asset model for storing asset information.
    This model represents an asset in the system and includes fields for
    asset metadata, storage information, and relationships with other models.
    """

    __tablename__ = "assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)  # Human readable name
    filename = Column(String, nullable=False)  # Original filename
    mime_type = Column(String, nullable=False)  # Asset type
    size = Column(Integer, nullable=False)  # Asset size in bytes
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )  # Owner of the asset
    labels = Column(JSONB, default=dict, nullable=False)  # Dictionary of labels
    state = Column(String, nullable=False)  # Asset state
    state_message = Column(
        String, nullable=True
    )  # Message describing the current state
    extracted_data = Column(
        EncryptedJSONB, default=dict, nullable=True
    )  # Extracted data from the asset (encrypted)
    summary = Column(
        EncryptedJSONB, nullable=True
    )  # On-demand prose summary (encrypted)

    # Relationships
    user = relationship("User", back_populates="assets")

    @property
    def human_readable_size(self) -> str:
        """Return the asset size in a human-readable format."""
        size_value = float(self.size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_value < 1024.0:
                return f"{size_value:.1f} {unit}"
            size_value /= 1024.0
        return f"{size_value:.1f} PB"
